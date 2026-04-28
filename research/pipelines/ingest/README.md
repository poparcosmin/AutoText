# Pipeline Ingest — Gmail → corpus/raw/

Standalone Python fetcher pentru email-uri Gmail, cu OAuth, checkpointing și retry. NU depinde de Claude Code, MCP, sau alte tooling-uri externe — reproductibil pe orice mașină.

---

## Files

- **`schemas.py`** — Pydantic models canonice (Message, Thread, IngestionState)
- **`fetch_gmail.py`** — main fetcher cu OAuth + checkpointing + retry
- **`README.md`** — acest fișier

---

## OAuth Setup (one-time, ~10 min)

### Pas 1 — Google Cloud Project + Gmail API

1. Mergi la https://console.cloud.google.com/
2. Top-left, dropdown proiecte → "New Project"
3. Nume proiect: `paff-email-research` (sau cum vrei)
4. Click "Create"
5. Asigură-te că ești pe noul proiect (top-left dropdown)
6. Search bar sus: `Gmail API` → click rezultatul
7. Click `Enable`

### Pas 2 — OAuth Consent Screen

1. Sidebar stânga → `APIs & Services` → `OAuth consent screen`
2. User Type: `External` → Create
3. App name: `PAFF Email Research`
4. User support email: `contact@paff.ro` (sau tine personal)
5. Developer email: la fel
6. Save and Continue
7. Scopes: skip (nu adăuga nimic, vor fi cerute la runtime)
8. Test users: `Add Users` → `contact@paff.ro` (și orice alt cont vrei să auditezi)
9. Save and Continue → Back to Dashboard

### Pas 3 — OAuth Client ID

1. Sidebar → `APIs & Services` → `Credentials`
2. `Create Credentials` → `OAuth client ID`
3. Application type: `Desktop app`
4. Name: `paff-email-fetcher`
5. Click `Create`
6. Modal "OAuth client created" → `Download JSON`
7. Salvează ca `research/.credentials/credentials.json` în repo

```bash
mkdir -p /home/cosmin/Work/AutoText/research/.credentials
mv ~/Downloads/client_secret_*.json /home/cosmin/Work/AutoText/research/.credentials/credentials.json
chmod 600 /home/cosmin/Work/AutoText/research/.credentials/credentials.json
```

### Pas 4 — Install Python deps

```bash
cd /home/cosmin/Work/AutoText
uv sync --group research
```

### Pas 5 — First run (interactive auth)

```bash
# Test pe ultima luna (rapid, ~210 mesaje):
uv run --group research python research/pipelines/ingest/fetch_gmail.py \
    --user contact@paff.ro \
    --start 2026-04 --end 2026-04 \
    --dry-run
```

La prima rulare:
1. Se va deschide browser-ul automat
2. Selectează contul `contact@paff.ro`
3. Ecran "Google hasn't verified this app" → `Advanced` → `Go to PAFF Email Research (unsafe)`
4. Allow Gmail readonly access
5. Browser zice "The authentication flow has completed"
6. Token salvat în `research/.credentials/token.json` — refresh automat după

`--dry-run` doar numără mesajele fără să fetch-ueze conținut. Verifică că totul funcționează înainte de full pull.

---

## Usage

### ⚠️ ATENȚIE: NU folosi `--extra-filter "in:inbox OR in:sent"`

Pe conturi Gmail cu filtre auto care arhivează inbound (cazul `contact@paff.ro`),
acest filter pierde **toate mesajele de la clienți**. Operatorul `OR` în Gmail
search nu se comportă cum ai aștepta — clauza `in:sent` poate domina și returna
doar SENT folder.

**Verificat empiric (aprilie 2026):**
- Niciun filter: 2.619 mesaje
- `--exclude-system` doar: **2.097** (cu inbound + outbound) ✅
- `--exclude-system --extra-filter "in:inbox OR in:sent"`: 1.122 (lipsesc inbound!) ❌

