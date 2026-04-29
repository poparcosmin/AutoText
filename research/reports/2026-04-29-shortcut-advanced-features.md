---
created: 2026-04-29
status: applied
window: 2024-04 → 2026-04
applied_via: research/pipelines/improve/apply_advanced_features.py
backup: db.sqlite3.bak.20260429-pre-advanced
research_source: ~/.claude/data/research/2026-04-29-email-b2b-copywriting-autotext.md
---

# Shortcut refactor cu features avansate AutoText

## Aplicat

1. **10 user variables shared** (× 4 useri = 40 INSERTs):
   - `tel_aura`, `tel_marius`, `tel_marius_2`, `tel_picu`, `tel_office`
   - `iban_boxpack`
   - `webfaq` (URL FAQ)
   - `firma_brand` ("PAFF :: Producător ambalaje")
   - `track_dragon`, `track_fan` (URL tracking)

2. **11 atomic snippets** (building blocks reutilizate prin `[[%s(...)]]`):
   - `salut` — `[[greeting]],`
   - `mts` — `[[random:Mulțumim!|Vă mulțumim!|Mulțumim pentru încredere!]]`
   - `mts_short` — `Mulțumim!`
   - `cta-mod` — call-to-action standard pentru modificări
   - `reply-yn` — reply scaffolding 3 opțiuni
   - `eta-curier` — `Termen estimat livrare: 4-7 zile lucrătoare.`
   - `eta-paff` — `Termen estimat livrare: 1-3 zile lucrătoare (București).`
   - `sig-personal` — semnătură cu `[[user]] + [[var:tel_office]]`
   - `sig-equipe` — `Cu stimă, Echipa PAFF`
   - `track-dragon`, `track-fan` — link tracking

3. **11 top body templates refactorate** cu features avansate:
   - `[[greeting]]` salut auto pe ora zilei
   - `[[date:DD.MM.YYYY]]` data plății concret
   - `[[var:NAME]]` telefoane / IBAN reutilizabile
   - `[[%s(...)]]` snippet nesting pentru DRY
   - `[[random:A|B|C]]` variație micro-frază
   - `{{form:Label|default}}` placeholder la expand (op, ia1, nu1)
   - `$|$` cursor positioning după expand

## Features verificate funcționale în engine

| Feature | Sursa | Funcționează? |
|---|---|---|
| `[[date]]`, `[[date+Nd]]`, `[[date:fmt]]` | content.js:434-438 | ✅ |
| `[[time]]` | content.js:439 | ✅ |
| `[[day]]` | content.js:751 (returnează `Luni, Marți, ...`) | ✅ |
| `[[greeting]]` | content.js:598-603 (<11=dimineața, <18=ziua, else=seara) | ✅ |
| `[[user]]` | content.js:627-635 (din chrome.storage.local.username) | ✅ |
| `[[recipient]]` | content.js:661 → siteParsers (Gmail-only) | ⚠️ vezi probleme |
| `[[var:NAME]]` | content.js:684-740 (recursive depth 3) | ✅ |
| `[[random:A\|B\|C]]` | content.js:605-610 | ✅ |
| `[[select:A\|B\|C]]` | content.js:644-660 (window.prompt blocking) | ✅ |
| `{{name:Label\|default}}` | content.js:480-560 | ✅ |
| `[[%s(other)]]` snippet nesting | content.js:524-548 (max depth 5) | ✅ |
| `$\|$` cursor marker | content.js:781 | ✅ |

## Probleme identificate + soluții aplicate

### P1 — `[[recipient]]` poate returna empty
**Problemă:** Gmail layout schimbă (Google updates) → parser fail → `[[recipient]]` returnează "". Pattern `[[greeting]] [[recipient]],` devine `Bună ziua ,` (comma izolată).

**Soluție aplicată:** NU folosim `[[recipient]]` în nicio template. În locul lui:
- Pentru cazuri unde personalizare e crucială: `{{form:Numele clientului|}}` (user completează 1× la expand, controllable)
- Pentru cazuri standard: `[[greeting]],` standalone (fără recipient)

### P2 — `[[date+Nd]]` ignoră weekend-uri
**Problemă:** `[[date+5d]]` în zi de joi = `Marți` next week (factoring 7 days), nu factoring weekend pentru curier.

