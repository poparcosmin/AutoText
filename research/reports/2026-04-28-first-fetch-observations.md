---
created: 2026-04-28
batch_id: 2026-04-28-batch-001
status: preliminary
window: 2026-04-21 → 2026-04-28 (7 zile)
sample_size: 10 mesaje (din ~50+ disponibile în fereastră)
---

# Primele observații — fetch real Gmail `contact@paff.ro`

> **Status:** observații pe sample minim (10 mesaje). NU statistic significant. Servește la validare ipoteze + descoperire pattern-uri necunoscute pentru următorul batch mai mare.

## Volumetrie reală observată

| Fereastră | Count | Extrapolare |
|---|---|---|
| 7 zile (21-28 apr 2026) | 50+ (cu pagination, full count pending) | ~7 mesaje/zi |
| 30 zile estimat | ~210 | — |
| 24 luni estimat | **~5.000** | (vs estimare inițială 22.000 — revizuit major) |

**Diferență vs estimarea inițială:** 5.000 vs 22.000 — supraestimasem cu 4-5×. Bun pentru noi: pipeline 5× mai rapid + mai puțin tokens consumate la clasificare.

## Filtrare automată necesară

Din 10 mesaje extrase, **4 sunt sistem/automate** (40%):

| Tip | Count | Filter rule pentru pipeline |
|---|---|---|
| Notificări `Comanda noua pe site: #XXXXX` (WooCommerce auto) | 2 | Subject regex `^Comanda noua pe site:` |
| Reset parolă auto | 1 | Subject regex `^Resetare parolă` + From self |
| Newsletter `no-reply@*` | 1 | From regex `no-reply@` sau `noreply@` |

**Recomandare query Gmail rafinată:** adaugă `-from:no-reply* -subject:"Comanda noua pe site" -subject:"Resetare parolă"` pentru a reduce fetch volume. Sau filter post-fetch dacă vrem urme de sistem pentru audit.

## Pattern-uri vizibile imediat (n=6 human messages)

### ✅ Confirmare anti-pattern-uri din Iteration 1-5

1. **`salut_fara_diacritice` confirmat** — răspunsul Aura către Lasatex începe cu `"Buna ziua ."` (fără diacritică pe `ă` + spațiu+punct)
2. **`eta_47_zile_template` confirmat** — la cerere ofertă (Lasatex) PAFF răspunde generic `"4-7 zile lucrătoare de la plata"` fără să țină cont că e doar cerere ofertă, nu comandă plată
3. **`brand_string_inconsistent` confirmat** — semnătura folosită alternativ: `"PAFF :: Producator ambalaje"` (fără diacritice + lipsă "de") vs `"PAFF :: Producător Ambalaje"` (corect parțial) — niciodată exact `"PAFF :: Producător de Ambalaje"` cum cere Brand-Voice v1
4. **`lipsa_diacritice_partial`** — frecvent în răspunsurile ad-hoc Aura: `"Comanda minima este in valoare de 50 lei fata tva / dimensiune"` (lipsă `ă, ț`, `față de` scris greșit)

### 🆕 NEW INSIGHT — contrazice "structural defensive prin template"

**Cazul Pursehuit.ro (thread 19dd430b4b842c0d):**

Aura a primit confirmare plată simplă (`"Buna ziua, Am atasat op."`) și a răspuns cu template `mc1` MODIFICAT — a inserat ÎNAINTE de body-ul template-ului:

> *"Vă mulțumim pentru plată **, daca avem drum in zona va aducem noi comanda mai repede 1-3 zile.**"*

**De ce contează:** Iteration 5 concluziona că PAFF este *"structural defensiv prin template — pierde ocazia să construiască încredere prin underpromise/overdeliver"*. Acest mesaj contrazice direct ipoteza:
- Aura A modificat template-ul ad-hoc
- A oferit timeline mai bun (1-3 zile vs 4-7)
- A făcut-o pentru un client local pe care îl recunoaște

**Dar:** template-ul rămâne după (`"4-7 zile lucrătoare"` apare în continuare în corp), creând **inconsistență internă în același mesaj** — promit 1-3 zile dar tot pun "4-7 zile" copy-paste 3 rânduri mai jos.

**Întrebare nouă pentru cercetarea full:** ce % din răspunsuri PAFF au modificări ad-hoc benefice? Sunt concentrate la anumiți persoane (Aura)? Sunt declanșate de pattern-uri în context (client local, recurent, suma mică)?

### 🆕 NEW INSIGHT — emoji client neglijat

**Cazul Mihailiuc (thread 19dd37dda80ef12b):**

Client foarte cald: `"Bună Ziua! / Mulțumesc pentru receptivitate 🤗 / o zi frumoasă în continuare!🌷 / Cu stimă"` — sentiment evident `entuziast`.

PAFF a răspuns cu template-ul `mc1` STANDARD, fără orice element de reciprocitate caldă. Niciun emoji, niciun "vă mulțumim și dvs.", niciun "o zi frumoasă". Pure template tranzacțional.

**Anti-pattern nou candidat:** `lipsa_reciprocitate_caldura` — când client semnal pozitiv (emoji, formule calde, mulțumiri repetate), PAFF răspunde sec template. Fals neutru = pierdere oportunitate retention.

**Counterfactual ideal:** "Bună ziua dl. Mihailiuc, vă mulțumim și pentru cuvintele calde 🌷. Pregătim coletul..."

## Hipoteze de testat la scale

Bazat pe aceste 6 mesaje umane (sample minimal), 3 hipoteze worth investigating la 5.000 mesaje:

| H | Hipoteză | Testare la scale |
|---|---|---|
| **H1** | "4-7 zile" e folosit literal în >70% din confirmările de plată, chiar când realitatea e 1-3 zile | Cross-reference data plată vs data AWB sent (V2 — necesită OCR sau header tracking AWB) |
| **H2** | Modificările ad-hoc benefice (gen Pursehuit) sunt < 10% din răspunsuri și concentrate la 1-2 persoane | Detect template_modified vs template_pure rate; correlate cu responder_persona |
| **H3** | Client cu sentiment `entuziast` (emoji, formule calde) primesc răspuns identic cu client `neutru` — zero adaptare ton | Cross-tab sentiment_client × tone_match_quality |

## Limitări sample

- **n=6 human messages** — descoperim pattern-uri, nu generalizăm încă
- **24h slice** — comportament dintr-o zi de marți ar putea diferi de luni dimineață sau vineri seara
- **Lipsă thread istoric** — răspunsul Aura citat în Lasatex thread vine din contextul precedent care nu e în batch

## Următorul pas decis

Decide tu:
- (a) Mărime mai mare same-week — pull restul celor 50+ mesaje + content
- (b) Sample stratified pe 12 luni — 1 săptămână per lună × 24 = ~24 sample-uri spread temporal
- (c) Direct full pull 24 luni — durează ~30-60 min cu MCP, ~5.000 mesaje
- (d) Stop fetching, build pipeline Python proper care face asta automat (durează scriere ~30 min, apoi rulează curat)

Recomand (b) sau (d):
- (b) — descoperim mai multe pattern-uri în diversitate temporală cu effort minim
- (d) — investiția în script se amortizează imediat (rerun la +6 luni gratuit)
