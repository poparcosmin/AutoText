# Classification Taxonomy

> **Versiune:** 0.9 (DRAFT — necesită refinement Cosmin înainte de Etapa 4)
> **Status:** ⚠️ TODOs marcate explicit. **Decizie one-way-door** — schimbări post-annotation invalidează ground truth.

Document defineste cele 5 dimensiuni de clasificare aplicate fiecărui mesaj în pipeline. Acuratețea finală depinde direct de cât de bine sunt definite categoriile aici.

---

## 1. Principii de design

1. **Mutually Exclusive, Collectively Exhaustive (MECE)** la nivelul `intent.primary` și `sentiment.label` — orice mesaj cade într-o singură categorie.
2. **Multi-label permis** la `intent.secondary` (ex: cerere ofertă + cerere tehnică).
3. **Examples concrete în RO** pentru fiecare categorie — un annotator care citește definiția trebuie să poată eticheta fără ambiguitate.
4. **Edge cases documentate** explicit — ce facem când un mesaj atinge mai multe categorii.
5. **Versionare** — orice schimbare post-Etapa 4 = nouă versiune `vX.Y` cu re-annotation pe sample.

---

## 2. Dimensiunea: `intent` (mesaje INBOUND, de la client)

### 2.1 Categorii primare (10) — DRAFT

> ⚠️ **TODO Cosmin** — pentru fiecare categorie, validează:
> - Numele se potrivește cu cum vorbiți voi în PAFF intern?
> - Lipsește vreo categorie observată în Iteration 1-5?
> - Sunt 2 categorii care se confundă mereu?

| Cod | Categorie | Definiție | Exemple RO observate (sau sintetice) | Frecvență așteptată (din Iteration 1) |
|---|---|---|---|---|
| `cerere_oferta` | Client cere preț/disponibilitate fără comandă fermă | "Ne puteți trimite o ofertă pentru cutii X cu Y dimensiuni?" | ~25% |
| `comanda_noua` | Client transmite comandă fermă (cantitate + acceptare preț) | "Confirmăm comanda din proformă, atașăm OP-ul." | ~20% |
| `urmarire_status` | Client întreabă unde e comanda / când vine livrarea | "Bună ziua, când plecă coletul cu numărul X?" | ~15% |
| `reclamatie_calitate` | Defect / produs neconform / lipsă | "Cutiile au sosit rupte / cu print greșit." | ~5% |
| `dispute_factura` | Cost diferit de așteptat / cerere clarificare factură | "Pe factură văd 313 lei în plus, ce reprezintă?" | ~3% |
| `cerere_urgenta` | Client menționează deadline strâns sau "urgent / azi / cât mai curând" | "Avem nevoie urgent până vineri pentru export." | ~5% |
| `cerere_preventiva` | Client cere atenție specială înainte de producție | "Vă rugăm să fie fără defecte ca data trecută." | ~2% |
| `feedback_pozitiv` | Mulțumire, recomandare, recenzie | "Mulțumim, ați livrat impecabil." | ~1% |
| `cerere_tehnica` | Întrebare specs (Pantone, dimensiuni, materiale, stante) | "Care e grosimea cartonului pentru E-flute?" | ~10% |
| `salutari_protocol` | Felicitări sărbători, schimb politețuri fără task | "Sărbători fericite, mulțumim de colaborare!" | ~2% |

**Catch-all:** `altceva` (max 5% admis — dacă depășește, taxonomy e incompletă)

**TODO Cosmin §2.1 — completează:**
- [ ] Confirmă cele 10 categorii sunt corecte (sau adaugă/elimini)
- [ ] Adaugă 2-3 exemple **reale** din Iteration 1-5 per categorie (după pseudonymization)
- [ ] Validează frecvențele așteptate vs ce ai observat manual

### 2.2 Multi-label `intent.secondary`

Se completează doar dacă mesajul atinge ≥2 categorii relevante. Exemplu:

```
"Bună ziua, putem comanda 100 cutii (vezi atașat) și am dori urgent până luni — care e prețul total cu transport?"

→ primary: comanda_noua
→ secondary: [cerere_oferta, cerere_urgenta]
```

### 2.3 Edge cases