**Recomandare:** folosește **doar `--exclude-system`**. Daca vrei să excluzi
trash/spam/drafts, foloseste `--extra-filter "-in:trash -in:spam -in:drafts"`.

### Stratified sample (recomandat primul)

1 săptămână per lună × 24 luni ≈ 24 batch-uri × ~50 mesaje = ~1.200 mesaje. Bun pentru prima analiză cu diversitate temporală.

```bash
uv run --group research python research/pipelines/ingest/fetch_gmail.py \
    --user contact@paff.ro \
    --start 2024-04 --end 2026-04 \
    --stratified \
    --exclude-system
```

Estimat: 5-10 min.

### Full pull 24 luni

~50.000 mesaje (inbound + outbound, după excludere zgomot sistem).
Take-uri ~3-4 ore.

```bash
uv run --group research python research/pipelines/ingest/fetch_gmail.py \
    --user contact@paff.ro \
    --start 2024-04 --end 2026-04 \
    --exclude-system
```

### Resume după întrerupere

Dacă a crăpat la jumătate, state file-ul (`research/corpus/_state.json`) ține minte ce s-a făcut. Re-run cu `--resume`:

```bash
uv run --group research python research/pipelines/ingest/fetch_gmail.py \
    --user contact@paff.ro \
    --start 2024-04 --end 2026-04 \
    --resume
```

### Re-research la +6 luni

Same command, alt window:

```bash
uv run --group research python research/pipelines/ingest/fetch_gmail.py \
    --user contact@paff.ro \
    --start 2026-04 --end 2026-10
```

State file separat per user — păstrează istoric.

---

## Output

```
research/corpus/
├── _state.json                       ← checkpoint (gitignored)
└── raw/
    ├── 2024-04/
    │   ├── thread-19abc123def456ab.json
    │   ├── thread-19xyz789012345ef.json
    │   └── ...
    ├── 2024-05/
    └── ...
```

Fiecare thread = un fișier JSON cu array de mesaje sortate cronologic. Schema în `schemas.py`.

---

## Audit log

Toate run-urile sunt logate în `research/audit.log` (gitignored):

```jsonl
{"ts": "2026-04-28T17:30:00+00:00", "action": "run_start", "user": "contact@paff.ro", "windows_count": 25}
{"ts": "2026-04-28T17:30:05+00:00", "action": "window_start", "window": "2024-04", "query": "after:2024/04/01 before:2024/05/01"}
{"ts": "2026-04-28T17:32:18+00:00", "action": "window_done", "window": "2024-04", "messages": 218, "threads": 41}
```

Util pentru debugging și transparency.

---

## Troubleshooting

### "Missing OAuth credentials at .credentials/credentials.json"
→ Refă Pas 3 de mai sus.

### "invalid_grant: Token has been expired or revoked"
→ Șterge `research/.credentials/token.json` și re-run (va re-deschide browser-ul).

### "User type Internal vs External"
→ Folosește `External` cu test users (Pas 2) — `Internal` cere Workspace organization.

### Rate limit / quota exceeded
→ Script throttle-ează deja la 10 req/sec. Dacă tot apare 429, mărește `THROTTLE_SLEEP_SECONDS` în fetch_gmail.py.

### "Access blocked: This app's request is invalid"
→ Verifică în GCP Console → OAuth consent screen că `Test users` îl conține pe userul cu care încerci să te autentifici.

---

## Security notes

- `research/.credentials/` e gitignored — token + credentials nu ies din mașina ta
- Scope `gmail.readonly` — script-ul NU poate trimite/șterge email-uri
- Datele mesajelor stau în `corpus/raw/` (gitignored)
- Audit log gitignored separat

---

## Dezvoltare ulterioară

- `pipelines/enrich/` — clasificare via Gemini CLI
- `pipelines/analyze/` — pattern mining
- `pipelines/report/` — synthesis output

Aceste pipeline-uri citesc DIN `corpus/raw/` (output-ul fetch_gmail.py) și produc enriched/analyzed în `corpus/enriched/`.
