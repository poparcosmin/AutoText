# Eval Methodology

> **Versiune:** 1.0
> **Status:** STABLE pentru Etapa 4 ground truth annotation

Document descrie cum măsurăm calitatea cercetării: ground truth, inter-annotator agreement, classifier metrics, statistical validity. Fără acest document, orice claim e opinion, nu evidence.

---

## 1. De ce metodologia contează

Pentru că vrei "enterprise grade", afirmațiile din raport trebuie să fie:
1. **Reproducible** — alt annotator obține rezultate similare (κ > 0.7)
2. **Falsifiable** — există date care le-ar putea contrazice
3. **Quantitative** — "X% din cazuri" cu interval de încredere, NU "des observat"
4. **Externally auditable** — un terț poate verifica metrologia

Fără asta, raportul e părere informată — utilă, dar nu defendable.

---

## 2. Stratified sampling pentru ground truth

### 2.1 De ce stratified, NU random

Random pe 30k mesaje cu distribuție skewed (ex: 80% `comanda_noua`, 1% `feedback_pozitiv`) = ground truth dezechilibrat. Stratified asigură reprezentare proporțională per intent category.

### 2.2 Sample size target

**200 mesaje totale** distribuite stratified pe intent (cele 10 categorii din `02-classification-taxonomy.md`):

| Stratum | n minimum | n target |
|---|---|---|
| `cerere_oferta` | 25 | 50 |
| `comanda_noua` | 25 | 40 |
| `urmarire_status` | 20 | 30 |
| `cerere_tehnica` | 15 | 20 |
| `cerere_urgenta` | 10 | 15 |
| `reclamatie_calitate` | 10 | 15 |
| `dispute_factura` | 8 | 10 |
| `cerere_preventiva` | 5 | 8 |
| `feedback_pozitiv` | 5 | 7 |
| `salutari_protocol` | 5 | 5 |
| `altceva` | 0 | 0 |
| **TOTAL** | **128** | **200** |

**Min n=30 per category** pentru claim-uri statistice (rule of thumb pentru CLT). Pentru categories cu n<30, claim-uri sunt prezentate ca "qualitative observations", nu cu CI.

### 2.3 Sample selection algorithm

```python
# pseudocode
def stratified_sample(corpus, taxonomy, n=200):
    # Folosim PRIMA clasificare automată (Gemini) ca bucketing aproximativ
    # Apoi sample uniform în fiecare bucket
    sampled = []
    for intent, target_n in taxonomy.items():
        bucket = [msg for msg in corpus if msg.intent == intent]
        sampled.extend(random.sample(bucket, min(target_n, len(bucket))))
    return sampled
```

Setting `random.seed(42)` pentru reproducibility.

---

## 3. Inter-annotator agreement (κ)

### 3.1 Protocol

1. Cosmin etichetează **toate 200** mesaje (annotator A)
2. Un al doilea annotator etichetează **50 random sample din cele 200** (annotator B)
3. Se calculează **Cohen's kappa** pe cele 50 etichete duble
4. Threshold: **κ ≥ 0.7** = taxonomy bună
5. Dacă κ < 0.7 → analyze disagreements → refine taxonomy → re-annotate batch nou

### 3.2 Cohen's kappa formula

```
κ = (po - pe) / (1 - pe)

unde:
- po = observed agreement (% match between annotators)
- pe = expected agreement by chance (depends on label distribution)
```

Implementare: `sklearn.metrics.cohen_kappa_score(labels_a, labels_b)`.

### 3.3 Interpretation

| κ | Interpretation | Action |
|---|---|---|
| > 0.8 | Excellent | Procedeu cu enrichment |
| 0.7 – 0.8 | Good | Procedeu, document edge cases observate |
| 0.6 – 0.7 | Moderate | Refine taxonomy + re-annotate sample 50 nou |
| < 0.6 | Poor | Stop. Re-design taxonomy. Nu pornim Etapa 5. |

### 3.4 Annotator B options

Cine poate fi annotator B (în ordine de preferință):

1. **Aura sau Florentina** (PAFF intern) — cunosc context perfect; potential bias subtil
2. **Cosmin (re-annotation după 2 săptămâni)** — same person, drift natural în timp simulează a doua perspectivă; nu ideal dar acceptabil pentru solo-research
3. **LLM (Claude Sonnet)** — fast, no human bias, dar nu e human ground truth
4. **External freelance annotator** (Upwork, RO speaker) — gold standard dacă buget permite

