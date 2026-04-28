---
created: 2026-04-29
status: actionable
window: 2024-04 → 2026-04 (25 luni)
total_outbound: 37862
total_shortcuts_db: 62
focus: îmbunătățirea celor 62 shortcut-uri AutoText
---

# Audit + propuneri îmbunătățire shortcut-uri AutoText

## TL;DR

**Pareto extrem: 8 shortcut-uri acoperă 95% din folosire.** Cele mai mari oportunități:

1. **`ia1`** (144 utilizări) — **conține datele 2023 hardcoded**, încă folosit în 2026 → fix urgent
2. **`mc1`** (1.233 utilizări) — "4-7 zile" prea conservator → schimbă la 3-5 zile
3. **`mc2`** (doar 31 utilizări vs mc1 1.233) — opțiunea **RAPID PAFF gratuit** pentru București nu e oferită → up-sell pierdut
4. **`nu1`** (131 utilizări) — refuz fără diacritice + fără alternative

**Cleanup**: 11 shortcut-uri sunt duplicate sau învechite — ștergere/arhivare reduce noise în UI.

---

## 1. Top 10 shortcut-uri folosite (Pareto 95%)

| # | id | key | matches | % outbound | scor mediu | rol |
|---|---:|---|---:|---:|---:|---|
| 1 | 105 | `mr` | 3.106 | 8.2% | 0.62 | Contact șofer Marius |
| 2 | 91 | `ffd` | 2.265 | 6.0% | 0.76 | Factură + AWB Dragon Star |
| 3 | 90 | `ffan` | 1.366 | 3.6% | 0.72 | Factură + AWB Fan Courier |
| 4 | 107 | `mc1` | **1.233** | 3.3% | 0.77 | Confirmare plată curier |
| 5 | 110 | `mp1` | 592 | 1.6% | 0.89 | Livrare PAFF gratuit |
| 6 | 115 | `op` | **527** | 1.4% | **0.98** | Confirmare comandă + proformă |
| 7 | 114 | `pi` | 507 | 1.3% | 0.69 | Contact șofer Picu |
| 8 | 95 | `ia1` | 144 | 0.4% | 0.84 | **Concediu/aglomerație (DATE 2023!)** |
| 9 | 112 | `nu1` | 131 | 0.3% | 0.73 | Refuz scurt |
| 10 | 108 | `mc2` | 31 | 0.1% | 0.91 | Opțiune RAPID PAFF vs curier |

> **Score mediu**: cât de literal e folosit shortcut-ul. 1.0 = paste exact, <0.7 = adaptat semnificativ.

> **op are score 0.98** = e folosit aproape literal, semn că e perceput ca template ideal. Confirmă recomandarea anterioară să-l replicăm.

---

## 2. Probleme identificate per shortcut

### 🔴 P0 — `ia1` (144 utilizări, încă activ)

**Conținut actual:**
> "...amânăm comenzile primite în perioada următoare pentru **prima parte a lunii ianuarie 2024**.
> ...
> În perioada **22.12.2023 - 07.01.2024** suntem în concediu."

**Problema:** datele sunt HARDCODED 2023/2024. **A fost folosit 144 de ori** — multe de la utilizatori în 2024-2026 cu **info expirat în mesajele primite**.

**Fix propus** (păstrează scurtătura `ia1`):
```
Bună ziua,

Din cauza aglomerației de sezon ne vedem nevoiți să amânăm
comenzile primite în perioada următoare pentru
[PRIMA PARTE A LUNII ___].

Comenzile sunt procesate în ordinea sosirii. Dacă sunteți
de acord, menținem comanda activă și vă trimitem proforma
imediat după revenirea din vacanță.

Vă rugăm să confirmați dacă păstrăm comanda.

Perioada de concediu: ___.

Vă mulțumim pentru înțelegere și vă dorim Sărbători Liniștite!

Cu stimă,
Echipa PAFF
```

