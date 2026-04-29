---
created: 2026-04-29
status: actionable
window: 2024-04 → 2026-04 (25 luni curate, 37.835 mesaje outbound)
total_shortcuts_db: 62
focus: 3 variante per top scurtături pentru variație + ordonare completă după frecvență
sql_file: 2026-04-29-shortcut-variants-3x.sql
---

# Scurtături — ordonare completă + 3 variante per top

## TL;DR

Pe 37.835 mesaje outbound (corpus curățat de spam):

- **10 scurtături acoperă 99% din folosire reală în corp de email** — restul de 52 sunt fie semnături individuale, fie variante neutilizate, fie referințe FEFCO vizuale.
- **3 variante** per top scurtătură = same intent, ton diferit (oficial / cald / scurt) → variație în comunicarea cu clienți recurenți.
- Sursă: `research/reports/2026-04-29-shortcut-freq-full.csv` + `research/pipelines/analyze/shortcut_freq.py`.
- SQL ready-to-run: `research/reports/2026-04-29-shortcut-variants-3x.sql` (22 INSERT-uri).

---

## 1. Ordonare completă (62 scurtături) — top 20 body templates

| Rank | id | key | matches | % outbound | Rol |
|---:|---:|---|---:|---:|---|
| 1 | 73 | `ac` | 27.701 | 73.2% | Semnătură Aura (signature, NU template) |
| 2 | 105 | `mr` | 4.337 | 11.5% | Contact șofer Marius |
| 3 | 91 | `ffd` | 2.738 | 7.2% | Factură + AWB Dragon Star |
| 4 | 107 | `mc1` | **2.680** | 7.1% | Confirmare plată curier 4-7 zile |
| 5 | 90 | `ffan` | 1.830 | 4.8% | Factură + AWB Fan Courier |
| 6 | 115 | `op` | **1.381** | 3.6% | Confirmare comandă + proformă |
| 7 | 110 | `mp1` | 1.252 | 3.3% | Livrare PAFF gratuit București |
| 8 | 114 | `pi` | 824 | 2.2% | Contact șofer Picu |
| 9 | 76 | `b1` | 614 | 1.6% | Semnătură Bogdan (signature) |
| 10 | 95 | `ia1` | 469 | 1.2% | Concediu (date 2023 hardcoded!) |
| 11 | 60 | `201` | 288 | 0.8% | FEFCO 201 (link vizual) |
| 12 | 112 | `nu1` | 171 | 0.5% | Refuz scurt fără diacritice |
| 13 | 88 | `fb` | 118 | 0.3% | Cont bancar Boxpack (firma 2) |
| 14 | 65 | `426` | 93 | 0.2% | FEFCO 426 |
| 15 | 108 | `mc2` | 80 | 0.2% | RAPID PAFF București (subutilizat!) |
| 16 | 66 | `427` | 75 | 0.2% | FEFCO 427 |
| 17 | 75 | `ni` | 53 | 0.1% | Semnătură Irina (signature) |
| 18 | 120 | `bapi` | 53 | 0.1% | Bandă personalizată (template lung) |
| 19 | 79 | `pf` | 45 | 0.1% | Semnătură Florian |
| 20 | 83 | `bt` | 41 | 0.1% | "Ok pentru tipar" + Bogdan |

**Restul (42 scurtături)**: <20 matches sau 0 matches. Listă completă în `2026-04-29-shortcut-freq-full.csv`.

> **`ac` (73.2%)**: e semnătura Aura, nu template de body. NU intră în recomandări de variație.

---

## 2. Strategie 3 variante — A/B/C

Ordonare: A [Enterprise] → B [Pragmatic] → C [Escape hatch]

### A [Enterprise] — 3 scurtături separate (`mc1`, `mc1b`, `mc1c`)
**Why enterprise:** zero dependențe pe feature-set extension; control fin pe context (formal/cald/scurt) per client; oricând eliminabil dacă o variantă nu prinde.

- ✅ Funcționează pe orice engine AutoText
- ✅ Permite urmărirea care variantă o folosești cel mai des → consolidare ulterioară
- ❌ Mental load la fiecare email: alegi pe loc varianta

### B [Pragmatic] — sintaxă `{a|b|c}` în 1 scurtătură
- ✅ Random uniform, zero efort cognitiv
- ❌ Necesită engine care suportă (verificat tu — nu toate Chrome AutoText extensions o fac)