**Default:** opțiunea 2 (Cosmin re-annotation după 14 zile) — practic și reproducible.

---

## 4. Classifier evaluation metrics

### 4.1 Per-classifier targets

| Classifier | Metric | Target | Calculation |
|---|---|---|---|
| `intent.primary` | Macro-F1 | ≥ 0.85 | Per-class F1, average uniform across classes |
| `intent.primary` | Per-class precision | ≥ 0.80 pentru top 5 categories | Standard precision |
| `intent.primary` | Per-class recall | ≥ 0.80 pentru top 5 categories | Standard recall |
| `sentiment.label` | Accuracy | ≥ 0.80 | (label-uri rare) |
| `sentiment.label` | MAE pe scale_value | ≤ 0.4 | Mean Absolute Error pe scale -1 to +1 |
| `responder_persona` | Accuracy | ≥ 0.95 | Easy task — semnătură explicit; only fallback la LLM are imprecision |
| `response_type` | Accuracy | ≥ 0.85 | Fuzzy match cu pragul ales (0.85 / 0.60) |
| `quality_assessment.label` | Accuracy | ≥ 0.70 | Subjective; threshold mai mic acceptat |
| `quality_assessment.rubric_scores` | MAE | ≤ 0.8 | Pe scale 1-5 |

### 4.2 Confusion matrix per classifier

Pentru fiecare classifier, generate confusion matrix vs ground truth:

```python
from sklearn.metrics import confusion_matrix, classification_report

y_true = [...]  # din ground-truth/annotations-v1.jsonl
y_pred = [...]  # din corpus/enriched/

print(confusion_matrix(y_true, y_pred, labels=INTENT_CATEGORIES))
print(classification_report(y_true, y_pred))
```

Output salvat în `eval/results/confusion-matrix-{classifier}-{timestamp}.txt`.

### 4.3 Failure mode analysis

Pentru fiecare classifier cu F1 < target:
1. Identify top 5 confusion pairs (ex: `cerere_oferta` ↔ `cerere_tehnica` confundate des)
2. Pentru fiecare pair, sample 10 mesaje confuze
3. Analyze: e taxonomy ambiguous? e prompt slab? e edge case real?
4. Decision: refine prompt | refine taxonomy | accept (cu documented limitation)

---

## 5. Golden response set (50 perechi)

### 5.1 Scop

Setul "ideal responses" servește 3 scopuri:
1. **Baseline pentru evaluation:** orice template/shortcut viitor poate fi măsurat vs cum ar fi răspuns Cosmin ideal
2. **Training set pentru Brand-Voice v2:** exemplele ideale informează regulile noi
3. **Reality check:** dacă golden response e foarte diferit de actual PAFF response → opportunity claritate

### 5.2 Selection criteria

Pentru fiecare din cele 10 intent categories, alege 5 mesaje inbound (50 total) unde:
- Răspunsul actual PAFF a fost `mismatch` sau `harmful` (sau cel puțin `acceptable`)
- Cosmin scrie manual răspunsul ideal (5-15 minute per pair)

### 5.3 Format

În `ground-truth/ideal-responses-v1.jsonl`:

```json
{"pair_id":"gt-resp-001","message_id":"...","intent":"cerere_oferta","client_message_excerpt":"<PERSON_47> ne puteți trimite oferta...","actual_paff_response":"Bună ziua, găsiți atașat oferta...","ideal_response":"Bună ziua, [...]","quality_actual":"acceptable","ideal_brand_voice_rules_applied":["recunoaștere_recurent","cost_transparent"],"notes":"Client e <ORG_12>, recurent cu 8 comenzi în 2.5 ani"}
```

### 5.4 Usage

```bash
# Compare any new template against golden set
python research/eval/golden_match.py --new-template "templates/05-scuze-reclamatie.md"
# Output: similarity score, divergence points, BVoice rules respected/violated
```

---

## 6. Statistical validity

### 6.1 Confidence intervals pentru claim-uri

Pentru orice afirmație "X% din mesaje au property Y":
- n ≥ 30 (per stratum) → 95% CI calculat cu binomial proportion CI (Wilson score)
- n < 30 → claim prezentat ca "qualitative observation", NU procentaj

