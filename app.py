from __future__ import annotations

import csv
import io
import os
import re
from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache
from typing import Any, Callable

from flask import Flask, render_template, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

ISSUE_CODE_PATTERN = re.compile(r"\bSPO-\d+\b", re.IGNORECASE)

SLO_DAYS_BY_PRIORITY = {"highest": 1, "high": 30, "medium": 45, "low": 90}

SNOW_PRIORITY_GROUPS = ("Kritiek", "Hoog", "Gemiddeld", "Laag", "Onbekend")

# (group name, match predicate) - order matters, first match wins.
# "highest" must be checked before "high" (substring!), same for "hoogste"/"hoog".
# P1-P4 is the format actually used by the SPO/Jira "Prioriteit" export field.
_SLO_PRIORITY_RULES: tuple[tuple[str, Callable[[str], bool]], ...] = (
    ("highest", lambda p: p.startswith("p1") or p.startswith("1") or "highest" in p or "hoogste" in p or "kritiek" in p or "critical" in p),
    ("high", lambda p: p.startswith("p2") or p.startswith("2") or "high" in p or "hoog" in p),
    ("medium", lambda p: p.startswith("p3") or p.startswith("3") or "medium" in p or "gemiddeld" in p or "normaal" in p or "normal" in p),
    ("low", lambda p: p.startswith("p4") or p.startswith("4") or "low" in p or "laag" in p),
)

# (group name, match predicate) - order matters, first match wins
_SNOW_PRIORITY_RULES: tuple[tuple[str, Callable[[str], bool]], ...] = (
    ("Kritiek", lambda p: p.startswith("1") or "critical" in p or "kritiek" in p),
    ("Hoog", lambda p: p.startswith("2") or "high" in p or "hoog" in p),
    ("Gemiddeld", lambda p: p.startswith("3") or "moderate" in p or "medium" in p or "gemiddeld" in p),
    ("Laag", lambda p: p.startswith("4") or "low" in p or "laag" in p),
)

_TU_PRIORITY_RULES: tuple[tuple[str, Callable[[str], bool]], ...] = (
    ("P1", lambda p: p.startswith("1") or "kritiek" in p),
    ("P2", lambda p: p.startswith("2") or "hoog" in p),
    ("P3", lambda p: p.startswith("3") or "gemiddeld" in p),
    ("P4", lambda p: p.startswith("4") or "laag" in p),
)

DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%d-%m-%Y",
    "%d-%m-%Y %H:%M",
    "%d/%m/%Y",
    "%d/%m/%Y %H:%M",
)

# In-memory "store" so the Kanban view can reuse the most recently
# uploaded SNOW dataset without requiring a second upload.
snow_store_holder: dict[str, dict[str, list[dict[str, Any]]]] = {
    "grouped": {group: [] for group in SNOW_PRIORITY_GROUPS}
}


def empty_snow_grouped() -> dict[str, list[dict[str, Any]]]:
    return {group: [] for group in SNOW_PRIORITY_GROUPS}


def first_of(record: dict[str, Any], *keys: str, default: str = "") -> str:
    """Return the first non-empty value among the given field names."""
    for key in keys:
        value = record.get(key)
        if value:
            return value
    return default


@lru_cache(maxsize=4096)
def parse_record_date(value: str) -> date | None:
    raw = value.strip()
    if not raw:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _as_date_key(value: Any) -> str:
    """Normalize a raw field value into a cache-friendly string key."""
    return str(value or "")


def format_display_date(value: Any) -> str:
    parsed = parse_record_date(_as_date_key(value))
    return parsed.strftime("%d/%m/%Y") if parsed else str(value or "")


def load_records(upload: Any) -> list[dict[str, Any]]:
    """Load a CSV upload, supporting UTF-8-sig and CP1252 encodings."""
    raw_data = upload.stream.read()

    try:
        text = raw_data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw_data.decode("cp1252")

    records = list(csv.DictReader(io.StringIO(text), strict=True))

    if not records or not all(isinstance(item, dict) for item in records):
        raise ValueError("Het CSV-bestand moet een header en records bevatten.")

    return records


def normalize_issue_code(value: Any) -> str:
    match = ISSUE_CODE_PATTERN.search(str(value or "").strip())
    return match.group(0).upper() if match else ""


def _classify(
    priority_raw: Any,
    rules: tuple[tuple[str, Callable[[str], bool]], ...],
    default: str | None,
) -> str | None:
    priority = str(priority_raw or "").strip().lower()
    for label, predicate in rules:
        if predicate(priority):
            return label
    return default


def normalize_tu_priority(value: Any) -> str:
    return _classify(value, _TU_PRIORITY_RULES, default="-")


def normalize_slo_priority(value: Any) -> str | None:
    """Map a raw SPO priority value onto an SLO_DAYS_BY_PRIORITY key.

    Unlike a plain dict lookup, this tolerates Dutch labels, numeric
    prefixes ("2 - High") and casing/whitespace variations, so SLO
    progress keeps working even if the source export's priority
    format changes.
    """
    return _classify(value, _SLO_PRIORITY_RULES, default=None)