### C [Escape hatch] — 1 scurtătură cu 3 paragrafe alternative
- ✅ Zero dependență
- ❌ Trebuie să ștergi 2/3 paragrafe după paste manual

**Recomandare:** A pentru top 5 (mc1, ffd, ffan, op, mp1). Începi cu 2 variante per scurtătură (V1 + V2), adaugi V3 dacă observi rotație utilă.

---

## 3. Variante propuse — top 11 body templates

### `mc1` — Confirmare plată + curier (2.680 utilizări)

**V1 [oficial / B2B serios] — `mc1`** (default; corectat 4-7 → 3-5)
```
Bună ziua,

Vă mulțumim pentru plată.

Pregătim coletele pentru expedierea prin serviciul de curierat.

INFORMAȚII EXPEDIERE:
 - Termenul estimat de livrare este de 3-5 zile lucrătoare.
 - Vă vom trimite numărul de AWB și factura fiscală imediat ce pachetul pleacă.

Pentru orice modificare la adresă sau cantitate, vă rugăm să ne răspundeți la acest email cât mai curând posibil.

Vă mulțumim!
```

**V2 [cald / client recurent] — `mc1b`**
```
Bună ziua,

Plata a intrat — mulțumim.

Coletele intră astăzi în pregătire pentru expediere prin curier. În 3-5 zile lucrătoare ar trebui să ajungă la dvs., iar imediat ce pleacă din depozit vă trimitem AWB-ul și factura fiscală.

Dacă apar modificări la adresă sau cantitate, scrieți-ne pe acest email cât mai repede.

Mulțumim pentru încredere!
```

**V3 [scurt / follow-up rapid] — `mc1c`**
```
Bună ziua,

Plata confirmată, coletele pleacă astăzi/mâine prin curier (3-5 zile lucrătoare). Trimitem AWB-ul imediat ce iese din depozit.

Pentru orice modificare, răspundeți la acest email.

Mulțumim!
```

---

### `ffd` / `ffan` — Factură + AWB (4.568 utilizări totale)

**V1 [oficial] — `ffd` / `ffan`** (default, păstrat + CTA)
```
Bună ziua,

Atașăm factura fiscală pentru produsele expediate prin {Dragon Star|Fan Courier}.

Numărul de AWB este: ___

Factura fiscală poate fi descărcată și din e-Factura.

Pentru orice nelămurire la primire, răspundeți direct la acest email.

Vă mulțumim pentru încredere!
```

**V2 [cald] — `ffdb` / `ffanb`**
```
Bună ziua,

Coletele au plecat astăzi prin {Dragon Star|Fan Courier}.

AWB: ___
Factură atașată (și disponibilă în e-Factura).

La primire, dacă observați ceva ce nu e în regulă, scrieți-ne — rezolvăm rapid.

Mulțumim!
```

**V3 [scurt] — `ffdc` / `ffanc`**
```
Bună ziua,

AWB: ___ ({Dragon Star|Fan Courier})
Factura atașată + disponibilă în e-Factura.

Mulțumim!
```

---

### `op` — Confirmare comandă + proformă (1.381 utilizări)

**V1 [oficial] — `op`** (4-7 → 3-5)
```
Bună ziua,

Vă mulțumim pentru comandă! Găsiți atașată factura proformă aferentă.

Vă rugăm să verificați corectitudinea comenzii (preț, cantitate și dimensiuni). Pentru a grăbi procesul de pregătire a produselor, ne puteți trimite o copie (printscreen, poză) a ordinului de plată după efectuarea transferului bancar.

Produsele vor fi pregătite pentru expediere imediat după confirmarea plății. În funcție de metoda de livrare aleasă, acestea vor ajunge la dvs. în 3-5 zile lucrătoare.

Vă mulțumim!
```

**V2 [cald] — `opb`**
```
Bună ziua,

Mulțumim pentru comandă! Găsiți atașată proforma.

Vă rugăm să verificați:
 - prețul, cantitatea și dimensiunile sunt cele agreate?
 - dacă da, după plată trimiteți-ne un printscreen al ordinului — accelerează start-ul producției.

Pregătim imediat după confirmarea plății; ajung la dvs. în 3-5 zile lucrătoare.

Mulțumim!
```

