---
created: 2026-04-29
status: applied
backup: db.sqlite3.bak.20260429-pre-enterprise
applied_via: manual + sqlite + extension/content.js
---

# Enterprise pack — A — toate quick wins

## Aplicat în această sesiune

### 1. Engine features noi (extension/content.js)

**`[[date+Nwd]]` — working days offset**
- Skip Saturday + Sunday automat
- Pattern: `[[date+5wd:DD.MM.YYYY]]`
- Test: Vineri 24.04 + 5wd = Vineri 01.05 (Mon-Fri counted, weekend sărit)
- Util pentru ETA realiste cu curier care nu lucrează SS

**`[[recipient_first]]` — prenume only**
- Returnează primul cuvânt din `[[recipient]]`, capitalizat
- "Aura Chițulescu" → "Aura"
- "ana.maria" (din email local-part) → "Ana"
- Util pentru salut prietenos: `Bună [[recipient_first]],`
- Fallback gracios la "" dacă Gmail parser fail

### 2. `bapi` refactor (3.508 chars, 53 utilizări) — variants noi

Primary păstrat ca-este (text complet specs technice). Adăugate 2 variants:

- **V1 [scurt]** — 8 linii cu emoji bullets pentru cazuri "Cât costă rapid?"
  - Comandă minimă, format grafică, prețuri clișee, termen, promo prima comandă
- **V2 [med]** — 5 secțiuni (grafică + comandă + dimensiuni + prețuri + termen + mostre)
  - Fără spec tehnice BOPP/adeziv (le ai în primary dacă cere clientul)

Total acum: primary (3.508 chars) + V1 (~700 chars) + V2 (~1.500 chars) = 3 niveluri de detalii.

### 3. Cleanup 11 duplicate shortcuts

| ID | Key | Motiv | Înlocuit cu |
|---:|---|---|---|
| 106 | `mc0` | Duplicate al `mc1`, 0 utilizări | `mc1` |
| 109 | `mc3` | Variantă alternativă `mc2`, 0 utilizări | `mc2` |
| 111 | `mp2` | Variantă alternativă `mp1`, 0 utilizări | `mp1` |
| 113 | `nu2` | Refuz extins neutilizat | `nu1` (cu variants) |
| 99 | `la1` | Variantă review request | `la2` (cu variants) |
| 101 | `la3` | Variantă review request | `la2` (cu variants) |
| 102 | `la4` | Variantă review request | `la2` (cu variants) |
| 103 | `mj1` | Vechi majorare preț | `mj2` |
| 84 | `bc1` | Vechi bandă cantități | `bc2` |
| 92 | `livrare1` | Vechi livrare | `livrare2` |
| 96 | `ia2` | Datele 2025-2026 hardcoded | `ia1` (cu placeholder) |

**Verificare nesting:** toate 11 keys au 0 referențe în alte shortcuts → safe delete.

**Backup:** rândurile arhivate în `textsync_shortcut_deletes_20260429` (pot fi restaurate cu INSERT INTO textsync_shortcut SELECT ...).

**Total:** 80 → 69 shortcuts (-13.75%, UI mai curat).

### 4. Tracking — verificare

`extension/content.js:235-264` are funcția `sendUsageToServer()` care apelează endpoint Django `/track-usage/`. Endpoint funcționează (vezi `textsync/views/usage.py`).

**De ce `usage_count` e 0**: extension verifică `auth_token + api_url` în `chrome.storage.local`. Dacă lipsesc → skip silent ("not configured"). Probabil utilizatorii folosesc extension-ul fără să fie loginați la Django backend.

**Pentru activare** (5 min, manual):
1. Pornește Django: `cd /home/cosmin/Work/AutoText && .venv/bin/python manage.py runserver 0.0.0.0:8000`
2. În extension popup → Login cu credențialele tale
3. Verifică în extension popup → Settings: `api_url = http://localhost:8000/api`
4. După 1-2 expand-uri, verifică DB: `sqlite3 db.sqlite3 "SELECT key, usage_count FROM textsync_shortcut WHERE usage_count > 0"`

Dacă vrei tracking persistent fără să rulezi Django local, deploy backend-ul pe server (Docker compose, etc.) — out of scope acum.

## Tests

- **151/151 pass** (145 + 6 noi):
  - 3 teste pentru `[[date+Nwd]]` (forward, single day, backward)
  - 3 teste pentru `[[recipient_first]]` (empty fallback, capitalize, dotted email)

## Statistici cumulate (sesiune 29 aprilie)

| Componentă | Înainte | Acum | Δ |
|---|---:|---:|---:|
| Top body shortcuts cu features avansate | 0 | 11 | +11 |
| Atomic snippets reutilizabile | 0 | 18 | +18 |
| User variables (shared + per-user) | 0 | 48 | +48 |
| Combinații teoretice mc1 PRIMARY | 1 | ~2.880 | +2.879 |
| Engine features (system vars) | 8 | 10 | +2 |
| Engine features (date macros) | 4 unități | 5 unități | +1 (wd) |
| Total shortcuts în DB | 62 | 69 | +7 (atomic) -11 (cleanup) |
| Tests JS | 145 | 151 | +6 |

## Mai rămân pentru altă sesiune (priorități medii din raportul anterior)

- Refactor `la2` consolidat (cu variants din `la1/la3/la4`)
- Refactor `mj2` (majorare preț) cu form placeholder pentru perioadă/procent
- Refactor `bc2` (bandă cantități) cu form placeholder
- Lint script pentru shortcuts (CLI)
- Healthcheck DB (broken `[[var:X]]`, missing nesting)
- Sezonalitate auto pentru `[[greeting]]` (decembrie → "sărbători apropiate")

## Test în producție acum

1. **Reload extension AutoText** în Chrome (CRITICAL — content.js modificat)
2. În compose Gmail tastează:
   - `mc1` → primary cu random pick (1/2880 chance fiecare combinație)
   - `bapi` → primary lung (specs complete)
   - Pentru testare features noi:
     - `Bună [[recipient_first]],` într-un draft → vezi prenume client
     - `Estimare livrare [[date+5wd:DD.MM]]` → vezi data working-days

## Rollback

```bash
# Full rollback
cp db.sqlite3.bak.20260429-pre-enterprise db.sqlite3

# Doar restaurare 11 shortcuts șterse
sqlite3 db.sqlite3 "INSERT INTO textsync_shortcut SELECT * FROM textsync_shortcut_deletes_20260429;"
```

```bash
# Revert engine changes
git revert <commit-sha>
```