def normalize_snow_priority(value: Any) -> str:
    return _classify(value, _SNOW_PRIORITY_RULES, default="Onbekend")


def group_snow_records(snow_records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = empty_snow_grouped()
    for record in snow_records:
        priority_group = normalize_snow_priority(record.get("priority"))
        record["snow_priority_group"] = priority_group
        record["spo_issue_code"] = normalize_issue_code(record.get("short_description", ""))
        grouped[priority_group].append(record)
    return grouped


def _load_and_group_snow(
    snow_file: Any,
    record_filter: Callable[[dict[str, Any]], bool] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], str | None]:
    """Shared upload/parse/group logic for both SNOW import flows."""
    try:
        snow_records = load_records(snow_file)
        if record_filter is not None:
            snow_records = [r for r in snow_records if record_filter(r)]

        snow_grouped = group_snow_records(snow_records)
        snow_store_holder["grouped"] = snow_grouped
        return snow_grouped, snow_records, None

    except (ValueError, csv.Error, UnicodeDecodeError) as exc:
        return empty_snow_grouped(), [], str(exc)


def process_snow_upload(
    snow_file: Any,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], str | None]:
    """Load a SNOW CSV. This general import keeps ALL SNOW records."""
    return _load_and_group_snow(snow_file)


def process_kanban_snow_upload(
    snow_file: Any,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], str | None]:
    """Load SNOW for the Kanban view: only 'Chapter Commerce' incidents."""
    is_chapter_commerce = (
        lambda r: str(r.get("assignment_group", "")).strip().lower() == "chapter commerce"
    )
    return _load_and_group_snow(snow_file, record_filter=is_chapter_commerce)