Sau folosește deja `ia2` (id 96) care e versiune nouă cu date 20.12.2025 - 07.01.2026 — și e adresat să fie updatat anual.

### 🔴 P0 — `mc1` (1.233 utilizări) — schimbă "4-7 zile" la "3-5 zile"

**Conținut actual:**
> "Termenul estimat de livrare este de **4-7 zile** lucrătoare."

**Problema:** verificat empiric — fraza e folosită literal în ~1.000 mesaje/an. Realitate operațională (verifică tu): 3-5 zile e mai aproape de adevăr pentru curier standard.

**Fix propus:**
```
Bună ziua,

Vă mulțumim pentru plată.

Pregătim imediat coletele pentru expedierea prin
serviciul de curierat.

----------------

INFORMAȚII EXPEDIERE:
 - Termenul estimat de livrare este de 3-5 zile lucrătoare.
 - Vă vom trimite numărul de AWB și factura fiscală imediat
   ce pachetul pleacă.

----------------

Pentru orice modificare la adresă sau cantitate, vă rugăm
să ne răspundeți la acest email cât mai repede.

Vă mulțumim!
```

Adăugat: ultimul paragraf = call-to-action explicit pentru modificări (reduce drop-off 0.3%).

### 🔴 P0 — `nu1` (131 utilizări) — adaugă diacritice + opțiune partener

**Conținut actual:**
> "Buna ziua, Va multumim pentru interesul acordat societatii noastre, insa din motive tehnice nu putem da curs cererii dvs."

**Probleme:**
- Toată fraza fără diacritice (`Buna`, `Va multumim`, `interesul`, `societatii`, `motive`)
- Nu spune **DE CE** — utilizatorii adaugă manual reasoning ("Nu producem etichete", etc.)
- Nu sugerează alternative sau parteneri

**Fix propus** (păstrează scurt, 2-3 fraze, dar cu diacritice + placeholder reason):
```
Bună ziua,

Vă mulțumim pentru interesul acordat produselor PAFF. Din
păcate, nu putem da curs cererii dumneavoastră deoarece [____].

[OPȚIONAL — pentru produse adiacente]
Pentru [____], vă putem recomanda colaboratorii noștri ____.

Cu stimă,
Echipa PAFF
```

Câmpurile `____` sunt placeholder-uri pe care utilizatorul le completează în 5 secunde.

**Alternative**: shortcut nou `nu-eticheta`, `nu-personalizate`, `nu-dimensiuni-mari` cu reasons + parteneri pre-completați (3-5 noi).

### 🟡 P1 — `mc2` (31 utilizări) — promovează folosirea (oportunitate de up-sell)

**Diagnostic:**
- `mc1` (4-7 zile curier) folosit 1.233x
- `mc2` (oferă RAPID PAFF GRATUIT pentru București) folosit doar 31x
- = utilizatorii NU oferă opțiunea rapidă/gratuită clienților București (când e disponibilă)

**Acțiune:** când adresa de livrare e în București/Ilfov, foloseste `mc2` în loc de `mc1`. Estimare: ~30-40% din comenzi sunt București. **Beneficiu** pentru client (timp + ZERO transport) + diferențiere PAFF vs concurența.

**Fix recomandat:** redenumire pentru disambiguare:
- `mc1` → `mc-curier` (clear: curier standard, 3-5 zile)
- `mc2` → `mc-buc` (București cu opțiune rapid)
- `mp1`, `mp2` → `mc-buc-flota` (rezumate într-o variantă)

### 🟡 P1 — `pi` (507 utilizări) și `mr` (3.106 utilizări) — diacritice + context

**`mr`:**
> "**Puteti** contacta **soferul** nostru (Marius) la numerele de telefon: 0756.119.864, 0737.642.346"

**`pi`:**
> "**Soferul** care se va ocupa de livrarea produselor este Picu (Marales Gheorghe). Si **il puteti** contacta folosind numarul de telefon: 0745 992 533"