```python
from statsmodels.stats.proportion import proportion_confint

p_hat = count / n
ci_low, ci_high = proportion_confint(count, n, alpha=0.05, method="wilson")
# Report as: "X% (95% CI: [Y%, Z%])"
```

### 6.2 Power analysis

Pentru a detecta o diferență de 10pp între 2 categorii cu α=0.05, β=0.20:
- n minim per group ≈ 200
- Total per intent stratum target: 200/n_categories ≈ 20 (deci n=200 corpus = OK pentru top 5 categories, marginal pentru tail)

### 6.3 Multiple testing correction

Dacă facem k teste statistice paralele (ex: comparație intent vs intent pentru 10 categorii = 45 teste):
- Bonferroni: α_adjusted = 0.05 / k = 0.05 / 45 = 0.0011
- Sau Benjamini-Hochberg pentru FDR control

Implementare: `statsmodels.stats.multitest.multipletests`.

---

## 7. Eval pipeline

### 7.1 `eval/run_eval.sh`

```bash
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

# 1. Validate ground truth schema
uv run python eval/validate_annotations.py ground-truth/annotations-v1.jsonl

# 2. Load enriched corpus + ground truth
# 3. Compute κ between annotators
uv run python eval/cohen_kappa.py \
  --ann-a ground-truth/annotations-v1.jsonl \
  --ann-b ground-truth/annotations-v1-second-pass.jsonl \
  --output eval/results/kappa-$(date +%Y%m%d).json

# 4. Compute classifier metrics
uv run python eval/classifier_metrics.py \
  --corpus corpus/enriched/ \
  --ground-truth ground-truth/annotations-v1.jsonl \
  --output eval/results/classifier-$(date +%Y%m%d).json

# 5. Generate eval report
uv run python eval/generate_report.py \
  --kappa eval/results/kappa-*.json \
  --classifier eval/results/classifier-*.json \
  --output reports/eval-report-$(date +%Y%m%d).md
```

### 7.2 Acceptance criteria pentru continue Etapa 5

Înainte de a porni analysis paralelă (Etapa 5):

| Gate | Threshold | Pe ce |
|---|---|---|
| Inter-annotator κ | ≥ 0.7 | Intent classification |
| Classifier F1 (intent macro) | ≥ 0.85 | Pe golden set |
| Classifier F1 (sentiment) | ≥ 0.80 | Pe golden set |
| Sample completeness | ≥ 95% | n acoperire vs target stratified |

**Fail any gate → STOP Etapa 5, rework taxonomy or prompts.**

---

## 8. Reporting standards

### 8.1 Format claim în raport

❌ **Bad:** "PAFF răspunde des cu '4-7 zile' chiar și când livrează în 1-2."

✅ **Good:** "În 78% (95% CI: [73%, 82%], n=412) din răspunsurile la `comanda_noua` confirmate cu plată, PAFF folosește expresia '4-7 zile lucrătoare' deși time-to-delivery efectiv mediu pe 24 luni este 2.3 zile (σ=1.1, n=412)."

### 8.2 Visualizations standard

- **Bar charts** pentru distribuții discrete (intent frequency, persona frequency)
- **Heatmap** pentru cross-tab (intent × responder, intent × quality)
- **Time series** pentru evoluție temporală (anti-pattern frequency / month)
- **Sankey** pentru flow client → PAFF response → outcome
- **Box plots** pentru distribuții numerice (response time, length)

Tool: matplotlib + seaborn în Jupyter; export PNG + interactive HTML cu plotly.

---

## 9. Cadenta re-eval

| Trigger | Acțiune |
|---|---|
| Taxonomy change | Re-run κ pe sample 50 nou |
| New corpus window (re-research la +6m) | Re-run full eval pipeline |
| Classifier prompt change | Re-run F1 pe golden set |
| Adăugare anti-pattern nou | Add la rubric, re-eval `quality_assessment` pe 50 sample |

---

## 10. Referințe

- `./00-charter.md` — success criteria SC3, SC4
- `./02-classification-taxonomy.md` — taxonomy versionată
- Cohen's kappa: https://en.wikipedia.org/wiki/Cohen%27s_kappa
- scikit-learn metrics: https://scikit-learn.org/stable/modules/model_evaluation.html
- statsmodels CIs: https://www.statsmodels.org/stable/stats.html