def build_snow_template_context(snow_grouped: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    counts = {group: len(records) for group, records in snow_grouped.items()}

    return {
        "snow_grouped": snow_grouped,
        "snow_all_incidents": [r for records in snow_grouped.values() for r in records],
        "snow_critical_count": counts["Kritiek"],
        "snow_high_count": counts["Hoog"],
        "snow_medium_count": counts["Gemiddeld"],
        "snow_low_count": counts["Laag"],
        "snow_unknown_count": counts["Onbekend"],
        # "Overig" in the Kanban view groups everything but critical/high.
        "snow_medium_low_other": (
            snow_grouped["Gemiddeld"] + snow_grouped["Laag"] + snow_grouped["Onbekend"]
        ),
        "snow_total_count": sum(counts.values()),
    }


def _index_snow_by_issue_code(
    snow_records: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    snow_by_issue_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for snow_record in snow_records:
        match = ISSUE_CODE_PATTERN.search(str(snow_record.get("short_description", "")))
        if match:
            snow_by_issue_code[match.group(0).upper()].append(snow_record)
    return snow_by_issue_code


def _build_slo_fields(spo_priority: str, created_date: date | None, today: date) -> dict[str, Any]:
    slo_key = normalize_slo_priority(spo_priority)
    slo_days = SLO_DAYS_BY_PRIORITY.get(slo_key) if slo_key else None
    created_days = max((today - created_date).days, 0) if created_date else None

    if created_days is not None and slo_days:
        progress_value = (created_days / slo_days) * 100
        progress_percentage = min(int(progress_value), 100)
        within_slo = created_days <= slo_days
        color_class = "is-green" if within_slo else "is-red"
    else:
        progress_value = progress_percentage = within_slo = None
        color_class = ""

    return {
        "created_days": created_days,
        "slo_days": slo_days,
        "slo_progress_percentage": progress_percentage,
        "slo_progress_value": progress_value,
        "slo_within_target": within_slo,
        "slo_color_class": color_class,
    }


def _build_match_record(
    spo_record: dict[str, Any],
    issue_code: str,
    matching_snow_records: list[dict[str, Any]],
    today: date,
) -> dict[str, Any]:
    snow_record = matching_snow_records[0] if matching_snow_records else None

    snow_numbers = list(
        dict.fromkeys(
            str(r.get("number", "")).strip()
            for r in matching_snow_records
            if str(r.get("number", "")).strip()
        )
    )

    spo_priority = first_of(spo_record, "Prioriteit", "Priority")
    created_raw = first_of(spo_record, "Aangemaakt", "Created")
    created_date = parse_record_date(_as_date_key(created_raw))

    result = {
        "issue_code": issue_code,
        "has_snow_match": bool(matching_snow_records),
        "spo_priority": spo_priority,
        "spark_priority": first_of(
            spo_record,
            "Aangepast veld (Spark ticket priority)",
            "Custom field (Spark ticket priority)",
        ),
        "summary": first_of(spo_record, "Samenvatting", "Summary"),
        "status": first_of(spo_record, "Status", "State"),
        "created": created_raw,
        "created_display": format_display_date(created_raw),
        "updated": format_display_date(first_of(spo_record, "Bijgewerkt", "Updated")),
        "reporter": first_of(spo_record, "Melder", "Reporter"),
        "developer": first_of(spo_record, "Ontwikkelaar", "Creator"),
        "snow_priority": snow_record.get("priority", "") if snow_record else "",
        "snow_priority_group": (
            snow_record.get("snow_priority_group") or normalize_snow_priority(snow_record.get("priority"))
        )
        if snow_record
        else "",
        "tu_priority": normalize_tu_priority(snow_record.get("priority")) if snow_record else "-",
        "snow_summary": snow_record.get("short_description", "") if snow_record else "",
        "snow_created": snow_record.get("sys_created_on", "") if snow_record else "",
        "snow_updated": snow_record.get("sys_updated_on", "") if snow_record else "",
        "snow_assigned_to": snow_record.get("assigned_to", "") if snow_record else "",
        "snow_number": snow_record.get("number", "") if snow_record else "",
        "snow_numbers": snow_numbers,
    }
    result.update(_build_slo_fields(spo_priority, created_date, today))
    return result


def build_matches(
    spo_records: list[dict[str, Any]],
    snow_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    today = date.today()
    snow_by_issue_code = _index_snow_by_issue_code(snow_records)

    matches = []
    for spo_record in spo_records:
        issue_code = normalize_issue_code(
            first_of(spo_record, "Issuecode", "Issue key", "issue key")
        )
        if not issue_code:
            continue

        matching_snow_records = snow_by_issue_code.get(issue_code, [])
        matches.append(_build_match_record(spo_record, issue_code, matching_snow_records, today))

    return matches


def _build_no_match_info(spo_records: list[dict[str, Any]], snow_records: list[dict[str, Any]]) -> str:
    snow_codes = {
        match.group(0).upper()
        for r in snow_records
        if (match := ISSUE_CODE_PATTERN.search(str(r.get("short_description", ""))))
    }
    spo_codes = {
        code
        for r in spo_records
        if (code := normalize_issue_code(first_of(r, "Issuecode", "issue key")))
    }
    return (
        "Geen matches gevonden. "
        f"SPO bevat {len(spo_records)} records ({len(spo_codes)} Issuecodes) en "
        f"SNOW bevat {len(snow_records)} records ({len(snow_codes)} SPO-codes in short_description)."
    )


@app.route("/", methods=["GET", "POST"])
def index():
    matches: list[dict[str, Any]] = []
    snow_grouped = snow_store_holder["grouped"]
    error, info = "", ""
    spo_name, snow_name = "", ""
    spo_loaded, snow_loaded = False, False
    spo_records: list[dict[str, Any]] = []
    snow_records: list[dict[str, Any]] = []

    if request.method == "POST":
        spo_file = request.files.get("spo_file")
        snow_file = request.files.get("snow_file")
        spo_name = spo_file.filename if spo_file else ""
        snow_name = snow_file.filename if snow_file else ""

        # --- SPO upload ---
        if spo_file and spo_file.filename:
            try:
                spo_records = load_records(spo_file)
                spo_loaded = True
            except (ValueError, csv.Error, UnicodeDecodeError) as exc:
                error = f"SPO-upload mislukt: {exc}"
        else:
            error = "SPO: selecteer een CSV-bestand."

        # --- SNOW upload ---
        if snow_file and snow_file.filename:
            snow_grouped, snow_records, snow_err = process_snow_upload(snow_file)
            if snow_err:
                error = f"{error} SNOW-upload mislukt: {snow_err}".strip()
            else:
                snow_loaded = True
        else:
            error = f"{error} SNOW: selecteer een CSV-bestand.".strip()

        # --- Matching ---
        if spo_loaded and snow_loaded:
            matches = build_matches(spo_records, snow_records)
            if not matches:
                info = _build_no_match_info(spo_records, snow_records)

    matched_count = sum(1 for m in matches if m["has_snow_match"])
    counts = {group: len(records) for group, records in snow_grouped.items()}

    return render_template(
        "index.html",
        matches=matches,
        snow_grouped=snow_grouped,
        error=error,
        info=info,
        spo_name=spo_name,
        snow_name=snow_name,
        spo_status="success" if spo_loaded else "error" if request.method == "POST" else "pending",
        snow_status="success" if snow_loaded else "error" if request.method == "POST" else "pending",
        matched_count=matched_count,
        unmatched_count=len(matches) - matched_count,
        snow_critical_count=counts["Kritiek"],
        snow_high_count=counts["Hoog"],
        snow_medium_count=counts["Gemiddeld"],
        snow_low_count=counts["Laag"],
        snow_unknown_count=counts["Onbekend"],
        snow_total_count=sum(counts.values()),
    )


@app.route("/kanban", methods=["GET", "POST"])
def kanban():
    error = ""

    if request.method == "POST":
        snow_file = request.files.get("snow_file")

        if snow_file and snow_file.filename:
            _, kanban_records, error = process_kanban_snow_upload(snow_file)
            if not error and not kanban_records:
                error = "Geen SNOW-incidenten gevonden met assignment_group 'Chapter Commerce'."
        else:
            error = "Selecteer een geldig SNOW CSV-bestand."

    context = build_snow_template_context(snow_store_holder["grouped"])
    context["error"] = error

    return render_template("kanban.html", **context)


if __name__ == "__main__":
    app.run(
        debug=False,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5001")),
    )
