from __future__ import annotations

import csv
import io
import os
import re
from datetime import date, datetime
from typing import Any

from flask import Flask, render_template, request


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

ISSUE_CODE_PATTERN = re.compile(r"\bSPO-\d+\b", re.IGNORECASE)
SLO_DAYS_BY_PRIORITY = {
    "highest": 1,
    "high": 30,
    "medium": 45,
    "low": 90,
}


def parse_record_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    # Try the most common CSV export formats from SPO/SNOW first.
    formats = (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%d-%m-%Y",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M",
    )

    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def format_display_date(value: Any) -> str:
    parsed_date = parse_record_date(value)
    return parsed_date.strftime("%d/%m/%Y") if parsed_date else str(value or "")


def load_records(upload: Any) -> list[dict[str, Any]]:
    """Load a comma-separated export with quoted and multiline fields."""
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


def build_matches(spo_records: list[dict[str, Any]], snow_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = date.today()
    snow_by_issue_code: dict[str, dict[str, Any]] = {}
    for snow_record in snow_records:
        match = ISSUE_CODE_PATTERN.search(str(snow_record.get("short_description", "")))
        if match:
            snow_by_issue_code.setdefault(match.group(0).upper(), snow_record)

    matches = []
    for spo_record in spo_records:
        issue_code = normalize_issue_code(spo_record.get("Issuecode"))
        snow_record = snow_by_issue_code.get(issue_code)
        spo_priority = str(spo_record.get("Prioriteit", "")).strip()
        slo_days = SLO_DAYS_BY_PRIORITY.get(spo_priority.lower())
        created_date = parse_record_date(spo_record.get("Aangemaakt"))
        created_days = max((today - created_date).days, 0) if created_date else None
        if created_days is not None and slo_days:
            progress_value = (created_days / slo_days) * 100
            progress_percentage = min(int(progress_value), 100)
            within_slo = created_days <= slo_days
            slo_color_class = "is-green" if within_slo else "is-red"
        else:
            progress_value = None
            progress_percentage = None
            within_slo = None
            slo_color_class = ""
        if not issue_code:
            continue
        matches.append(
            {
                "issue_code": issue_code,
                "has_snow_match": snow_record is not None,
                "spo_priority": spo_priority,
                "summary": spo_record.get("Samenvatting", ""),
                "created": spo_record.get("Aangemaakt", ""),
                "created_display": format_display_date(spo_record.get("Aangemaakt")),
                "created_days": created_days,
                "slo_days": slo_days,
                "slo_progress_percentage": progress_percentage,
                "slo_progress_value": progress_value,
                "slo_within_target": within_slo,
                "slo_color_class": slo_color_class,
                "updated": spo_record.get("Bijgewerkt", ""),
                "developer": spo_record.get("Ontwikkelaar", ""),
                "snow_priority": snow_record.get("priority", "") if snow_record else "",
                "snow_summary": snow_record.get("short_description", "") if snow_record else "",
                "snow_created": snow_record.get("sys_created_on", "") if snow_record else "",
                "snow_updated": snow_record.get("sys_updated_on", "") if snow_record else "",
                "snow_assigned_to": snow_record.get("assigned_to", "") if snow_record else "",
                "snow_number": snow_record.get("number", "") if snow_record else "",
            }
        )
    return matches


@app.route("/", methods=["GET", "POST"])
def index():
    matches: list[dict[str, Any]] = []
    error = ""
    info = ""
    spo_name = ""
    snow_name = ""
    spo_loaded = False
    snow_loaded = False

    if request.method == "POST":
        spo_file = request.files.get("spo_file")
        snow_file = request.files.get("snow_file")
        spo_name = spo_file.filename if spo_file else ""
        snow_name = snow_file.filename if snow_file else ""

        if not spo_file or not spo_file.filename:
            error = "SPO: selecteer een CSV-bestand."
        else:
            try:
                spo_records = load_records(spo_file)
                spo_loaded = True
            except (ValueError, csv.Error, UnicodeDecodeError) as exc:
                error = f"SPO-upload mislukt: {exc}"

        if not snow_file or not snow_file.filename:
            error = f"{error} SNOW: selecteer een CSV-bestand." if error else "SNOW: selecteer een CSV-bestand."
        else:
            try:
                snow_records = load_records(snow_file)
                snow_loaded = True
            except (ValueError, csv.Error, UnicodeDecodeError) as exc:
                error = f"{error} SNOW-upload mislukt: {exc}" if error else f"SNOW-upload mislukt: {exc}"

        if spo_loaded and snow_loaded:
            matches = build_matches(spo_records, snow_records)
            if not matches:
                snow_codes = {
                    match.group(0).upper()
                    for record in snow_records
                    for match in [ISSUE_CODE_PATTERN.search(str(record.get("short_description", "")))]
                    if match
                }
                spo_codes = {
                    normalize_issue_code(record.get("Issuecode"))
                    for record in spo_records
                    if normalize_issue_code(record.get("Issuecode"))
                }
                info = (
                    f"Geen matches gevonden. SPO bevat {len(spo_records)} records "
                    f"({len(spo_codes)} Issuecodes) en SNOW bevat {len(snow_records)} records "
                    f"({len(snow_codes)} SPO-codes in short_description)."
                )

    return render_template(
        "index.html",
        matches=matches,
        error=error,
        info=info,
        spo_name=spo_name,
        snow_name=snow_name,
        spo_status="success" if spo_loaded else "error" if request.method == "POST" else "pending",
        snow_status="success" if snow_loaded else "error" if request.method == "POST" else "pending",
        matched_count=sum(1 for match in matches if match["has_snow_match"]),
        unmatched_count=sum(1 for match in matches if not match["has_snow_match"]),
    )


if __name__ == "__main__":
    app.run(
        debug=False,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5001")),
    )