| Situație | Decizie |
|---|---|
| Mesaj cu o singură propoziție "Bună ziua" | `salutari_protocol` (chiar dacă e introducere la thread) |
| Forward / Fwd: către PAFF | Folosește mesajul OBSERVAT, ignoră history forward-ed |
| Mesaj automat (Out of Office, no-reply) | Skip — `intent: null` cu `auto_generated: true` |
| Mesaj predominant în EN (Fortune 500 client) | Aceleași categorii; flag `language_quality: "en-ro-mix"` |
| Mesaj fără text (doar atașament) | `cerere_tehnica` cu `notes: "attachment-only"` |

---

## 3. Dimensiunea: `sentiment` (mesaje INBOUND)

### 3.1 Scale (5 valori, scală discretă)

| Cod | Label | Scale value | Definiție | Indicatori lexicali (RO) |
|---|---|---|---|---|
| `entuziast` | 🟢 | +1.0 | Mulțumire explicită, exclamații, recomandare | "extraordinar", "minunat", "vă recomand" |
| `politicos` | 🟢 | +0.5 | Formule de politețe complete, ton respectuos | "Bună ziua,", "vă mulțumesc", "cu stimă" |
| `neutru` | ⚪ | 0.0 | Tranzacțional, fără semnale emoționale | text scurt, fapte, fără adjective |
| `frustrat` | 🟡 | -0.5 | Nemulțumire fără agresiune, concise critic | "din nou", "iar", "deja a 3-a oară" |
| `agresiv` | 🔴 | -1.0 | Acuzații, ALL CAPS, amenințare ANPC/legal | "INACCEPTABIL", "voi face plângere", "ANPC" |

**TODO Cosmin §3.1 — completează:**
- [ ] Scale e ok cu 5 valori sau preferi 3 (negativ/neutru/pozitiv) pentru κ mai mare?
- [ ] Adaugă 2-3 indicatori lexicali RO observați real per categorie

### 3.2 Edge cases

| Situație | Decizie |
|---|---|
| Politețe formală + conținut frustrat ("Bună ziua, însă vă comunic că ne-am săturat de...") | `frustrat` (conținut > formă) |
| Sarcasm / ironie | Cea mai probabilă interpretare; flag `notes: "sarcasm_suspected"` |
| Mesaj scurt sec ("Trimite AWB.") | `neutru` (NU `frustrat` doar pentru că e scurt) |

---

## 4. Dimensiunea: `response_type` (mesaje OUTBOUND PAFF)

### 4.1 Tipuri (4)

| Cod | Definiție | Detection method |
|---|---|---|
| `template_pure` | Match >85% similarity cu un shortcut din `textsync_shortcut` (ChrF + embedding cosine) | Fuzzy match automat |
| `template_modified` | Match 60-85% — folosește un template ca bază dar adaugă/elimină paragrafe | Fuzzy match + diff |
| `ad_hoc` | Match <60% — răspuns scris liber pentru context specific | Fuzzy match negative |
| `hybrid` | 2+ template-uri concatenate (ex: confirmare plată + notă tehnică) | Multi-match detection |

### 4.2 `template_match` resolution

Algoritm:
1. Pentru fiecare shortcut active din `textsync_shortcut` (62 entries), calculează similarity vs body PAFF
2. Cele cu similarity ≥ 0.85 → `template_pure` cu `template_match.shortcut_id` setat
3. Cele cu similarity 0.60-0.85 → `template_modified`
4. Cele cu similarity < 0.60 → `ad_hoc`
5. Dacă două shortcut-uri DIFERITE au fiecare similarity ≥ 0.40 cu părți disjuncte → `hybrid`

---

## 5. Dimensiunea: `responder_persona` (mesaje OUTBOUND)

### 5.1 Personas (5 + 1 fallback)

| Cod | Identificare | Note |
|---|---|---|
| `aura` | Semnătură "Aura Chitulescu" sau patterns Iteration 3 | Front-office primary |
| `florentina` | Semnătură "Florentina Păun" | Recovery / reclamații |
| `bogdan` | Semnătură "Bogdan Popa" | Tehnic / decizii rapide |
| `florian` | Semnătură "Florian Popa" | Decident / escaladare |
| `generic` | Semnătură "Echipa PAFF" sau fără semnătură personală | Mesaje protocol |
| `unknown` | Nu se poate determina | Flag pentru manual review |

### 5.2 Detection

