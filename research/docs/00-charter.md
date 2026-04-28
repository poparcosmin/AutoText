# Charter — PAFF Email Communication Research

> **Versiune:** 1.0
> **Data start:** 2026-04-28
> **Owner:** Popa Cosmin (`poparcosmin@gmail.com`)
> **Status:** ACTIVE — Etapa 1 (Fundație)

---

## 1. Problema de business

Cele 62 răspunsuri predefinite din AutoText (`textsync_shortcut`) servesc echipa PAFF la `contact@paff.ro` (~30 emailuri/zi). Există dovezi calitative (Iteration 1-5 în Obsidian) că:

- Stilul răspunsurilor PAFF este **structural defensiv prin template** (nu se adaptează la context client / sentiment / segment).
- Calitatea răspunsului depinde de **persoana fizică** care îl trimite (Aura/Florentina/Bogdan/Florian), nu de un standard articulat.
- Anti-pattern-urile (ex. cost retroactiv, "4-7 zile" copy-paste, brand string inconsistent) sunt prezente în cele 62 shortcut-uri actuale.

**Cercetarea Iteration 1-5** a identificat aceste pattern-uri pe ~265 mesaje, 13 thread-uri, 12 luni — bază calitativă, dar fără validare statistică.

## 2. Întrebarea de cercetare

> **Pentru fiecare context primit de la client (intent + sentiment + segment), care este răspunsul predefinit cel mai potrivit, și unde diverge realitatea curentă PAFF de acel ideal?**

Sub-întrebări:
1. Care sunt categoriile de intent client distincte și cu ce frecvență apar?
2. Care răspunsuri PAFF sunt "mismatch" pentru contextul în care sunt folosite?
3. Care anti-pattern-uri se manifestă la scală statistic semnificativă?
4. Care segmente de clienți (1-shot / ocazional / recurent / strategic) primesc comunicare sub-optimă?
5. Cum a evoluat în timp (24 luni) calitatea comunicării — îmbunătățire sau regres?

## 3. Scope

### 3.1 In scope

- **Sursă:** contul Gmail `contact@paff.ro` (gpaff Workspace, acces via `mcp__workspace-mcp__*`)
- **Perioadă:** **2024-04-28 → 2026-04-28** (24 luni)
- **Direcție:** thread-uri complete (inbound client + outbound PAFF) — analiza pe perechi context↔răspuns, nu doar outbound
- **Volume estimat:** ~22.000 mesaje outbound + ~8.000 inbound = **~30.000 mesaje, ~3.500 thread-uri**
- **Outputs:**
  - Dataset enriched (clasificat) versionat în `research/corpus/enriched/`
  - Ground truth set (200 etichetări manuale + 50 ideal responses)
  - Raport de findings (`reports/`) reproducibil
  - Recomandări operationalizate → `operationalize/` (migration plan pentru SQLite shortcuts + Brand-Voice v2)
  - Dashboards Streamlit pentru echipă

### 3.2 Out of scope (explicit)

| Out | De ce |
|---|---|
| Conturi Gmail diferite de `contact@paff.ro` | Scope V1; extensie posibilă în V2 (`comenzi@`, `productie@`) |
| Mesaje automate de la WooCommerce / Magento (`Comanda noua pe site`) | Notificări sistem, nu intervenție umană |
| Thread-uri PAFF↔furnizori (outbound către furnizori) | Subiect separat; doar Maxoll a apărut incidental în Iteration 4 |
| Atașamente (PDF facturi, AWB, imagini) — **conținut** | Doar metadata (nume + dim) capturată; OCR pe atașamente = V3 |
| Modificări UX la extensia Chrome | Decizie operațională separată după ce avem findings |
| Schimbări în personalul PAFF (HR signals) | Etic out of scope |
| Predicție / generare automată răspunsuri (LLM-as-agent în production) | Etic + UX risk; cercetare informează template-uri umane, nu autoresponder |

## 4. Success criteria (măsurabile)

| # | Criteriu | Target | Metoda măsurare |
|---|---|---|---|
| **SC1** | Acoperire corpus ingerat | ≥95% din thread-urile din 24 luni capturate | Comparație count Gmail search vs corpus local |
| **SC2** | Pseudonymization completeness | 0 PII detectabil în corpus pseudonymized (sample 200 manual) | Audit manual + regex final scan |
| **SC3** | Taxonomy clarity | Cohen's kappa ≥ 0.7 inter-annotator pe intent | Eval methodology §3 |
| **SC4** | Classifier quality (intent) | F1 ≥ 0.85 pe golden set | `eval/run_eval.sh` |
| **SC5** | Findings actionability | ≥10 recomandări specifice cu evidence cantitativă (frequency × impact) | Review manual |
| **SC6** | Operationalization | Migration plan executable în <2h pe AutoText production | Dry-run + Plan Reviewer agent |
| **SC7** | Reproducibility | Pipeline rulează end-to-end fără intervenție pe un corpus nou | Re-run la +6 luni cu zero modificări code |
| **SC8** | Cost containment | Total LLM cost = **$0** (Gemini CLI cu abonament, nu API). Singurul cost monitorizat: timp pasiv. | `audit.log` (per request: model + tokens + duration) |

## 5. Decision log (Etapa 1 — confirmat 2026-04-28)

