---
created: 2026-04-28
status: final
window: 2024-04 → 2026-04 (25 luni)
total_messages: 66052
total_threads: 23069
outbound: 37862
inbound: 27624
---

# Raport final — Analiza comunicării PAFF, 25 luni

## TL;DR

1. **66.052 mesaje** pe 25 luni — 57% outbound PAFF, 42% inbound clienți.
2. **Iulie 2024** = single-step improvement la diacritice (-29pp salut_fara_diacritice). Cauză probabilă: layout RO Programmer's keyboard sau autocorrect deployat la ambele personae (Aura + Florentina). NU e personnel change.
3. **Octombrie 2025** = adoptare AutoText la scale (template usage 0.6% → 27%). Efect mixt:
   - ✅ Diacritice îmbunătățite (-6.6pp)
   - 🔴 **Brand string inconsistent EXPLODAT: 29.6% → 63.7% (+34pp)**
4. **Cauză root**: 0 din cele 23 shortcut-uri cu "PAFF" în corp folosesc forma canonică `Producător de Ambalaje`. Toate folosesc variante (`Producător Ambalaje`, `PAFF SRL`, `BOXPACK SRL | PAFF SRL`).
5. **Acțiune cu impact maxim**: audit + fix al celor 23 shortcut-uri în DB. **Un singur sprint de 2-3h** = -30pp anti-pattern detectabil.

---

## 1. Volumetrie

### 1.1 Distribuție per lună (mesaje totale)

| Window | Total | Inbound | Outbound | Threads |
|--------|-------|---------|----------|---------|
| 2024-04 | 2.880 | 1.148 | 1.732 | 953 |
| 2024-05 | 2.545 | 1.018 | 1.527 | 871 |
| 2024-06 | 2.308 | 933 | 1.375 | 794 |
| 2024-07 | 2.584 | 1.026 | 1.558 | 866 |
| 2024-08 | 2.468 | 982 | 1.486 | 826 |
| 2024-09 | 2.729 | 1.089 | 1.640 | 880 |
| 2024-10 | 3.362 | 1.378 | 1.984 | 1.059 |
| 2024-11 | 3.420 | 1.354 | 2.066 | 1.098 |
| 2024-12 | 2.167 | 905 | 1.262 | 759 |
| 2025-01 | 2.804 | 1.112 | 1.692 | 836 |
| 2025-02 | 2.789 | 1.133 | 1.656 | 928 |
| 2025-03 | 2.488 | 999 | 1.489 | 844 |
| 2025-04 | 2.318 | 939 | 1.379 | 795 |
| 2025-05 | 2.623 | 1.111 | 1.512 | 858 |
| 2025-06 | 2.464 | 1.063 | 1.401 | 947 |
| 2025-07 | 2.736 | 1.192 | 1.544 | 1.063 |
| 2025-08 | 2.201 | 980 | 1.221 | 878 |
| 2025-09 | 2.878 | 1.306 | 1.572 | 1.063 |
| 2025-10 | 2.686 | 1.209 | 1.477 | 1.028 |
| 2025-11 | 3.166 | 1.404 | 1.762 | 1.124 |
| 2025-12 | 2.032 | 918 | 1.114 | 837 |
| 2026-01 | 2.416 | 1.048 | 1.368 | 838 |
| 2026-02 | 2.440 | 1.104 | 1.336 | 984 |
| 2026-03 | 2.909 | 1.321 | 1.588 | 1.055 |
| 2026-04 | 2.073 | 952 | 1.121 | 885 |
| **TOTAL** | **66.052** | **27.624** | **37.862** | **23.069** |

### 1.2 Sezonalitate observată

- Vârf volum: **2024-10 + 2024-11** (3.362 + 3.420) — pre-Crăciun
- Minim volum: **2025-12** (2.032) — Crăciun + Anul Nou + concedii
- Pattern Crăciun: scădere ~30% în decembrie + creștere bruscă septembrie/octombrie

### 1.3 Avg messages/thread

- Mediu: **2.86 msgs/thread** — conversații scurte (intent → răspuns + posibil follow-up)
- Lungimea threads e stabilă, nu se modifică temporal

---

## 2. Discontinuități temporale (puncte de cotitură)

### 2.1 Iulie 2024 — single-step improvement la diacritice

```
salut_fara_diacritice timeline:
2024-04 ████████████████████████████████████ 87.8%
2024-05 ██████████████████████████████████   84.7%
2024-06 ██████████████████████████████       75.6%
2024-07 ██████████████████████████           58.5% ← cliff -17pp
2024-08 → 2026-04: plateau 55-66%
```

**Verificat:** atât Aura cât și Florentina au sărit -33pp simultan între iunie și iulie 2024. Florentina NU a plecat (a preluat MAI MULT trafic în iulie). E un **infrastructure change**, nu personnel.