**V3 [scurt] — `opc`**
```
Bună ziua,

Mulțumim pentru comandă. Atașat: proforma.

După plată, dacă ne trimiteți printscreen-ul ordinului, începem pregătirea imediat. Livrare 3-5 zile lucrătoare.

Mulțumim!
```

---

### `mp1` — Livrare PAFF București (1.252 utilizări)

**V1 [oficial] — `mp1`** (păstrat ca-este)

**V2 [cald] — `mp1b`**
```
Bună ziua,

Plata a intrat — mulțumim!

Coletele pleacă spre București cu mașinile noastre, deci ajung la dvs. în 1-3 zile lucrătoare.

Câteva detalii practice:
 - livrarea e până la sediul dvs., gratuită.
 - șoferul lasă coletele la cel mai apropiat loc de parcare sau în curtea sediului.
 - nu poate urca în clădire (la etaj/birou) — pregătiți cineva la primire dacă e cazul.

Detalii suplimentare: https://www.paff.ro/intrebari-frecvente#q3

Mulțumim!
```

**V3 [scurt] — `mp1c`**
```
Bună ziua,

Plata confirmată, coletele pleacă spre București cu mașinile noastre (1-3 zile lucrătoare, gratuit, până la parcare/curte).

Detalii: https://www.paff.ro/intrebari-frecvente#q3

Mulțumim!
```

---

### `mr` / `pi` — Contact șoferi (5.161 utilizări totale)

**`mr` — Marius**

**V1 [oficial] — `mr`**
```
Pentru livrarea cu flota PAFF în București, șoferul nostru este Marius. Îl puteți contacta la 0756.119.864 sau 0737.642.346.
```

**V2 [cald] — `mrb`**
```
Pentru orice detalii legate de livrare, sună direct pe Marius (șoferul nostru pe București): 0756.119.864 / 0737.642.346.
```

**V3 [scurt] — `mrc`**
```
Marius (șofer PAFF București): 0756.119.864 / 0737.642.346.
```

**`pi` — Picu**

**V1 [oficial] — `pi`**
```
Pentru livrarea cu flota PAFF în București, șoferul nostru este Picu (Marales Gheorghe). Îl puteți contacta la 0745 992 533.
```

**V2 [cald] — `pib`**
```
Pe traseu pe București vă întâlniți cu Picu (Marales Gheorghe), șoferul nostru. Direct la el: 0745 992 533.
```

**V3 [scurt] — `pic`**
```
Picu (Marales Gheorghe), șofer PAFF: 0745 992 533.
```

---

### `ia1` — Concediu (P0 — date 2023 active!)

**V1 [oficial] — `ia1`** (cu placeholder generic)
```
Bună ziua,

Din cauza aglomerației de sezon ne vedem nevoiți să amânăm comenzile primite în perioada următoare pentru prima parte a lunii [LUNA ___].

Comenzile sunt procesate în ordinea sosirii. Dacă sunteți de acord, menținem comanda activă și vă trimitem proforma imediat după revenirea din vacanță.

Vă rugăm să confirmați dacă păstrăm comanda.

Perioada de concediu: [DATA ÎNCEPUT] - [DATA SFÂRȘIT].

Vă mulțumim pentru înțelegere și vă dorim Sărbători Liniștite!
```

**V2 [cald] — `ia1b`**
```
Bună ziua,

În perioada [___] PAFF e în concediu, iar comenzile primite acum se procesează după întoarcere — în prima parte a lunii [___].

Dacă sunteți de acord, păstrăm comanda în coadă și vă trimitem proforma imediat ce reluăm activitatea. Așteptăm un OK scurt din partea dvs.

Sărbători liniștite!
```

**V3 [scurt] — `ia1c`**
```
Bună ziua,

Suntem în concediu între [___] și [___]. Comanda dvs. intră în prima parte a lunii [___] — confirmați dacă o păstrăm.

Mulțumim și sărbători frumoase!
```

---

### `nu1` — Refuz (P0 — fără diacritice + fără reasoning)

**V1 [oficial] — `nu1`** (cu placeholder)
```
Bună ziua,

Vă mulțumim pentru interesul acordat produselor PAFF. Din păcate, nu putem da curs cererii dumneavoastră deoarece [____].

Cu stimă,
Echipa PAFF
```

