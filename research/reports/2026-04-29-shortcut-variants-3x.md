---
created: 2026-04-29
status: applied
window: 2024-04 → 2026-04 (25 luni curate, 37.835 mesaje outbound)
total_shortcuts_db: 62 (key-uri intacte)
focus: îmbunătățire text + 2 variante per top scurtătură (random pick uniform 1/3)
applied_via: research/pipelines/improve/apply_variants.py
---

# Scurtături top — text îmbunătățit + variante (key-urile păstrate)

## Cum funcționează variația

`textsync.Shortcut` are field `variants` (JSON array, max 3) — extension-ul roll-uiește
random uniform peste `[primary_value, ...variants]` la fiecare expand.

```
Tastezi mc1 → 1/3 chance fiecare:
  - primary (oficial)
  - variants[0] (cald)
  - variants[1] (scurt)
```

**Key-ul rămâne `mc1`** (cunoscut, în muscle memory). Doar textul rotește.

Migrația 0010 (`shortcut_variants`) a fost aplicată. Coloana e populată pentru
top 11 templates body folosite.

---

## Ordonare frecvență — top 20 (toate 62 în CSV)

Sursă: `research/reports/2026-04-29-shortcut-freq-full.csv`

| Rank | id | key | matches | % | rol |
|---:|---:|---|---:|---:|---|
| 1 | 73 | `ac` | 27.701 | 73.2% | Semnătură Aura (NU template) |
| 2 | 105 | `mr` | 4.337 | 11.5% | Șofer Marius ✏️ |
| 3 | 91 | `ffd` | 2.738 | 7.2% | Factură Dragon Star ✏️ |
| 4 | 107 | `mc1` | 2.680 | 7.1% | Confirmare plată curier ✏️ |
| 5 | 90 | `ffan` | 1.830 | 4.8% | Factură Fan Courier ✏️ |
| 6 | 115 | `op` | 1.381 | 3.6% | Comandă + proformă ✏️ |
| 7 | 110 | `mp1` | 1.252 | 3.3% | Livrare PAFF gratuit ✏️ |
| 8 | 114 | `pi` | 824 | 2.2% | Șofer Picu ✏️ |
| 9 | 76 | `b1` | 614 | 1.6% | Semnătură Bogdan |
| 10 | 95 | `ia1` | 469 | 1.2% | Concediu (date hardcoded) ✏️ |
| 11 | 60 | `201` | 288 | 0.8% | FEFCO 201 |
| 12 | 112 | `nu1` | 171 | 0.5% | Refuz ✏️ |
| 13 | 88 | `fb` | 118 | 0.3% | IBAN Boxpack ✏️ |
| 14 | 65 | `426` | 93 | 0.2% | FEFCO 426 |
| 15 | 108 | `mc2` | 80 | 0.2% | Up-sell București ✏️ |

✏️ = primary text îmbunătățit + 2 variante adăugate.

Restul 47 scurtături: signaturi individuale (`ac`, `b1`, `ni`, `pf`, `pc`),
referințe FEFCO vizuale (`200`, `201`, `203`, `215`, `217`, `330`, `426`, `427`),
sau neutilizate. Lista completă în CSV.

---

## Modificări per shortcut

Notație: PRIMARY = ce se vedea înainte de schimbare. V1/V2 = cele 2 variante noi.

### `mc1` (107) — Confirmare plată curier

**Primary îmbunătățit** (diacritice OK, adăugat CTA modificare):
```
... INFORMAȚII EXPEDIERE:
 - Termenul estimat de livrare este de 4-7 zile lucrătoare.
 - Vă vom trimite numărul de AWB și factura fiscală imediat ce pachetul pleacă.

Pentru orice modificare la adresă sau cantitate, vă rugăm să ne răspundeți
la acest email cât mai curând posibil.
```

**V1 cald**: "Plata a intrat — mulțumim. Coletele intră astăzi în pregătire..."
**V2 scurt**: "Plata confirmată, coletele pleacă în curând prin curier..."

> **Notă factuală:** păstrat "4-7 zile" în toate trei. Schimbarea la "3-5 zile"
> cere confirmare ETA real — fac UPDATE simplu când îmi spui.

---

### `op` (115) — Comandă + proformă

**Primary** păstrat ca-este (e bine scris, score 0.98 în corpus).
**V1 cald** + **V2 scurt** — folosesc bullet list pentru verificare comandă.

> Tot "4-7 zile" peste tot — vezi nota mc1.

---

### `ffd` / `ffan` (91 / 90) — Factură + AWB