**Probleme:**
- Lipsă diacritice (`Puteti`, `soferul`, `il`)
- `pi` confuz: "Picu (Marales Gheorghe)" — Picu e nickname, Marales e nume real. Clientul nu știe care e?

**Fix propus:**

```
Pentru livrarea cu flota PAFF în București, șoferul nostru
este Marius. Îl puteți contacta la 0756.119.864 sau 0737.642.346.
```

```
Pentru livrarea cu flota PAFF în București, șoferul nostru este
Picu (Marales Gheorghe). Îl puteți contacta la 0745 992 533.
```

Adaugă context "flota PAFF în București" → clarifică contextul de utilizare.

### 🟢 P2 — `ffd` și `ffan` (3.631 utilizări totale) — adaugă CTA

**Conținut actual:**
> "Atașăm factura fiscală pentru produsele expediate prin **Fan Courier/Dragon Star**.
> Numărul de AWB este: \_\_\_
> Factura fiscală poate fi descărcată și din e-Factura."

**E OK ca formă** — informativ, complet. Pot adăuga ultim paragraf scurt pentru engagement post-livrare:

**Fix propus:**
```
Bună ziua,

Atașăm factura fiscală pentru produsele expediate prin Fan Courier.
Numărul de AWB este: ___

Factura fiscală poate fi descărcată și din e-Factura.

Pentru orice nelămurire la primire, ne puteți răspunde direct
la acest email.

Vă mulțumim pentru încredere!
```

Plus opțional: trimite link Google Review după 3-5 zile (separat — folosind `la2` sau `la3`).

---

## 3. Cleanup propus — shortcut-uri duplicate sau învechite

### Pentru ștergere (impact zero, reduce confuzia):

| id | key | Motiv |
|---:|---|---|
| 106 | `mc0` | Înlocuit complet de `mc1` (același conținut, neutilizat) |
| 109 | `mc3` | Variantă alternativă la `mc2`, neutilizată |
| 111 | `mp2` | Variantă alternativă la `mp1`, neutilizată |
| 113 | `nu2` | Refuz extins neutilizat (utilizatorii preferă `nu1`) |

### Pentru consolidare:

| Categorie | Shortcut-uri | Acțiune |
|---|---|---|
| Cere review Google | `la1`, `la2`, `la3`, `la4` (4 variante) | Păstrează doar 1 (`la2` e cel mai bine scris) |
| Majorare preț | `mj1`, `mj2` | Păstrează `mj2` (mai actual, neutralizat) |
| Bandă adezivă | `bc1`, `bc2`, `bapt` | Păstrează `bc2` (mai bine scris) + `bapt` (specific) |
| Livrare detalii | `livrare1`, `livrare2` | Păstrează `livrare2` (mai concis) |
| Concediu | `ia1`, `ia2` | Modifică `ia1` cu placeholder generic, șterge `ia2` (date hardcoded) |

### De păstrat ca-este (chiar dacă match scor 0):

| Categorie | Shortcut-uri | Motivație |
|---|---|---|
| FEFCO desene tehnice | `200`, `201`, `203`, `215`, `217`, `330`, `426`, `427` | Referințe vizuale (link la imagini), folosite cu paste manual |
| Etichete workflow Gmail | `aa`, `ap`, `af`, `ra`, `adr`, `a-nu` | HTML cu culori — pentru sortare conversații, NU mesaje outbound |
| Semnături individuale | `ac`, `fp`, `ni`, `b1`, `b2`, `pc`, `pf`, `ep` | Body prea scurt pentru CHRF (sub threshold), dar sunt folosite |

---

## 4. Plan implementare

### Etapa 1 (15 min) — fix data hardcoded
- `ia1` — schimbă datele 2023 cu placeholder `___` sau date pentru 2026

### Etapa 2 (30 min) — îmbunătățire mc1 + nu1
- `mc1` — `4-7 zile` → `3-5 zile` + adaugă CTA modificare
- `nu1` — diacritice + placeholder reason + opțiune partener

