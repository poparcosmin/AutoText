---
created: 2026-04-29
status: actionable_v2
window: 2024-04 → 2026-04 (25 luni)
total_threads_clean: 19900 (3169 spam mutate)
focus: cresterea ratei de conversie comenzi
supersedes: 2026-04-29-crestere-comenzi-recomandari.md
trigger_corecție: feedback user — răspunsurile scurte sunt în mare parte refuzuri sau confirmări plată, NU eșec de comunicare
---

# Recomandări v2 — analiza onestă a oportunităților de creștere comenzi

## TL;DR

Raportul v1 supraevalua **P0-A** (extinde shortcut scurt). Pe verificare empirică, 720 threads "single-round price_quote" se descompun:

| Tip | # | % | Interpretare |
|---|---:|---:|---|
| A. Confirmare plată | 62 | 8.6% | **deja convertit** (post-payment) |
| B. Refuz PAFF | 114 | 15.8% | **drop-off corect** (PAFF nu produce) |
| C. Confirmare livrare | 1 | 0.1% | post-AWB |
| D. Link scurt la produs | **79** | 11.0% | **oportunitate reală** |
| E. Răspuns scurt generic | 285 | 39.6% | mixt: facturi, avize, follow-up trimis |
| F. Răspuns lung single-round | 179 | 24.9% | clientul a primit info completă, n-a mai răspuns |

**Adevărata oportunitate de "comunicare mai bună"** = ~79 threads pe 25 luni = **~3/lună**. Impact real **mic** (1-2 comenzi/lună suplimentare).

**Oportunitate mai mare ascunsă în date:**
- **273 cereri REFUZATE** (~11/lună) — produse adiacente la portofoliul actual
- **6.462 mesaje fără răspuns** (~258/lună) — necesită triage manual

---

## 1. Ce am verificat și ce am corectat

### Ce credeam (v1):
> "Răspunsurile scurte cu link la produs nu vând. Extinde shortcut-ul de la 55 la 100 cuvinte cu plan acțiune. Impact: +38 comenzi/lună."

### Ce e real (după re-clasificare):
- 86% din răspunsurile scurte sunt corecte pentru contextul lor: refuzuri, confirmări plată, livrări trimise.
- Doar 11% (79 threads) sunt răspunsuri scurte cu link unde clientul tace = oportunitate de îmbunătățire.
- Impact realist: dacă recuperăm 30% din cei 79 cu CTA mai bun = ~24 comenzi în 25 luni = **~1 comandă/lună**.

### Sample concret D_LINK_SCURT
```
CLIENT: "Doresc oferta pentru 100 cutii 16Lx12lx35h.
         Totodata, oferta separata pentru 300 cutii..."

PAFF: "Va putem oferi :
       https://www.paff.ro/cutie-...165x120x375.../...
       https://www.paff.ro/cutie-...300x245x365.../..."

CLIENT: [tace]
```

PAFF a dat exact ce ceream — link la produs + preț. De ce taca clientul?
- Posibilitatea 1: a comandat direct pe site (zero email), dar nu am cum să verific fără tabela de comenzi
- Posibilitatea 2: prețul nu i-a convenit, s-a dus la concurență
- Posibilitatea 3: lipsa unui call-to-action explicit ("plătește pe site" sau "răspunde aici dacă vrei să procedăm")

---

## 2. Acțiuni revizuite

### P0-A — REVIZUIT (impact mic) — Adaugă CTA în răspunsurile cu link

**Diagnostic:** ~79 threads / 25 luni unde PAFF răspunde cu link la produs, fără call-to-action explicit.

**Acțiune:** când răspunzi cu link, adaugă o singură linie la final:
> "Pentru a finaliza comanda, plasați-o direct pe site sau răspundeți la acest email cu cantitatea finală — vă trimitem proforma."

**Effort:** 30 min (modificare shortcut existent).
**Impact realist:** +1-2 comenzi/lună (nu +38 cum spuneam).

### P0-B — Validat (impact mediu) — Triage zilnic mesaje fără răspuns

**Diagnostic:** 6.462 mesaje într-un singur mesaj inbound, fără răspuns PAFF (~258/lună). Pe sample manual, **~15-25% par a fi clienți reali** care n-au primit răspuns.

**Acțiune:** zilnic 5-10 minute, parcurge inbox-ul de ieri. Spam-ul e deja filtrat de Gmail labels (vezi P1-A).

**Effort:** 5-10 min/zi.
**Impact realist:** dacă 20% din 258 sunt clienți reali = 52 lead-uri/lună. Dacă 30% se transformă în comandă = **~15 comenzi/lună suplimentare**.

