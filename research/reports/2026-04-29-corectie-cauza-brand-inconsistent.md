---
created: 2026-04-29
status: correction
supersedes_sections: ["3", "5.P0-A"]
parent_report: 2026-04-28-final-aggregate-25-months.md
window: 2024-04 → 2026-04 (25 luni, 37862 outbound)
---

# Corecție — Cauza reală a regresiei `brand_string_inconsistent`

## TL;DR

Raportul anterior (2026-04-28) atribuia greșit cauza regresiei `+34.1pp` la cele 23 shortcut-uri din DB. **Verificare empirică post-publicare**: regex-ul `brand_string_inconsistent` nu se declanșează pe niciun shortcut din cele 23. Sursa reală e **semnătura Gmail (footer)** repetată în 37 variante distincte și 37k+ ocurențe.

**Impact pentru plan:** P0-A (fix shortcut-uri) **NU REZOLVĂ** regression-ul. P1-D (Gmail signatures) urcă la **P0** și devine acțiunea cu impact maxim.

---

## 1. Verificare empirică

### 1.1 Test direct pe DB shortcut-uri

```python
# regex-ul anti_patterns.py liniile 106-113
brand_re = r"PAFF\s*[:·\-]+"  # PAFF urmat de :, ·, sau - (NOT |)
wrong_variants = [
    r"Fabric[ăa]\s+(de\s+)?Ambalaje",
    r"Producator\s+ambalaje",
    r"Producător\s+Ambalaje\b",  # fără "de"
    r"Producator\s+de\s+Ambalaje",
]
```

**Rezultat run pe cele 23 shortcut-uri din `textsync_shortcut`:**
- 0/23 trigger-uiesc `brand_string_inconsistent`
- Cel mai apropiat candidat: shortcut `ep` (id 80) `"PAFF | Producător Ambalaje"` — separator `|` NU e în set-ul `[:·-]`, deci nu match

### 1.2 Test pe corpus enriched (37862 outbound)

```python
# scan toate mesajele care AU declanșat brand_string_inconsistent
# extrage signature block (3 linii context)
```

**Rezultat:** 37 variante distincte de signature block. Top 3 acoperă **>90%** din cazuri:

| Variantă | Ocurențe | Forma greșită detectată |
|---|---:|---|
| `*PAFF :: Producător ambalaje* 072.169.7233 - 074.466.7233` | 24.082 | `Fabrică de Ambalaje` din quoted reply |
| `*PAFF :: Producător ambalaje* RO4807535 · J15/1583/1993 ...` | 7.761 | `Producator ambalaje` (fără diacritică) |
| `*PAFF :: Producător Ambalaje* 072.169.7233 \| 074.466.7233` | 5.448 | `Producător Ambalaje` (lipsește "de") |

**Sursa:** semnătura Gmail per cont (multi-sender). Setare în `Gmail Settings → Signatures`.

### 1.3 Forma "canonică" e fictivă

```sql
-- Câte mesaje în 25 luni folosesc forma canonică din raportul inițial?
COUNT(messages WHERE body LIKE '%Producător de Ambalaje%') = 0
```

**Forma `Producător de Ambalaje` (cu "de") apare în 0/66052 mesaje.** Era o formă inventată în detector — toată lumea folosește `Producător ambalaje` sau `Producător Ambalaje`.

---

## 2. Cauza reală — temporal cliff

### 2.1 Evoluția per fereastră

```
brand_string_inconsistent absolute count + rate
window      outbound  brand  rate
2024-04         1732    528  30.5%
...           (stabil 27-31% pe 18 luni)
2025-09         1572    434  27.6%
2025-10         1477    430  29.1%  ← ultima lună normală
2025-11         1762    711  40.4%  ← +12.8pp (jump 1)
2025-12         1114    854  76.7%  ← +36.3pp (jump 2 — discontinuitate)
2026-01         1368   1082  79.1%
2026-04         1121    865  77.2%
```

**Două salturi temporale:**
1. **Noiembrie 2025**: +12.8pp — adopție AutoText începe (template usage 0.6% → 15.6%)
2. **Decembrie 2025**: +36.3pp — discontinuitate bruscă cu 50pp peste baseline