1. **Regex pe ultimele 10 linii** — căutare după nume + semnătură pattern
2. **Dacă regex eșuează** → fallback LLM judge: "Cine din [Aura/Florentina/Bogdan/Florian/Generic/Unknown] ai zice că a scris acest email?"

---

## 6. Dimensiunea: `quality_assessment` (perechi OUTBOUND ↔ INBOUND care îl precede)

### 6.1 Rubric (5 etichete + 4 sub-scoruri)

**Etichetă globală:**

| Cod | Definiție |
|---|---|
| `excellent` | Răspuns adresează toate punctele clientului + tonul potrivit + fără anti-pattern + ofera valoare suplimentară (recunoaștere recurent, transparență cost, etc.) |
| `good` | Toate punctele adresate, ton ok, fără anti-pattern grav |
| `acceptable` | Adresează clientul minimal, fără efort suplimentar, dar nu strică |
| `mismatch` | Template forțat care nu se potrivește contextului (ex: "Bună ziua, vă mulțumim pentru plată" dar clientul a întrebat doar de status) |
| `harmful` | Răspuns care produce daune business (cost retroactiv ascuns, refuz brusc politicos, lipsă scuze la reclamație clară) |

**Sub-scoruri** (1-5, completate de LLM judge cu rubric):

| Sub-scor | Definiție |
|---|---|
| `context_addressed` | Cât de bine răspunde la ÎNTREBĂRILE concrete ale clientului |
| `tone_match` | Cât de bine reciproca politețea / urgența / sentimentul clientului |
| `completeness` | Răspuns complet (nu necesită follow-up imediat din partea clientului) |
| `anti_pattern_count` | Număr de anti-pattern-uri Brand-Voice violations (count, nu scor — invers proportional cu calitate) |

### 6.2 Anti-patterns (din `Brand-Voice.md` v1)

Lista canonică verificată la scale:

| Cod | Pattern | Detection method |
|---|---|---|
| `salut_fara_diacritice` | "Buna ziua" / "Buna" | Regex literal |
| `salut_fara_virgula` | "Bună ziua\n" (fără virgulă) | Regex |
| `eta_47_zile_lazy` | "4-7 zile lucrătoare" copy-paste când livrare reală e 1-2 zile | Lookup + thread analysis |
| `cost_retroactiv` | Cost menționat doar pe factură, nu în proformă/confirmare | Cross-reference proformă vs factură (V2 — necesită OCR) |
| `brand_string_inconsistent` | "Fabrică de Ambalaje" / "Producator ambalaje" în loc de "Producător de Ambalaje" | Regex literal |
| `mode_telegrafic` | <30 cuvinte fără salut + fără semnătură | Length + structure detection |
| `tacere_la_cerere_preventiva` | Client a cerut "fără defecte" → PAFF nu acknowledge | Intent client = `cerere_preventiva` AND PAFF response NU conține "preluat / atenție / am notat" |
| `lipsa_recunoastere_recurent` | Client cu ≥3 comenzi în 12 luni primește template generic | Cross-reference cu thread history |

**TODO Cosmin §6.2 — completează:**
- [ ] Adaugă alte anti-pattern-uri pe care le observi în comunicare
- [ ] Pentru fiecare, validează detection method este implementabil

---

## 7. Versionare taxonomy

| Versiune | Data | Schimbări | Re-annotation necesară? |
|---|---|---|---|
| `0.9-DRAFT` | 2026-04-28 | Inițial | N/A |
| `1.0-RC` | post-Cosmin review | TODOs §2.1, §3.1, §6.2 rezolvate | NU (înainte de annotation) |
| `1.0-FROZEN` | post-200 annotations | Locked în pipeline | DA pentru orice schimbare |

**Regulă:** după `1.0-FROZEN` (când κ se calculează pe annotations) — orice schimbare la taxonomy = `2.0` cu re-annotation completă pe sample.

---

## 8. Referințe

- Brand-Voice anti-patterns sursă: `Obsidian://PAFF/Research/Email-Customer-Communication/Brand-Voice.md`
- Iteration 3 — Reclamații pattern (Florentina): `Obsidian://.../2026-04-26 - Iteration 3 - Reclamatii & Escalation Paths.md`
- Eval methodology — cum se folosește taxonomy în κ și F1: `./04-eval-methodology.md`
- Data schema — cum sunt persistate clasificările: `./01-data-schema.md`
