---
created: 2026-04-29
status: applied
backup: db.sqlite3.bak.20260429-pre-fixall
research_source: ~/.claude/data/research/2026-04-29-imbunatatiri-mesaje-cheatsheet.md
branch: feat/autotext-conditional-followups
---

# Fix-all pack — engine conditional + follow-ups + subjects

Aplicate cele 3 layere din raport + brevity audit.

## Layer 3 — Engine

### `[[recipient_email]]` system var
Sister-parser la `[[recipient]]` — întoarce email-ul (nu numele) din chip Gmail.
Fallback gracios la `""` dacă layout schimbă.

### `[[if:LHS op RHS]]A[[else]]B[[endif]]` conditional logic
Pipeline order: nesting → date → system → **if** → form (if rulează după
system vars rezolvate, deci LHS/RHS pot include valorile rezolvate).

**Operatori:**
- `==`, `!=` — string equality (case-insensitive)
- `contains` — substring match
- `startswith`, `endswith` — prefix/suffix match

**Exemple aplicabile:**
```
[[if:[[recipient_email]] endswith .it]]Hello![[else]]Bună ziua,[[endif]]
[[if:[[recipient_email]] contains bialetti]]Hi Iulia,[[else]]Bună ziua,[[endif]]
[[if:[[var:my_name]] == Aura]]Cu drag![[else]]Cu stimă,[[endif]]
```

**Implementare:** `extension/content.js` `processConditionals()` + 7 tests.

## Layer 1 — 8 body shortcuts noi

| Key | Trigger când | Char count |
|---|---|---:|
| `op-fu1` | Day 3 după `op` (soft check) | 609 |
| `op-fu2` | Day 10 după `op` (objection preempt) | 710 |
| `op-fu3` | Day 17 BREAKUP (paradox: more replies) | 738 |
| `op-accept` | Client zice OK, trimit dovada plății | 591 |
| `op-rej` | Client refuză — gather feedback + door open | 520 |
| `proba` | Mostre gratuite (door-opener) | 623 |
| `urg` | Comandă urgentă (priority handling) | 596 |
| `ret` | Re-engagement client inactiv >6 luni | 542 |

Toate cu `[[date-Nd]]` reference la trimiterea originală + reply scaffolding +
`[[%s(sig-personal)]]` per-user.

## Layer 2 — 8 subject line shortcuts

| Key | Subject |
|---|---|
| `subj-op` | `Proformă PAFF #{{nr:Nr proformă\|}}` |
| `subj-mc1` | `Plată confirmată — coletul intră în pregătire` |
| `subj-mp1` | `Plată confirmată — livrare PAFF București` |
| `subj-ffd` | `AWB Dragon Star — coletul a plecat` |
| `subj-ffan` | `AWB Fan Courier — coletul a plecat` |
| `subj-nu1` | `Răspuns cerere ofertă — PAFF` |
| `subj-fu1` | `Quick note pe oferta PAFF` |
| `subj-fu3` | `Să închid oferta din partea noastră?` |

Toate ≤45 chars (Boomerang research: 2-4 words = 46% open rate).

**Test în producție:** verifică empiric dacă AutoText expandează în câmpul
Subject Gmail. Dacă nu, prefix-ul `subj-` te avertizează că e pentru subject.

## Brevity audit — `mp1`, `mc2` PRIMARY scurtate

Research Boomerang: 75-100 words = 51% reply (peak). Sub 80 = top performer 2026.

| Shortcut | Înainte (chars / words) | Acum (chars / words) | Status |
|---|---:|---:|---|
| `mp1` | 877 / ~150 | **316 / ~55** | ✅ Sweet spot |
| `mc2` | 971 / ~165 | **338 / ~58** | ✅ Sweet spot |

Variants V1 (cald) + V2 (scurt) păstrate ca-erau (alternative dacă vrei detalii).

## Tests

- ✅ **161/161 pass** (154 + 7 noi pentru conditionals)
- ✅ **Lint 0 issues** pe DB (lint_shortcuts.py)

## DB final state

- Total shortcuts: **85** (69 + 16 noi)
- Atomic snippets: 18
- User variables: 48
- Engine features: 11 system vars + conditional logic

## Test în producție (după hot-reload extension)

1. Tastează `op-fu1` într-un draft → vezi follow-up cu `[[date-3d]]` rezolvat
2. Tastează `subj-op` în câmpul **Subject** Gmail → verifică expandare
3. Pentru un client cu email `.it`, scrie un draft cu:
   ```
   [[if:[[recipient_email]] endswith .it]]Hello![[else]]Bună ziua,[[endif]]
   ```
   → primul caz returnează "Hello!", al doilea "Bună ziua,"
4. `mp1` / `mc2` PRIMARY acum scurte (1/3 chance fiecare la random pick)

## Rollback

```bash
cp db.sqlite3.bak.20260429-pre-fixall db.sqlite3
git revert <commit-sha>  # pentru engine changes
```