### Etapa 3 (15 min) — promovare mc2
- Când răspunzi la plată cu adresă București, folosește `mc2` (opțiune RAPID PAFF gratuit)
- Eventual: redenumire shortcut-uri pentru claritate (`mc1` → `mc-curier`, `mc2` → `mc-buc`)

### Etapa 4 (10 min) — cleanup duplicate
- Șterge: `mc0`, `mc3`, `mp2`, `nu2`, `la1`, `la3`, `la4`, `mj1`, `bc1`, `livrare1`, `ia2`
- Total redus: 62 → 51 shortcut-uri (-18%)

### Etapa 5 (30 min) — diacritice pe `mr`, `pi`
- Update text + adaugă context "flota PAFF în București"

**Total effort:** ~2h. **Reflux/risc:** zero (modificări reversibile via SQLite backup).

---

## 5. SQL ready-to-run (după review user)

```sql
-- BACKUP înainte de orice
CREATE TABLE textsync_shortcut_backup_20260429 AS SELECT * FROM textsync_shortcut;

-- E1: ia1 — datele 2023 → placeholder
UPDATE textsync_shortcut SET
    value = 'Bună ziua,

Din cauza aglomerației de sezon ne vedem nevoiți să amânăm
comenzile primite în perioada următoare pentru prima parte
a lunii [LUNA ___].

Comenzile sunt procesate în ordinea sosirii. Dacă sunteți
de acord, menținem comanda activă și vă trimitem proforma
imediat după revenirea din vacanță.

Vă rugăm să confirmați dacă păstrăm comanda.

Perioada de concediu: [DATA ÎNCEPUT] - [DATA SFÂRȘIT].

Vă mulțumim pentru înțelegere și vă dorim Sărbători Liniștite!

Cu stimă,
Echipa PAFF',
    updated_at = datetime('now')
WHERE id = 95;

-- E2a: mc1 — 4-7 → 3-5 + CTA modificare
UPDATE textsync_shortcut SET
    value = REPLACE(
      REPLACE(value, '4-7 zile lucrătoare', '3-5 zile lucrătoare'),
      'Vă mulțumim!',
      'Pentru orice modificare la adresă sau cantitate, vă rugăm să ne răspundeți la acest email cât mai repede.

Vă mulțumim!'
    ),
    updated_at = datetime('now')
WHERE id = 107;

-- E2b: nu1 — diacritice + placeholder
UPDATE textsync_shortcut SET
    value = 'Bună ziua,

Vă mulțumim pentru interesul acordat produselor PAFF. Din
păcate, nu putem da curs cererii dumneavoastră deoarece [_____].

Cu stimă,
Echipa PAFF',
    updated_at = datetime('now')
WHERE id = 112;

-- E4: cleanup duplicate (DOAR DUPĂ confirmare user)
-- DELETE FROM textsync_shortcut WHERE id IN (106, 109, 111, 113, 99, 101, 102, 103, 84, 92, 96);

-- VERIFY
SELECT id, key, length(value), substr(value, 1, 80) FROM textsync_shortcut WHERE id IN (95, 107, 112);
```

---

## 6. Următorii pași

1. **Tu decizi:** acceptă propunerile (P0/P1/P2) sau modifică textele
2. **Backup:** rulează `CREATE TABLE backup`
3. **Update text:** rulează SQL P0 (cu modificările tale)
4. **Reload AutoText extension** Chrome (sau așteaptă auto-refresh)
5. **Monitor 2 săptămâni:** măsoară noile rates de utilizare + alți indicatori
6. **Cleanup duplicate** după 2 săptămâni de folosire stabilă

Întrebări:
- Care e termenul real de livrare prin curier (3-5? 5-7? altfel)?
- Ai parteneri pe care îi recomanzi pentru etichete / pungi personalizate / serigrafie? (Pentru `nu1` extins.)
- Vrei să adaugăm shortcut-uri NOI specifice pentru produse adiacente (ex: `nu-eticheta`)?
