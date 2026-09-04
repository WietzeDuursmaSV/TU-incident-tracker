# SPO x SNOW Incident Tracker

Een lokale Flask-webapplicatie die SPO-issues koppelt aan ServiceNow-incidenten. De app toont alleen SPO-issues waarvoor een overeenkomstige `SPO-XXXX`-code voorkomt in het veld `short_description` van een SNOW-record.

## Vereisten

- Python 3.9 of hoger
- Een SPO-CSV-export met minimaal het veld `Issuecode`
- Een SNOW-CSV-export met minimaal het veld `short_description`

## Installeren en starten

Open een terminal in de projectmap:

### Starten met npm

```bash
npm run dev
```

Dit commando gebruikt de lokale `.venv`. Als die nog niet bestaat, maakt het commando de virtuele omgeving aan en installeert het automatisch de Python-dependencies uit `requirements.txt`.

### Handmatig starten

Je kunt de app ook rechtstreeks met Python starten:

#### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PORT = "5001"
python app.py
```

#### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PORT=5001
python app.py
```

Open daarna in een browser:

<http://localhost:5001>

Het `npm run dev`-script sluit eerst bestaande processen op de gekozen poort en start daarna de app. De server blijft actief zolang het terminalvenster open is. Stoppen kan met `Ctrl+C`. De npm-start gebruikt bewust geen Flask-reloader, zodat er geen extra achtergrondprocessen ontstaan.

### De volgende keer handmatig starten

De virtuele omgeving en dependencies zijn dan al aanwezig. Gebruik alleen:

#### Windows (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
$env:PORT = "5001"
python app.py
```

#### macOS/Linux

```bash
source .venv/bin/activate
export PORT=5001
python app.py
```

Met npm blijft het eenvoudiger:

```bash
npm run dev
```

## Deployen op Render

Deze app kan direct als Python Web Service op Render draaien.

### Wat moet anders voor productie

- Gebruik Render als Python-service, niet `npm run dev`.
- Start de app met `gunicorn`.
- Laat de app luisteren op `0.0.0.0` en de door Render ingestelde `PORT`.

### Instellingen in Render

Gebruik in het formulier deze waarden:

- **Language:** `Python 3`
- **Branch:** `main` of de branch die je wilt deployen
- **Root Directory:** leeg laten
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`

### Deploy-config in de repo

Er staat ook een Render-configbestand in de repo: `render.yaml`.
Als je die gebruikt, kan Render de service-instellingen automatisch overnemen.

### Belangrijke opmerking

De app verwerkt uploads direct in het verzoek en slaat ze niet permanent op. Dat is geschikt voor Render. Als je later geuploade bestanden of resultaten wilt bewaren, heb je extra opslag nodig.

### Virtuele omgeving verlaten

```bash
deactivate
```

## De applicatie gebruiken

1. Klik bij **SPO** op **Bestand kiezen** en selecteer de SPO-export, bijvoorbeeld `spo data.csv`.
2. Klik bij **SNOW** op **Bestand kiezen** en selecteer de ServiceNow-export, bijvoorbeeld `snow data.csv`.
3. Klik op **Toon matches**.
4. De tabel toont alle SPO-issues waarvoor een match in SNOW is gevonden.

Na een succesvolle zoekopdracht wordt het uploadgedeelte ingeklapt. Klik op **Bestanden wijzigen** om het opnieuw te openen en een andere combinatie van bestanden te selecteren.

## Hoe de matching werkt

SPO is de leidende bron:

- De waarde uit SPO-veld `Issuecode` wordt gelezen, bijvoorbeeld `SPO-8447`.
- In elk SNOW-record wordt gezocht naar een code met het patroon `SPO-nummer` in `short_description`.
- De vergelijking is niet hoofdlettergevoelig en negeert extra spaties rond de SPO-code.
- Alleen records met een overeenkomst worden getoond.
- Als meerdere SNOW-records dezelfde SPO-code bevatten, wordt het eerste SNOW-record gebruikt.

De tabel bevat gegevens uit beide bronnen:

| Bron | Velden |
| --- | --- |
| SPO | `Issuecode`, `Prioriteit`, `Samenvatting`, `Aangemaakt`, `Bijgewerkt`, `Ontwikkelaar` |
| SNOW | `priority`, `number`, `short_description`, `sys_created_on`, `sys_updated_on`, `assigned_to` |

## Ondersteund CSV-formaat

De app verwacht een komma-gescheiden CSV-bestand met een headerregel. Velden met komma's, aanhalingstekens en regeleinden moeten volgens de standaard CSV-regels tussen dubbele aanhalingstekens staan. De aangeleverde exports voldoen hieraan.

```csv
Samenvatting,Issuecode,Prioriteit
Voorbeeldissue,SPO-8447,High
```

Voor SNOW zijn minimaal deze kolommen nodig:

```csv
priority,number,short_description,sys_created_on,sys_updated_on,assigned_to
1 - Kritiek,INC1234567,"(SPO-8447) Security issue",2026-09-03,2026-09-03,Team
```

De parser probeert eerst UTF-8 te gebruiken en valt bij oudere Windows-exports terug op Windows-1252. De maximale uploadgrootte is 25 MB per verzoek.

## Problemen oplossen

- **Geen matches gevonden:** controleer of SPO `Issuecode` bevat en of dezelfde code letterlijk of tussen andere tekst staat in SNOW `short_description`.
- **Upload mislukt:** controleer of beide bestanden geldige CSV zijn, een headerregel bevatten en komma's, aanhalingstekens en regeleinden correct volgens CSV-regels zijn geescaped.
- **Pagina kan niet worden geopend:** controleer of de server nog draait en gebruik precies <http://localhost:5001>.
- **Flask niet gevonden:** activeer eerst de virtuele omgeving (`.\.venv\Scripts\Activate.ps1` op Windows of `source .venv/bin/activate` op macOS/Linux) en installeer daarna opnieuw met `pip install -r requirements.txt`.