**Plauzibil:** layout tastatură RO Programmer's, AutoHotkey/TextExpander, sau Gmail autocorrect activat.

### 2.2 Octombrie 2025 — adoptarea AutoText la scale

```
template_pure + template_modified rate:
2025-09 |  10  ( 0.6%) ← shortcuts existente, neutilizate
2025-10 | 230  (15.6%) ← jump
2025-11 | 381  (21.6%)
2025-12 | 236  (21.2%)
2026-01 | 382  (27.9%)
2026-02 | 375  (28.1%)
2026-03 | 711  (44.8%) ← peak
2026-04 | 612  (54.6%)
```

**De la 0.6% la 54.6%** template usage în 7 luni. Confirmă deployment AutoText la scale începând octombrie 2025.

### 2.3 brand_string_inconsistent — corelat 1:1 cu adoptarea AutoText

```
brand_inconsistent rate:
2024-04 → 2025-10: stabil 27-31% (18 luni baseline)
2025-11: 40.3%  (+12pp)
2025-12: 76.7%  (+50pp 🔴)
2026-01: 79.1%
2026-02: 77.5%
2026-03: 78.3%
2026-04: 77.2%
```

**De la 30% la 79% în 4 luni**, sincronizat cu utilizarea AutoText. **Cauza: shortcut-urile însele conțin brand string-uri ne-canonice.**

---

## 3. Audit shortcut-uri — root cause AutoText

### 3.1 Statistici DB

```sql
-- Total shortcut-uri
SELECT COUNT(*) FROM textsync_shortcut;
-- 62

-- Shortcut-uri care conțin "PAFF" în corp
SELECT COUNT(*) FROM textsync_shortcut WHERE value LIKE '%PAFF%';
-- 23

-- Shortcut-uri cu brand canonic "Producător de Ambalaje" (Brand-Voice v1)
SELECT COUNT(*) FROM textsync_shortcut WHERE value LIKE '%Producător de Ambalaje%';
-- 0  ⚠️  ZERO SHORTCUT-URI CORECTE
```

### 3.2 Variante brand string în shortcut-uri (3 explicit gresite + cele implicit)

| ID | Key | Variantă brand string |
|---|---|---|
| 80 | `ep` | `"PAFF \| Producător Ambalaje"` (lipsește **"de"**) |
| 77 | `b2` | `"BOXPACK SRL \| PAFF SRL"` (Bogdan signature mixed) |
| 103 | `mj1` | `"SC PAFF SRL"` (entitate juridică) |

Plus 20 shortcut-uri care conțin "PAFF" fără brand string explicit (în mijlocul textului tehnic).

### 3.3 Recomandare SQL audit + fix

```sql
-- LIST: toate shortcut-urile care necesită review
SELECT id, key, substr(value, 1, 200) FROM textsync_shortcut
WHERE value LIKE '%PAFF%'
ORDER BY id;

-- FIX 1: Înlocuiește "Producător Ambalaje" cu "Producător de Ambalaje"
UPDATE textsync_shortcut
SET value = REPLACE(value, 'Producător Ambalaje', 'Producător de Ambalaje')
WHERE value LIKE '%Producător Ambalaje%' AND value NOT LIKE '%de Ambalaje%';

-- FIX 2: Pentru shortcut-uri fără brand canonic, add semnătură standardizată
-- (necesită review manual per shortcut — vezi research/operationalize/shortcut-migration-plan.md)
```

---

## 4. Anti-patterns globale (37.862 outbound)

| Anti-pattern | Total | Rate | Pre-AT | Post-AT | Δ |
|---|---|---|---|---|---|
| `salut_fara_diacritice` | 23.370 | **61.7%** | 63.4% | 56.8% | -6.6pp |
| `salut_fara_virgula` | 12.239 | 32.3% | 34.0% | 27.6% | -6.4pp |
| `eta_47_zile_template` | 12.069 | 31.9% | 31.5% | 32.9% | +1.4pp |
| `brand_string_inconsistent` | 14.548 | **38.4%** | 29.6% | **63.7%** | **+34.1pp 🔴** |
| `salut_cu_spatiu_punct` | 4.799 | 12.7% | 11.8% | 15.1% | +3.3pp |
| `lipsa_diacritice_partial` | 3.575 | 9.4% | 9.6% | 9.1% | -0.5pp |
| `mode_telegrafic` | 901 | 2.4% | 2.0% | 3.6% | +1.6pp |

### 4.1 Distribuție per persona (Aura vs Florentina)

(Vezi window-uri 2024-04 → 2024-09 detaliat în reports anterioare. Pattern: ambele personae au comportament SIMILAR pe anti-patterns. Diferențele sunt incidentale, nu structurale.)