Decembrie 2025 = ceva s-a schimbat în signature settings — un cont Gmail a primit semnătură nouă, sau un format de signature s-a modificat.

### 2.2 De ce AutoText înrăutățește

AutoText scoate quoting-ul din mesaje (template-uri sunt ne-quoted). Dar signature-ul Gmail rămâne mereu jos. Deci:

**Pre-AutoText:** mesaje lungi cu quoted history → signature apare o dată → 1 trigger
**Post-AutoText:** mesaje scurte (template only) → signature reprezintă procent mai mare din body → trigger garantat

**Plus:** template-urile noi din AutoText rulate pe mesaje cu quote-uri vechi pot conține `Fabrica de Ambalaje` sau `Producător Ambalaje` din thread anterior, ceea ce trigger-uiește detector-ul în combinație cu signature-ul.

---

## 3. Plan corectat de remediere

### 3.1 P0-A REVIZUIT — Standardizare Gmail signatures

**Effort:** 30-60 min (config Gmail Settings × N personae)
**Impact estimat:** -50pp pe `brand_string_inconsistent` (de la 77% la ~25-30% baseline pre-2025-11)

**Acțiuni concrete:**

1. **Identifică toate conturile Gmail** care trimit prin `contact@paff.ro`:
   - contact@paff.ro
   - aura@paff.ro (sau identitate alternativă)
   - florentina@paff.ro
   - bogdan@paff.ro
   - florian@paff.ro
   - irina@paff.ro
   - + alte send-as configurate

2. **Decide forma canonică** (alegere business, nu tehnică):
   - **Opțiune A** [Status quo lexical]: `*PAFF :: Producător ambalaje*` — forma cu cea mai mare prezență (24k ocurențe). **PRO**: zero change management. **CONTRA**: lipsește diacritica + lipsește "de".
   - **Opțiune B** [Corectă lingvistic]: `*PAFF :: Producător de Ambalaje*` — forma cu diacritică completă + cu "de". **PRO**: corectă. **CONTRA**: 0 ocurențe în corpus → schimbare vizibilă pentru clienți (poate un client întreabă "v-ați schimbat numele?")
   - **Opțiune C** [Minimalist]: `*PAFF*` — fără descriptor. **PRO**: imposibil de greșit. **CONTRA**: pierzi context "ce facem".

3. **Setare uniformă în Gmail Settings → See all settings → General → Signature** pe TOATE conturile

4. **Verifică în 2 săptămâni** — re-run `anti_patterns.py` pe windows 2026-05/2026-06

### 3.2 P0-B (neschimbat) — Update `mc1` template ETA

ETA `4-7 zile` hardcodat în template-uri rămâne problemă. Acțiunea recomandată în raportul anterior e validă.

### 3.3 P1 NOU — Refactor anti_patterns.py detector

Detectorul actual e fals-pozitiv în masă (37k trigger-uri legitime sunt etichetate ca "wrong"). Două căi:

- **A** [Refactor]: detectează doar inconsistency reală (mai mulți senderi cu variante diferite ale aceluiași string brand). Necesită stocare cross-thread + comparație.
- **B** [Replace]: scoate `brand_string_inconsistent` din lista anti-patterns și înlocuiește cu metric utilă: `signature_drift` (variantă diferită față de canonical setat).

**Recomandare**: B — implementarea e simplă (1-2h) și produce semnal acționabil.

### 3.4 P1 (neschimbat) — Activare RO Programmer's keyboard

Pentru `salut_fara_diacritice` (56.8% post-AutoText, plafon greu).

---

## 4. Cifre corectate (care rămân valabile din raportul inițial)

Aceste cifre **nu sunt afectate** de corecție:

| Anti-pattern | Pre-AT | Post-AT | Δ |
|---|---|---|---|
| `salut_fara_diacritice` | 63.4% | 56.8% | -6.6pp ✅ |
| `salut_fara_virgula` | 34.0% | 27.6% | -6.4pp ✅ |
| `eta_47_zile_template` | 31.5% | 32.9% | +1.4pp ⚠️ |
| `lipsa_diacritice_partial` | 9.6% | 9.1% | -0.5pp |
| `mode_telegrafic` | 2.0% | 3.6% | +1.6pp |
| `salut_cu_spatiu_punct` | 11.8% | 15.1% | +3.3pp |
| `brand_string_inconsistent` | 29.6% | 63.7% | +34.1pp 🔴 (cauza CORECTATĂ) |

**Adopția AutoText** (template usage 0.6% → 54.6% în 7 luni) și **îmbunătățirea diacriticelor** sunt confirmate independent.

---

## 5. Lecție meta — verificare empirică

**Ce am greșit:** am concluzionat „shortcut-urile sunt cauza" pe baza unei extracții de cod (regex-ul detector) fără să rulez o probă pe shortcut-uri sau pe corpus enriched. Output-ul JSON `_anti_patterns_summary.json` nu identifica sursa per text — doar număra trigger-uri.

**Ce trebuie făcut:** orice raport care atribuie cauză la **Y** trebuie să producă o probă concretă: "Y trigger-uiește pattern X în Z mesaje, exemplu: ..."

**Persistă în memorie?** Nu — e o lecție specifică pentru research în AutoText, nu un comportament global. Adaug în loc o linie la `research/docs/00-charter.md` despre cerința de verificare empirică pe finding-uri.

---

## 6. Cauză root EXACTĂ — Gmail Account Display Name

Refactor detector `brand_signature_drift` (commit ulterior) detectează doar 3.728 cazuri (vs 14.548 false-pozitive vechi) și revelează un **discontinuity exact**:

```
brand_signature_drift rate per fereastră:
2024-04 → 2025-06: 0.0% (stabil 15 luni!)
2025-07: 11.3% (răsărit brusc — 175 mesaje)
2025-08: 30.2% (plateau atins)
2025-09 → 2026-04: 27-30% (stabil)
```

**Inspecția signature blocks afectate** arată un singur pattern dominant:

```
*From:* PAFF :: Producator ambalaje <contact@paff.ro>
În X iul. 2025 la HH:MM, PAFF :: Producator ambalaje <contact@paff.ro> a scris:
On Mon, Jul 21, 2025 at HH:MM PAFF :: Producator ambalaje <contact@paff.ro> wrote:
```

**Sursa:** Header `From:` propagat în quoted reply chains. NU e signature din body — e **Display Name al contului Gmail `contact@paff.ro`**.

**Fix exact:**

1. Login `contact@paff.ro` în Gmail
2. Settings → See all settings → **Accounts and Import**
3. Section "Send mail as", la `contact@paff.ro` → click **Edit info**
4. Change "Name" field din `PAFF :: Producator ambalaje` în `PAFF :: Producător ambalaje`
   (sau în forma decisă de business — A, B sau C din §3.1)
5. Save

**Timp execuție:** 30 secunde. **Impact:** 0% drift pe mesajele noi. Cele istorice rămân așa — apar în quoted chains când clienții răspund la thread-uri vechi (atenuat în timp).

**Verificare retroactivă:** între 2025-06 și 2025-07 cineva a editat conștient sau accidental câmpul Name. Probabil când a apărut un nou laptop/Gmail relogin, au tastat fără diacritică și nu și-au dat seama.

---

## 7. Status

- [x] Verificare empirică shortcut-uri (0/23 trigger pattern)
- [x] Fingerprint signature blocks (37 variante distincte)
- [x] Confirmare cifre per fereastră (re-run anti_patterns pe TOATE 25 windows)
- [x] Refactor `anti_patterns.py` — pattern nou `brand_signature_drift`
- [x] **Cauză root identificată: Gmail Display Name al `contact@paff.ro`, schimbat iulie 2025**
- [ ] Fix Display Name în Gmail Settings (30 sec)
- [ ] Decision business: forma canonică Display Name (A=`Producător ambalaje`, B=`Producător de Ambalaje`, C=`PAFF`)
- [ ] Re-run + comparație peste 2-4 săptămâni post-fix