**V2 [cald, cu sugestie partener] — `nu1b`**
```
Bună ziua,

Mulțumim că v-ați gândit la noi pentru [___]. Din păcate nu producem acest tip de produs — specializarea PAFF este pe ambalaje din carton ondulat.

Pentru ce căutați dvs., vă putem recomanda colaboratorii noștri [___]. Spuneți-ne dacă doriți datele lor de contact.

Cu stimă,
Echipa PAFF
```

**V3 [scurt, factual] — `nu1c`**
```
Bună ziua,

Din păcate nu putem produce [___]. Pentru acest tip de cerere, [recomandare partener / sugestie / "ne pare rău"].

Cu stimă,
Echipa PAFF
```

---

### `mc2` — Up-sell București RAPID (P1 — 80 vs mc1 2.680!)

**V1 [oficial] — `mc2`** (păstrat ca-este)

**V2 [cald, persuasiv] — `mc2b`**
```
Bună ziua,

Mulțumim pentru plată!

Pentru că livrarea e în București, vă putem trimite coletele cu mașinile noastre — vă scapă de costul de curier și vă scurtează termenul.

Cele două variante:

OPȚIUNEA 1 — LIVRARE PAFF (recomandat: rapid, gratuit)
 - 1-3 zile lucrătoare, fără înfoliere
 - șoferul predă în cel mai apropiat loc de parcare / în curtea sediului (nu urcă în clădire)

OPȚIUNEA 2 — CURIER STANDARD
 - 3-5 zile lucrătoare, cu AWB și înfoliere
 - condițiile sunt cele ale firmei de curierat

Care variantă preferați? Aștept un OK scurt și pregătesc expedierea.

Mulțumim!
```

**V3 [scurt] — `mc2c`**
```
Bună ziua,

Plata confirmată. Pentru București vă putem trimite cu flota proprie:
 1) PAFF: 1-3 zile, gratuit, predare la parcare/curte.
 2) Curier: 3-5 zile, cu înfoliere și AWB.

Care preferați?

Mulțumim!
```

---

### `fb` — Facturare Boxpack (118 utilizări)

**V1 [actual] — `fb`** (păstrat)

> Notă: IBAN-ul Boxpack e public (apare pe facturi) dar îl evităm în report markdown
> ca să respectăm hook-ul de PII-guard. Vezi conținutul SQL pentru `fbb`/`fbc`.

**V2 [complet, cu IBAN format clar] — `fbb`** (IBAN preluat din shortcut-ul `fb` existent)

**V3 [scurt] — `fbc`** (IBAN preluat din shortcut-ul `fb` existent)

---

## 4. Plan implementare

**Etapa 1 (5 min) — INSERT variante noi**
- Backup + rulează `2026-04-29-shortcut-variants-3x.sql`
- Rezultat: 22 scurtături noi (NU schimbă nimic existent)

**Etapa 2 (5 min) — UPDATE pe textele cu probleme** (raport anterior)
- `ia1` (id 95) — datele 2023 → placeholder
- `mc1` (id 107) — `4-7` → `3-5`
- `nu1` (id 112) — diacritice + placeholder reason
- `mr` (id 105) — diacritice + context "flota PAFF"
- `pi` (id 114) — diacritice + context

**Etapa 3 (1 săptămână) — folosire variată**
- Rotează între `mc1`/`mc1b`/`mc1c` în funcție de context client
- Decizie 3 secunde: formal? cald? scurt?

**Etapa 4 (după 2 săptămâni) — măsoară**
- Re-rulezi `shortcut_freq.py` pe corpus actualizat
- Vezi care variantă a "prins" → consolidare
- Observi dacă rate de răspuns la `mc1`/`mc2` (acum 80 vs 2.680) se schimbă

---

## 5. Întrebări deschise

1. **Pe care 2-3 scurtături să începem?** Recomandare: `mc1` + `op` + `nu1` (cele mai vizibile pentru clienți).
2. **Pentru `nu1b` (sugestie parteneri):** ai cu cine? Pentru ce produse? — fără asta, varianta rămâne placeholder.
3. **Vrei să vezi tabelul complet 62 scurtături sortat?** CSV-ul `2026-04-29-shortcut-freq-full.csv` are tot — restul de 42 sunt fie pure-signatures, fie 0 matches.