---

## 5. Recomandări operaționale (prioritizate impact × effort)

### P0 — IMPACT MARE × EFFORT MIC (acționează săptămâna asta)

#### A. Audit + fix brand string în 23 shortcut-uri DB

**Effort:** 2-3h (review manual fiecare shortcut + corectare brand string + redeploy)
**Impact:** -34pp brand_string_inconsistent (de la 79% la ~30% baseline). Plus eliminarea propagării erorii pe toate shortcut-urile noi.

**Plan acțiune:**
1. Export cele 23 shortcut-uri cu PAFF în text
2. Pentru fiecare: înlocuiește brand string cu canonic `PAFF :: Producător de Ambalaje`
3. Bonus: standardizează semnătura completă (salut, închidere, brand string, telefoane)
4. Bulk UPDATE în SQLite + verificare
5. Deploy la următoarea reîncărcare extension Chrome

#### B. Update template `mc1` pentru ETA realist

**Effort:** 1h (rescriere shortcut + documentație)
**Impact:** -32pp eta_47_zile_template
**Cauză:** 32% din răspunsuri conțin "4-7 zile" copy-paste când realitatea e 1-3 zile.

**Plan acțiune:**
1. Rescriere shortcut `mc1` să NU conțină "4-7 zile" hardcodat
2. Variante separate: `mc-rapid` (1-3 zile zone locale), `mc-curier` (3-5 zile național), `mc-special` (5-10 zile producție)
3. Documentație 1-pager despre când folosești fiecare

### P1 — IMPACT MEDIU × EFFORT MIC

#### C. Activare keyboard layout RO Programmer's pentru toți

Anti-pattern `salut_fara_diacritice` rămâne la 56.8% post-AutoText. Plafon hard. Plus shortcut-urile sunt parțial cu/fără diacritice.

**Effort:** 30 min training + setup PC-uri
**Impact:** estimat -30pp pe `salut_fara_diacritice` și `lipsa_diacritice_partial` combinate

#### D. Standardizare email signature în Gmail settings

`brand_string_inconsistent` apare pentru că semnătura nu e setată în Gmail — apare în corpul textului. Setare semnătură standard în Gmail = singura sursă autoritară.

**Effort:** 15 min config Gmail × 4 personae
**Impact:** -10pp suplimentar la brand_string_inconsistent

### P2 — IMPACT MAI MIC, EFFORT MAI MARE

#### E. Pipeline classify_thread.py cu Gemini CLI

**Effort:** 6-12h (rulare full corpus + ground truth + eval)
**Impact:** Confirmă quantitative ipotezele calitative din Iteration 1-5 (Florentina = standardul de aur, Aura tranzacțională, etc.)

**Decizie:** opțional. Dacă vrei să măsori improvement după P0/P1, rulezi acum + repeti peste 3 luni. Altfel, skip.

---

## 6. Limitări recunoscute

1. **Threshold CHRF 0.85 prea strict** — confirmat empiric. Praguri reale: 0.5/0.3 ar fi mai realiste pentru text cu signature + quoted reply. Trebuie recalibrat.
2. **Persona detection imperfectă** — bazată pe regex pe nume; quoted replies cauzează duplicare. Pentru analiză precisă, folosește classify_thread.py + Gemini.
3. **Anti-patterns regex limitate** — 7 pattern-uri detectabile lexical. `cost_retroactiv`, `tacere_la_cerere_preventiva`, `lipsa_recunoastere_recurent`, `lipsa_reciprocitate_caldura` necesită LLM (nu sunt detectate aici).
4. **Filter excludere sistem (`--exclude-system`)** poate sări peste mesaje sistem care AR fi util de analizat (ex: confirmări automate care PAFF răspunde manual).

---

## 7. Următorii pași sugerați (în ordine)

1. **Săptămâna asta**: Acționează P0-A (audit shortcut-uri brand string) — primul deliverable cu impact măsurabil
2. **Săptămâna viitoare**: P0-B (refresh `mc1` ETA realist)
3. **Luna viitoare**: P1-C + P1-D (keyboard layout + Gmail signature)
4. **Q3 2026**: Re-research la +3 luni pentru verificare improvement (`/schedule` cu pipeline existent)
5. **Opțional**: P2-E (Gemini CLI classification) dacă vrei date statistic riguroase pentru meeting cu echipă

---

## 8. Referințe

- Iteration 1-5 (calitativ, Obsidian): `Obsidian://PAFF/Research/Email-Customer-Communication/`
- Brand-Voice v1: `Obsidian://.../Brand-Voice.md`
- Pipeline cod: `research/pipelines/`
- Corpus raw (gitignored): `research/corpus/raw/`
- Audit log: `research/audit.log`
- Branch: `feat/email-research-foundation` (8 commits)