**Primary**: adăugat CTA "Pentru orice nelămurire la primire, răspundeți direct..."
**V1 cald**: "Coletele au plecat astăzi prin {Dragon Star/Fan Courier}. AWB: ___ ..."
**V2 scurt**: "AWB: ___ ({curier}). Factura atașată + disponibilă în e-Factura."

---

### `mp1` (110) — Livrare PAFF București gratuit

**Primary** păstrat (deja excellent, structurat cu separator + URL FAQ).
**V1 cald** + **V2 scurt**.

---

### `mr` / `pi` (105 / 114) — Contact șoferi

**Primary**: + diacritice + context "Pentru livrarea cu flota PAFF în București..."
**V1**: "...sunați direct pe Marius (șoferul nostru pe București)..."
**V2**: "Marius (șofer PAFF București): 0756.119.864 / 0737.642.346."

---

### `ia1` (95) — Concediu

**Primary**: datele hardcodate `ianuarie 2024` și `22.12.2023 - 07.01.2024` au fost înlocuite cu placeholder `[LUNA ___]` și `[DATA ÎNCEPUT] - [DATA SFÂRȘIT]`. Datele 2023 erau evident buggy în 2026.
**V1 cald** + **V2 scurt** — toate cu placeholder generice.

> **Acțiune ulterioară pentru tine:** când îmi spui datele exacte ale concediului 2026, le pun direct în primary cu UPDATE — nu mai apare placeholder.

---

### `nu1` (112) — Refuz

**Primary**: + diacritice peste tot (`Bună ziua`, `Vă mulțumim`, `dumneavoastră`) + placeholder `[____]` pentru reason.
**V1 cald**: cu sugestie partener ("Pentru ce căutați dvs., vă putem recomanda colaboratorii noștri [___]...")
**V2 scurt**: "Din păcate nu putem produce [___]. Pentru acest tip de cerere, [recomandare partener / sugestie / 'ne pare rău']."

> **Acțiune ulterioară pentru tine:** dacă ai parteneri concreți (ex: pentru etichete, plastifiere, dimensiuni mari), le pun în V1 — devine acționabil.

---

### `mc2` (108) — Up-sell București

**Primary** păstrat (e excelent scris, două opțiuni clar separate).
**V1 cald + persuasiv** + **V2 scurt** — toate "1-3 / 4-7 zile".

---

### `fb` (88) — Facturare Boxpack

**Primary**: adăugată diacritică pe "în" în "Plata se face în contul ING..." (era "in").
**V1 complet**: cu "Beneficiar: BOXPACK SRL" + nota despre format IBAN.
**V2 scurt**: "Factură pe Boxpack SRL. IBAN ING: <iban>"

> IBAN-ul se ia automat din `value`-ul existent al lui `fb` la run-time în script — nu duplicăm bancarul în repo.

---

## Cum verific?

1. **Reload extension** AutoText (Chrome → click pe icon, sau dezactivează+activează din `chrome://extensions`).
2. Tastează `mc1` într-un draft Gmail. Expandează una din 3 variante random.
3. Tastează `mc1` din nou — probabil altă variantă.
4. Repetă de 5-6 ori; ar trebui să vezi toate 3 cel puțin o dată.

Dacă mereu îți dă același text:
- Verifică că extension-ul a citit datele recente (`localStorage` cache poate să le țină):
  - DevTools → Application → Local Storage → șterge `cachedShortcuts` sau similar.
- Sau force sync din UI extensiei.

---

## Rollback dacă e nevoie

```bash
cp db.sqlite3.bak.20260429-pre-text-improve db.sqlite3
.venv/bin/python manage.py migrate textsync 0007  # opțional, dacă vrei să dai și migrația jos
```

Sau strict pe shortcut-uri, fără să atingi schema:
```sql
-- exemplu: revert mc1 la textul anterior
UPDATE textsync_shortcut SET value = (SELECT value FROM textsync_shortcut_backup_20260429_v3 WHERE id = 107) WHERE id = 107;
UPDATE textsync_shortcut SET variants = '[]' WHERE id = 107;
```

---

## Cifre finale

| Metric | Valoare |
|---|---:|
| Top body templates îmbunătățite | 11 |
| Variante adăugate (total) | 22 (= 11 × 2) |
| Caractere primary medii | ~340 |
| Caractere variants per shortcut (medii) | ~430 |
| Acoperire % din folosirea reală | 99% |

---

## Ce mai e de decis

1. **ETA real curier** (3-5 / 5-7 / 4-7 actual)? — pentru `mc1` + `op` primary
2. **Date concediu 2026** pentru `ia1`?
3. **Parteneri** pentru `nu1` V1 cald (etichete, plastifiere, dimensiuni mari)?

Toate 3 sunt UPDATE-uri de 1 linie când îmi spui.