**Soluție aplicată:** păstrăm "4-7 zile lucrătoare" ca text static pentru ETA. Folosim `[[date]]` doar pentru "data plății" (today, where weekend doesn't matter).

### P3 — Form placeholder defaults ne-coerente gramatical
**Problemă inițială** (corectată):
```
nu1 V2: "Din păcate {{motiv:|nu putem produce}} {{produs:|aceasta}}."
        Cu defaults goale → "Din păcate nu putem produce aceasta." (OK)
        Cu defaults de la motiv = full sentence → "Din păcate specificul produsului nu intră în portofoliul nostru aceasta." (gramatical greșit)
```

**Soluție:** Single placeholder cu frază completă în default:
```
nu1 V2: "Din păcate, {{motiv:Motiv (frază completă)|nu putem da curs acestei cereri}}."
```

### P4 — Variabile per-user, nu globale
**Constrângere:** Django model — `textsync_uservariable` are `unique_together=(user_id, name)`.

**Soluție aplicată:** INSERT aceeași variabilă cu aceeași valoare pe fiecare user (40 INSERT-uri = 10 vars × 4 useri). Dezavantaj: dacă schimb un telefon, trebuie UPDATE pe 4 useri.

**Future-proof:** dacă adaug user nou, scriptul `apply_advanced_features.py` rulat din nou populează automat variabilele pentru utilizatorul nou (idempotent prin ON CONFLICT).

## Exemplu output expandat

`mc1` → la 14:30, miercuri 29.04.2026, user=Aura:

**Primary** (pick random — 1/3):
```
Bună ziua,

Plata din 29.04.2026 confirmată — mulțumim.

Astăzi pregătim coletele pentru curier.

----------------

INFORMAȚII EXPEDIERE:
 - Termen estimat livrare: 4-7 zile lucrătoare.
 - Vă trimitem numărul de AWB și factura imediat ce pachetul pleacă.

----------------

Pentru orice modificare la adresă sau cantitate, răspundeți la acest email cât mai curând posibil.

Mulțumim!
[cursor pică aici]
```

**Variant 2 scurt** (alt pick random):
```
Bună ziua,

Plata confirmată azi, 29.04.2026. Coletele pleacă în curând prin curier (4-7 zile lucrătoare).

Pentru orice modificare, răspundeți la acest email.

Mulțumim!
[cursor pică aici]
```

## Soluții NOI peste cheatsheet — proposed

Nu sunt aplicate încă (necesită discuție):

1. **`sig-personal` semnătură per-user automată** — atomic snippet `[[user]] + [[var:tel_office]]`. Aplicată indirect (există în atomic, dar shortcut-urile actuale folosesc `sig-equipe`). Pe care alegem ca default?

2. **Conditional logic prin pattern match** — engine NU suportă nativ. Workaround: 2 shortcuts separate (`mc1-buc` vs `mc1-curier`) cu logică în mintea utilizatorului.

3. **Snippet aliases** — `mc1` poate avea trigger și pe `m1`, `mc`. Reduce typo-uri. **DE APLICAT** dacă vrei.

4. **`bapi` (Bandă personalizată — 3.508 chars, 53 utilizări)** — text foarte lung, candidat pentru spargere în atomic snippets sau form-driven assembly. Nu refactorizat încă.

5. **Smart fallback pentru `[[recipient]]`** — engine în content.js:644 are `_promptSelect` cu `window.prompt`. Putem adăuga un layer extra: dacă `[[recipient]]` returnează gol, prompt manual. Asta cere modificare în extension/content.js (small PR).

## Întrebări deschise pentru tine

1. **Confirm că `[[user]]` returnează `cosmin`/`bogdan`/`aura`** (sau altceva)? — verifică în extension popup → "username" field.
2. **Vrei `sig-personal` ca default în `nu1`** (apare semnat cu numele tău/al Aurei) sau menținem `sig-equipe` (generic)?
3. **Aplicăm refactor și pe `bapi`** (banda personalizată, 53 utilizări dar 3508 chars)?
4. **Adăugăm aliases** la top shortcuts (ex: `mc1` cu alias `mc`, `m1`)?

## Test in production

1. Reload extension AutoText
2. În compose Gmail, tastează `mc1` + Tab → vezi un text random din 3 cu `Bună ziua` + data azi
3. Tastează `op` + Tab → la prompt completează "Număr proformă" (ex: 4587), apasă OK → text expandat cu numărul
4. Tastează `nu1` + Tab → la prompt completează motivul (frază completă) → text refuz cu motivul tău

## Rollback

```bash
cp db.sqlite3.bak.20260429-pre-advanced db.sqlite3
```

Sau per-shortcut:
```sql
-- Resetează variants
UPDATE textsync_shortcut SET variants = '[]' WHERE id = 107;
-- Restaurează value din backup table v3
UPDATE textsync_shortcut SET value = (
  SELECT value FROM textsync_shortcut_backup_20260429_v3 WHERE id = 107
) WHERE id = 107;
```

Sau șterge atomic snippets dacă te încurcă în UI:
```sql
DELETE FROM textsync_shortcut WHERE key IN (
  'salut', 'mts', 'mts_short', 'cta-mod', 'reply-yn',
  'eta-curier', 'eta-paff', 'sig-personal', 'sig-equipe',
  'track-dragon', 'track-fan'
);
```
