# PAFF Email Communication Research

> **Hub navigare** pentru research-ul sistematic asupra comunicării `contact@paff.ro` (24 luni, ~30k mesaje).
>
> **Status:** Etapa 1 (Fundație) — `feat/email-research-foundation` branch
> **Owner:** Popa Cosmin
> **Start:** 2026-04-28

---

## TL;DR

Research enterprise-grade pe perechi `(context client → răspuns PAFF)` pe 24 luni de email. Output: dataset versionat, ground-truth set, recomandări actionate direct în SQLite shortcuts (`textsync_shortcut`).

**Diferență vs Iteration 1-5 din Obsidian:** acolo a fost analiză calitativă pe 13 thread-uri. Aici procesăm sistematic ~30.000 mesaje cu clasificare automată + ground truth statistic.

---

## Citește ÎNAINTE de a rula orice script

| Document | De ce |
|---|---|
| **[00-charter.md](docs/00-charter.md)** | Scope, success criteria, decision log (PII=A, LLM=A, Repo=B), timeline 12 zile |
| **[01-data-schema.md](docs/01-data-schema.md)** | JSON Schema canonic pentru Message, Thread, Classification, Annotation |
| **[02-classification-taxonomy.md](docs/02-classification-taxonomy.md)** | ⚠️ Conține TODO-uri pentru Cosmin — refinement OBLIGATORIU înainte de Etapa 4 |
| **[03-privacy-model.md](docs/03-privacy-model.md)** | GDPR posture, pseudonymization rules, threat model, retention |
| **[04-eval-methodology.md](docs/04-eval-methodology.md)** | Cohen's kappa, F1 targets, golden set, statistical validity |

---

## Folder layout

```
research/
├── README.md                    ← acest fișier
├── docs/                        ← documente fundație (versioned)
│   ├── 00-charter.md
│   ├── 01-data-schema.md
│   ├── 02-classification-taxonomy.md
│   ├── 03-privacy-model.md
│   └── 04-eval-methodology.md
│
├── pipelines/                   ← Python scripts (uv) — versioned
│   ├── ingest/                  ← Etapa 2: Gmail → JSON
│   ├── enrich/                  ← Etapa 3: classification via Gemini CLI
│   ├── analyze/                 ← Etapa 5: pattern mining
│   └── report/                  ← Etapa 6: synthesis output
│
├── corpus/                      ← GITIGNORED + chmod 700 (PII)
│   ├── raw/                     ← Gmail dumps cu PII (plain JSON)
│   ├── pseudonymized/           ← PII-stripped working set
│   ├── enriched/                ← + classifications
│   └── pii_mapping/             ← token table (plain JSON, chmod 600)
│
├── ground-truth/                ← versioned (anonymous)
│   ├── annotations-v1.jsonl     ← 200 manual labels
│   └── ideal-responses-v1.jsonl ← 50 ideal pairs
│
├── eval/                        ← versioned
│   ├── run_eval.sh
│   ├── classifier_metrics.py
│   └── results/                 ← gitignored timestamped outputs
│
├── notebooks/                   ← Jupyter — versioned
│   └── *.ipynb
│
├── reports/                     ← Markdown + HTML — versioned
│   └── 2026-XX-XX-*.md
│
├── operationalize/              ← versioned (handoff to AutoText)
│   ├── shortcut-migration-plan.md
│   ├── new-shortcuts-spec.json
│   └── brand-voice-v2.md
│
└── scripts/                     ← versioned utilities
    └── pre-commit-corpus-guard.sh
```

---

## Etape proiect (overview)

```
Etapa 1: Fundație            [▓▓▓▓░░░] în curs (acest commit)
Etapa 2: Ingestion           [░░░░░░░] 24 batch-uri Gmail → corpus/raw/ → pseudonymized/
Etapa 3: Enrichment          [░░░░░░░] Gemini CLI batch classification
Etapa 4: Ground truth + eval [░░░░░░░] 200 etichetări manual + κ + F1
Etapa 5: Analysis paralel    [░░░░░░░] 5 agenți Claude simultan
Etapa 6: Synthesis           [░░░░░░░] Raport canonic + Brand-Voice v2 + migration plan
Etapa 7: Validation          [░░░░░░░] /plan-critique, /dual-llm, dashboard Streamlit
```

