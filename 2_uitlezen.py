from __future__ import annotations

# Stap 2: incidentenlijst ophalen via de lijst-export (CSV) van de ingelogde sessie
# en opslaan in exact hetzelfde formaat als het voorbeeldbestand incident (58).csv.
# Draai eerst 1_inloggen.py zodat sessie.json bestaat.
import csv
import io
import json
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

BASE = "https://soneparprod.service-now.com/incident_list.do"
QUERY = "assignment_group=e68479bb879d4610b42b40480cbb35c0^stateIN1,9,2,3^ORDERBYpriority"

# Kolommen en volgorde zoals in het voorbeeldbestand
KOLOMMEN = [
    "priority", "number", "business_service", "cmdb_ci", "state", "hold_reason",
    "assigned_to", "short_description", "opened_at", "opened_by", "caller_id",
    "u_requested_by", "assignment_group", "u_vip_user", "u_affected_countries",
    "u_affected_companies", "category", "description", "u_vendor_number",
    "sys_updated_on", "sys_updated_by", "resolved_at", "resolved_by",
    "close_code", "close_notes",
]


def decodeer(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1")


def verwerk(tekst: str):
    """Leest de export en geeft rijen terug met precies de kolommen uit KOLOMMEN."""
    lezer = csv.DictReader(io.StringIO(tekst, newline=""))
    ontbrekend = [k for k in KOLOMMEN if k not in (lezer.fieldnames or [])]
    if ontbrekend:
        print("WAARSCHUWING, kolommen niet in export gevonden (leeg gelaten):", ontbrekend)
    return [{k: (r.get(k) or "") for k in KOLOMMEN} for r in lezer]


def schrijf(rows, csv_pad="incident.csv", json_pad="incidenten.json"):
    # Zelfde formaat als het voorbeeld: cp1252, alle velden tussen aanhalingstekens, regeleinde LF
    with open(csv_pad, "w", newline="", encoding="cp1252", errors="replace") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator="\n")
        w.writerow(KOLOMMEN)
        for r in rows:
            w.writerow([r[k] for k in KOLOMMEN])
    with open(json_pad, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def fetch_incidents(
    session_path: str | Path = "sessie.json",
    csv_pad: str | Path = "incident.csv",
    json_pad: str | Path = "incidenten.json",
    headless: bool = True,
) -> list[dict[str, str]]:
    url = (
        f"{BASE}?CSV&sysparm_query={quote(QUERY, safe='')}"
        "&sysparm_default_export_fields=all"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=str(session_path))
        antwoord = context.request.get(url)
        data = antwoord.body()
        browser.close()

    tekst = decodeer(data)
    if "<html" in tekst[:500].lower() or "login" in antwoord.url.lower():
        raise SystemExit("Geen CSV ontvangen: sessie verlopen? Draai 1_inloggen.py opnieuw.")

    rows = verwerk(tekst)
    schrijf(rows, csv_pad=csv_pad, json_pad=json_pad)
    return rows


if __name__ == "__main__":
    rows = fetch_incidents(headless=True)
    print(f"{len(rows)} incidenten opgeslagen in incident.csv en incidenten.json")