| Decizie | Opțiune aleasă | Justificare |
|---|---|---|
| **PII strategy** | A — Pseudonymization completă pre-LLM | GDPR Art. 32 (privacy by design); zero PII trimis către provider extern |
| **LLM provider** | A — **Gemini CLI** (`/home/cosmin/.local/bin/gemini` v0.39.1) cu autentificare prin **abonament** (NU API key, NU `mcp__llm-bridge__` API call-uri) | Zero cost incremental (abonament deja plătit), respectă regula globală "INTERZIS apeluri directe la API-uri AI fără aprobare". Constrângere: rate limits CLI (probabil ~60 req/min) → batch processing cu retry/backoff în pipeline |
| **Repo strategy** | B — `research/` în AutoText (nu repo separat) | Co-locare cu code-ul care consumă recomandările (textsync shortcuts); friction zero |
| **Scope inboxuri** | `contact@paff.ro` only (V1) | Volume deja substanțial; extensie posibilă în V2 după ce validăm pipeline |
| **Perioadă** | 24 luni (2024-04-28 → 2026-04-28) | Sweet spot temporal: detectează evoluție fără noise vechi (>24m introduce comportament outdated al firmei) |

## 6. Stakeholders

| Rol | Persoană | Implicare |
|---|---|---|
| **Owner / decident** | Popa Cosmin | Charter approval, taxonomy refinement, ground-truth annotation, decision gates |
| **Subiecți cercetare** | Aura Chitulescu, Florentina Păun, Bogdan Popa, Florian Popa | Anonymized în output; dacă findings sunt prezentate echipei → revizuire pe sensibilitate |
| **Beneficiari** | Echipa front-office PAFF (Aura primary) | Va folosi shortcut-urile actualizate post-research |
| **Data Processor** | Anthropic (Claude), Google (Gemini), Google Workspace (Gmail) | Acoperit prin DPA-urile standard ale platformelor |

## 7. Timeline (estimat 12 zile calendar, ~12-15h Cosmin)

| Etapă | Zile calendar | Cosmin (h) | Output |
|---|---|---|---|
| **1. Fundație** | 1 | 3h | Charter, schema, taxonomy skelet, privacy, eval |
| **2. Ingestion** | 2-3 | 1h (sup.) | ~30k mesaje în `corpus/raw/` + `corpus/pseudonymized/` |
| **3. Enrichment** | 4-7 | 2h (sup.) | `corpus/enriched/` cu 5 dimensiuni clasificate |
| **4. Ground truth + eval** | 4-8 paralel | 6h | 200 etichetări + 50 ideal responses + κ + F1 |
| **5. Analysis** | 8-10 | 1h | Reports per agent (5 agenți paraleli) |
| **6. Synthesis** | 11 | 1h | Raport canonic + Brand-Voice v2 + migration plan |
| **7. Validation + handoff** | 12 | 1h | `/plan-critique`, `/dual-llm`, dashboard |

## 8. Riscuri principale + mitigare

(detaliat în `03-privacy-model.md` §threat model și `04-eval-methodology.md` §validation)

| Risc | P × I | Mitigare |
|---|---|---|
| GDPR exposure (PII la LLM provider) | M × Mare | Decision A pe PII; pseudonymization mandatorie pre-LLM; audit log per request |
| Rate limit Gemini CLI (abonament) | M × Mic | Throttle conservator (~30 req/min); checkpointing per batch; retry exponential; rerun-able |
| Gemini CLI version drift (auto-update) | Mică × Mediu | `gemini --version` snapshot în `audit.log`; classifier_version reflectă CLI version |
| Taxonomy ambiguă (κ < 0.5) | M × Mare | Etapa 4 obligatorie înainte de Etapa 5; rework permis |
| Findings invalide statistic | Mică × Mare | Stratified sample; min n=30 per category pentru claim-uri |
| Bias confirmation | M × Mediu | Etapa 5.B fără seed prior; mismatch detector descoperă pattern-uri necunoscute |
| Corpus stale | Sigur × Mic | `/schedule` re-run la +6 luni |
| Gmail API throttle | Mică × Mic | 250 req/min; backup `.mbox` export |

## 9. Out-of-scope dar de monitorizat (parking lot)

- **V2 (~Q3 2026):** Extensie la `comenzi@paff.ro`, `productie@paff.ro`
- **V3 (~Q4 2026):** OCR atașamente (PDF facturi pentru cross-validation cost vs proformă)
- **V4 (~2027):** Knowledge graph cu pgvector pentru "client similar with X" lookup la compunerea unui email nou

## 10. Referințe

- Iteration 1-5 (calitativ): `Obsidian://PAFF/Research/Email-Customer-Communication/`
- Brand-Voice v1: `Obsidian://.../Brand-Voice.md`
- AutoText shortcuts curente: `db.sqlite3` tabel `textsync_shortcut` (62 entries)
- Privacy model: `./03-privacy-model.md`
- Eval methodology: `./04-eval-methodology.md`
- Data schema: `./01-data-schema.md`
- Taxonomy: `./02-classification-taxonomy.md`

---

*Charter aprobat la: __________ (Cosmin signature)*
*Revizuire programată: post-Etapa 7 (zi 12)*