**Detalii fiecare etapă în [00-charter.md §7](docs/00-charter.md#7-timeline).**

---

## Quick start (când Etapa 1 e aprobată)

```bash
# 0. Verifică prerequisites
gemini --version       # ≥ 0.39.1
uv --version           # pentru Python deps

# 1. Install Python deps (Etapa 2)
cd /home/cosmin/Work/AutoText
uv add --dev spacy pandas pydantic tenacity httpx ruff jupyter streamlit
uv run python -m spacy download ro_core_news_lg

# 2. Pre-commit hook deja instalat în .git/hooks/pre-commit (Etapa 1)
#    Pentru clone-uri viitoare: cp research/scripts/pre-commit-corpus-guard.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

# 3. File permissions pentru corpus (după primul run ingestion)
chmod 700 research/corpus/

# 4. Rulează ingestion (Etapa 2)
uv run python research/pipelines/ingest/01_fetch_gmail_window.py --month 2024-04
# repetă pentru fiecare lună 2024-04 → 2026-04
```

---

## Cross-references — Iteration 1-5 (Obsidian)

Iteration-urile anterioare rămân autoritative pentru contextul calitativ:

| Document Obsidian | Folosit în research aici pentru |
|---|---|
| [`Brand-Voice.md`](file:///home/cosmin/Work/Scripts/Obsidian/personal/PAFF/Research/Email-Customer-Communication/Brand-Voice.md) | Anti-pattern source (`02-classification-taxonomy.md` §6.2) |
| [`2026-04-26 - Iteration 3 - Reclamatii & Escalation Paths.md`](file:///home/cosmin/Work/Scripts/Obsidian/personal/PAFF/Research/Email-Customer-Communication/2026-04-26%20-%20Iteration%203%20-%20Reclamatii%20%26%20Escalation%20Paths.md) | Pattern Florentina = quality `excellent` reference |
| [`2026-04-26 - Iteration 4 - Presiune Temporala & Burst Threads.md`](file:///home/cosmin/Work/Scripts/Obsidian/personal/PAFF/Research/Email-Customer-Communication/2026-04-26%20-%20Iteration%204%20-%20Presiune%20Temporala%20%26%20Burst%20Threads.md) | Cost retroactiv pattern + ETA realistă |
| [`2026-04-26 - Iteration 5 - Sinteza & Livrabile.md`](file:///home/cosmin/Work/Scripts/Obsidian/personal/PAFF/Research/Email-Customer-Communication/2026-04-26%20-%20Iteration%205%20-%20Sinteza%20%26%20Livrabile.md) | Hipoteze de validat statistic |
| [`Templates/01-10`](file:///home/cosmin/Work/Scripts/Obsidian/personal/PAFF/Research/Email-Customer-Communication/Templates/) | Drafts pentru shortcut-uri noi (validate vs golden set în Etapa 6) |

---

## Decision log (locked)

| Topic | Choice | Doc reference |
|---|---|---|
| **PII strategy** | A — Pseudonymization completă pre-LLM | [`03-privacy-model.md`](docs/03-privacy-model.md) |
| **LLM provider** | A — Gemini CLI cu abonament (NU API) | [`00-charter.md §5`](docs/00-charter.md#5-decision-log) |
| **Repo strategy** | B — `research/` în AutoText | (acest folder) |
| **Scope** | `contact@paff.ro` only V1 | [`00-charter.md §3`](docs/00-charter.md#3-scope) |
| **Perioadă** | 24 luni (2024-04 → 2026-04) | idem |
| **Cost** | $0 (gemini CLI) | [`00-charter.md §4 SC8`](docs/00-charter.md#4-success-criteria-măsurabile) |

---

## Stare actuală

- ✅ Etapa 1.1: Branch `feat/email-research-foundation` creat
- ✅ Etapa 1.2: Charter scris
- ✅ Etapa 1.3: Data schema definit
- ✅ Etapa 1.4: Taxonomy DRAFT (cu TODOs pentru Cosmin)
- ✅ Etapa 1.5: Privacy model
- ✅ Etapa 1.6: Eval methodology
- 🔄 Etapa 1.7: README + .gitignore + pre-commit hook (acum)
- ⏳ Etapa 1.8: Commit + handoff

**Next:** Cosmin completează TODOs din [`02-classification-taxonomy.md`](docs/02-classification-taxonomy.md), apoi pornim Etapa 2.

---

## Cum cer ajutor

- **Plan / strategy:** discuție cu Claude Code în main session
- **Specific implementation:** spawn agent specializat (Senior Developer pentru pipeline code, Data scientist pentru analysis)
- **Adversarial review:** `/challenge-codex` (când e disponibil) sau `/dual-llm` cu Gemini second opinion
- **Re-research peste 6 luni:** `/schedule` să mă reamintească

---

*Versiune: 1.0 — 2026-04-28*
