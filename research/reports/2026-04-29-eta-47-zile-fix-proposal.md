---
created: 2026-04-29
status: proposal
parent_report: 2026-04-28-final-aggregate-25-months.md
window: 2024-04 → 2026-04 (25 luni)
target_pattern: eta_47_zile_template (12069 trigger-uri, 31.9% outbound)
---

# Propunere fix — `eta_47_zile_template`

## TL;DR

5 shortcut-uri din `textsync_shortcut` conțin `4-7 zile lucrătoare`. 3 sunt context standalone (cauza regresiei), 2 sunt context comparativ (corect). Fix pe cele 3 standalone reduce ~70-80% din ocurențe.

## Inventar shortcut-uri afectate

| ID | Key | Context | Acțiune |
|---|---|---|---|
| 106 | `mc0` | Standalone — confirmare plată curier "termen estimat 4-7 zile" | **FIX** |
| 107 | `mc1` | Standalone — INFO EXPEDIERE "termenul estimat 4-7 zile" | **FIX** |
| 115 | `op` | Standalone — proformă "în funcție de metoda... 4-7 zile" | **FIX (PRIORITY)** |
| 108 | `mc2` | Comparativ — opțiune CURIER vs PAFF RAPID 1-3 zile | KEEP |
| 109 | `mc3` | Comparativ — opțiune CURIER vs PAFF RAPID 1-3 zile | KEEP |

## Validare empirică în corpus

Top frază în corpus (8000+ ocurențe identice):
> "în funcție de metoda de livrare aleasă produsele pot ajunge la dvs. în 4-7 zile lucrătoare"

= literal din shortcut `op` (id 115).

Trigger-uri totale: 26.682 mesaje cu fraza, 1.392 variante distincte (variațiile vin din level de quoting `>`, `>>`, `>>>` din thread chains). Real distinct templates: ~5-10.

## Decizia business

**Întrebare**: care e ETA realist actual?
- Pre-2025: probabil 4-7 era realist (logistică pre-PAFF flota proprie)
- Post-2025: cu flota proprie București (mc2/mc3), 1-3 zile e norma + 3-5 zile via curier

**Recomandare draft** (de validat cu Bogdan/Aura):

| Shortcut | Înainte | Propunere |
|---|---|---|
| mc0 | "Termen estimat de livrare: 4-7 zile lucrătoare" | "Termen estimat de livrare: 3-5 zile lucrătoare (curier)" |
| mc1 | "Termenul estimat de livrare este de 4-7 zile lucrătoare" | "Termenul estimat de livrare este de 3-5 zile lucrătoare (transport curier)" |
| op | "în funcție de metoda de livrare aleasă, acestea vor ajunge la dvs. în 4-7 zile lucrătoare" | "în funcție de metoda de livrare aleasă, acestea vor ajunge la dvs. în 1-5 zile lucrătoare (1-3 zile flota proprie București, 3-5 zile curier național)" |

## SQL UPDATE ready-to-run (DRAFT — necesită aprobare)

```sql
-- ⚠️ PRE-CHECK: backup tabela inainte
CREATE TABLE textsync_shortcut_backup_20260429 AS
SELECT * FROM textsync_shortcut WHERE id IN (106, 107, 115);

-- mc0 (id 106) — confirmare plată standard
UPDATE textsync_shortcut
SET value = REPLACE(value, '4-7 zile lucrătoare', '3-5 zile lucrătoare (curier)'),
    html_value = REPLACE(html_value, '4-7 zile lucrătoare', '3-5 zile lucrătoare (curier)'),
    updated_at = datetime('now')
WHERE id = 106;

-- mc1 (id 107) — confirmare plată structurat
UPDATE textsync_shortcut
SET value = REPLACE(value, '4-7 zile lucrătoare', '3-5 zile lucrătoare (transport curier)'),
    html_value = REPLACE(html_value, '4-7 zile lucrătoare', '3-5 zile lucrătoare (transport curier)'),
    updated_at = datetime('now')
WHERE id = 107;

-- op (id 115) — proformă cu disclaimer metodă
UPDATE textsync_shortcut
SET value = REPLACE(
        value,
        'acestea vor ajunge la dvs. în 4-7 zile lucrătoare',
        'acestea vor ajunge la dvs. în 1-5 zile lucrătoare (1-3 zile flota proprie București, 3-5 zile curier național)'
    ),
    html_value = REPLACE(
        html_value,
        'acestea vor ajunge la dvs. în 4-7 zile lucrătoare',
        'acestea vor ajunge la dvs. în 1-5 zile lucrătoare (1-3 zile flota proprie București, 3-5 zile curier național)'
    ),
    updated_at = datetime('now')
WHERE id = 115;

-- VERIFY
SELECT id, key, length(value), substr(value, 1, 60) FROM textsync_shortcut WHERE id IN (106, 107, 115);

-- Daca rezultat NEDORIT:
-- INSERT INTO textsync_shortcut SELECT * FROM textsync_shortcut_backup_20260429 ON CONFLICT(id) DO UPDATE SET value=excluded.value, html_value=excluded.html_value;
-- ALTER TABLE textsync_shortcut DROP — sau pastrezi backup-ul indefinit
```

## Impact estimat

Pe baza distribuției actuale (32% outbound msgs trigger pattern):
- Pre-fix: 12.069 trigger-uri / 25 luni
- Post-fix: ~3.000-5.000 trigger-uri (rămân doar mc2/mc3 comparativ + email-uri manuale legacy)
- **Reducere estimată: 60-75%** pe `eta_47_zile_template`

În rate% pe outbound: **31.9% → ~10-12%** în 6-8 săptămâni (timp pentru ca shortcuts să rezolve gradual).

## Risc + rollback

- **Risc principal**: termenii noi pot fi prea optimiști → întârzieri la livrare → rating clienți scade
- **Mitigation**: testează 2 săptămâni cu un singur shortcut (`op`), monitor recenzii Google
- **Rollback**: tabela `textsync_shortcut_backup_20260429` păstrează valorile originale

## Status

- [x] Inventar shortcut-uri afectate
- [x] Validare empirică (8k+ ocurențe identice cu shortcut `op`)
- [x] Draft SQL UPDATE
- [ ] Aprobare business (Bogdan/Aura) — ce ETA real folosim?
- [ ] Run SQL UPDATE pe DB
- [ ] Reload AutoText extension Chrome
- [ ] Re-run anti_patterns peste 4 săptămâni pentru validare