### P0-C — Validat (impact mare) — SLA <30 min cu auto-acknowledgement

**Diagnostic:** mediană FRT = 6 min (excelent), dar p90 = 7 ore (10% clienți așteaptă mult). Conversion drop la 35% când răspuns >5 min vs 47% sub 5 min.

**Acțiune:** auto-reply Gmail "Am primit cererea, revin în max 30 min" pentru toate mesajele cu subject conținând "ofert", "pret", "cere", când răspunsul real întârzie.

**Effort:** 30 min Gmail filters + canned response.
**Impact realist:** elimină tail-ul de 7+ ore. Estimare conservatoare: **+5-15 comenzi/lună** (depinde de câți din p90 ar fi convertit cu răspuns mai rapid).

### P1-NEW — Analiza cererilor REFUZATE (oportunitate ascunsă)

**Diagnostic:** 273 cereri refuzate de PAFF în 25 luni (~11/lună). Refuzuri tipice:
- "Nu producem etichete" (multiple cazuri)
- "Nu personalizăm pungi"
- "Nu plastifiem cartonul"
- "Dimensiuni prea mari pentru utilaje"
- "Nu producem cilindri din carton" (doar muchii drepte)
- "Nu lucrăm cu carton colorat"
- "Nu facem serigrafie"

**Acțiune (3 căi):**
1. **Identifică top 3 produse adiacente cele mai cerute** (ex: etichete, pungi personalizate). Estimare investiție pentru a le adăuga la portofoliu.
2. **Listă de parteneri** pentru recomandare (ex: PAFF nu face etichete, dar X face → recomandă cu reducere reciprocă, primesti o referal fee sau buy-back relationship).
3. **Răspuns mai informativ la "nu"**: în loc de "nu producem etichete", spune "nu producem etichete dar avem alternativa Y, sau te recomandăm la X care e specializat".

**Effort:** 4-6h analiză + 1-2 zile decizie business.
**Impact realist:** dacă recuperezi 30% din refuzati prin partner referral fee = **~3 comenzi indirecte/lună** + îmbunătățire reputație "PAFF te ajută chiar și când nu poate produce".

### P1-A — Setup Gmail filters newsletter (igienă inbox)

Setup automat: arhivare-uri pentru domenii cunoscute (mailchimp, sendgrid, FAN courier, ANAF, banci). Listă în `research/pipelines/clean/quarantine_spam.py`.

**Effort:** 30 min one-time.
**Impact:** triage P0-B devine 5 min/zi în loc de 30 min/zi.

---

## 3. Estimare impact total v2 (onest)

| Acțiune | Comenzi/lună (real) | Effort |
|---|---:|---|
| P0-A (CTA în link reply) | +1-2 | 30 min |
| P0-B (triage zilnic) | +15 | 5-10 min/zi |
| P0-C (SLA <30 min + auto-reply) | +5-15 | 30 min once |
| P1-NEW (refuzati → partner referral) | +3 | 4-6h analiză |
| **Total v2** | **+24-35 comenzi/lună** | **~10h once + 5-10 min/zi** |

La AOV B2B 800 RON: **+19-28k RON/lună**, NU 115k cum spuneam în v1.

⚠️ **Cifrele rămân estimări**. Validare reală cere:
- Tabelă comenzi (ca să măsor conversion exact post vs pre)
- A/B test 4-6 săptămâni
- Tracking website (ca să separ comenzi-direct-pe-site de comenzi-via-email)

---

## 4. Lecție meta — interpretare cu user în buclă

V1 al raportului avea concluzii bombastice:
> "+140-150 comenzi/lună, ~115k RON/lună revenue suplimentar"

User-ul, care **cunoaște operationalul**, a corectat: răspunsurile scurte sunt în mare parte rejecții corecte sau confirmări plată. **Datele susțineau v1, dar contextul a invalidat interpretarea.**

Lecție pentru viitor: **nu trag concluzii operaționale fără context business**. Pattern lexical poate fi simptom al unei alte cauze. Verificarea cu cineva care vede thread-urile zilnic e ireductibilă.

---

## 5. Status

- [x] Recategorizare 720 threads single-round price_quote (62 plată / 114 refuz / 79 link / 285 generic / 179 lung / 1 livrare)
- [x] Analiza 273 threads refuzate (oportunitate produse adiacente)
- [x] Estimare onestă impact (24-35 comenzi/lună vs 140-150 v1)
- [ ] Decizie user: care P0 începem prima dată
- [ ] (Opțional) Audit produs adiacente cele mai cerute pentru P1-NEW
