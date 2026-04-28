# Pipeline Enrich + Analyze

Adaugă clasificări la thread-uri, găsește template matches în SQLite, și scanează anti-pattern-uri la scale. Rulează DUPĂ ce `corpus/raw/` e populat.

---

## Flow

```
corpus/raw/YYYY-MM/thread-*.json
        ↓
   classify_thread.py  (Gemini CLI — intent, sentiment, response_type, quality_label, anti_patterns_detected)
        ↓
corpus/enriched/YYYY-MM/thread-*.json
        ↓
   match_template.py   (Pure Python — fuzzy CHRF match cu cele 62 textsync_shortcut)
        ↓
   anti_patterns.py    (Pure Python regex — scaler la cele 7+ anti-pattern Brand-Voice)
        ↓
corpus/enriched/_anti_patterns_summary.json
```

---

## Scripts

### `classify_thread.py` — Gemini CLI clasificare

Costul: $0 (abonament). Rate limit: ~30 req/min (Gemini CLI free tier).

```bash
# Test pe 5 thread-uri (verificare prompt + format output):
uv run --group research python research/pipelines/enrich/classify_thread.py \
  --limit 5 --verbose

# Run complet pe corpus:
uv run --group research python research/pipelines/enrich/classify_thread.py

# Resume daca s-a oprit:
uv run --group research python research/pipelines/enrich/classify_thread.py --resume

# Parallel (max 10 workers):
uv run --group research python research/pipelines/enrich/classify_thread.py --workers 5

# Doar o luna specifica:
uv run --group research python research/pipelines/enrich/classify_thread.py --window 2024-04
```

**Estimat timp:** ~10 sec/thread sequential, ~2 sec/thread cu 5 workers paraleli.
Pentru ~5.000 thread-uri: ~14 ore sequential, ~3 ore cu 5 workers.

### `match_template.py` — Fuzzy match shortcut-uri

Citește cele 62 shortcut-uri din `db.sqlite3` (`textsync_shortcut`), face CHRF score pentru fiecare răspuns PAFF, marchează `template_pure / template_modified / ad_hoc`.

```bash
uv run --group research python research/pipelines/enrich/match_template.py

# Doar pe o luna specifica:
uv run --group research python research/pipelines/enrich/match_template.py --window 2024-04
```

**Estimat timp:** ~30 sec pentru tot corpus-ul (pure Python, fast).

**Praguri:**
- `template_pure`: CHRF ≥ 0.85
- `template_modified`: CHRF ≥ 0.60
- `ad_hoc`: CHRF < 0.60

Calibrate empiric — adjustabil în `match_template.py`.

### `anti_patterns.py` — Regex scanner la scale

Scaner pure Python pentru cele 7 anti-pattern-uri detectabile lexical:
- `salut_fara_diacritice` ("Buna ziua" în loc de "Bună ziua")
- `salut_fara_virgula` ("Bună ziua" fără virgulă)
- `salut_cu_spatiu_punct` ("Buna ziua .")
- `eta_47_zile_template` ("4-7 zile lucrătoare" copy-paste)
- `brand_string_inconsistent` ("Producator ambalaje" / "Fabrică")
- `mode_telegrafic` (<30 cuvinte fără salut + fără semnătură)
- `lipsa_diacritice_partial` (≥2 cuvinte cheie fără diacritice)

Output: `corpus/enriched/_anti_patterns_summary.json` cu agregare per-pattern + per-window.

```bash
uv run --group research python research/pipelines/analyze/anti_patterns.py
```

**Estimat timp:** ~20 sec pentru tot corpus-ul.

---

## Order of execution

1. **Fetch** — `pipelines/ingest/fetch_gmail.py` populează `corpus/raw/`
2. **Match templates** — `pipelines/enrich/match_template.py` (NU depinde de classify_thread, poate rula primul)
3. **Anti-patterns** — `pipelines/analyze/anti_patterns.py` (idem, independent)
4. **Classify** — `pipelines/enrich/classify_thread.py` (Gemini CLI, lent)

În principiu ordinea 2-4 nu contează pentru output-ul final — fiecare adaugă propriul câmp în enriched JSON. Pentru iterare rapidă, rulează 2+3 înainte de 4.

---

## Output format final per thread

```json
{
  "_schema_version": "1.0",
  "_stage": "enriched",
  "thread_id": "...",
  "subject_root": "...",
  "messages": [
    {
      "message_id": "...",
      "direction": "inbound|outbound",
      "body": {...},
      "template_match": {                       ← from match_template.py
        "shortcut_id": 105,
        "shortcut_key": "mc1",
        "similarity_chrf": 0.94,
        "response_type": "template_pure"
      },
      "anti_patterns_regex": [...]              ← from anti_patterns.py
    }
  ],
  "classification": {                           ← from classify_thread.py
    "thread_summary": "...",
    "client_traits": {...},
    "thread_quality_overall": "good",
    "improvement_opportunity": "..."
  }
}
```

---

## Audit

Toate run-urile loguite în `research/audit.log`:

```jsonl
{"ts": "...", "action": "classify_run_start", "total_threads": 5234, "workers": 5}
{"ts": "...", "action": "classify_run_done", "ok": 5210, "err": 24, "duration_seconds": 11400}
{"ts": "...", "action": "template_match_done", "messages_processed": 12450, "matches_pure": 7800, ...}
{"ts": "...", "action": "anti_patterns_done", "total_messages_scanned": 12450, "patterns_total_count": {...}}
```

---

## Known limitations

- **Gemini CLI rate limit**: când subscription quota se atinge, script-ul va crăpa cu eroare API. Aşteaptă ~5 min sau scade `--workers`.
- **Output JSON parsing fragile**: dacă Gemini returnează text suplimentar înainte/după JSON, `extract_json_from_response` încearcă 3 strategii. Dacă tot nu merge, mesajul ajunge în error log.
- **CHRF threshold-uri arbitrar**: 0.85 / 0.60 sunt euristice. După primul run, vezi distribuția scor-urilor și ajustează.
- **Anti-patterns regex incomplet**: `cost_retroactiv`, `tacere_la_cerere_preventiva`, `lipsa_recunoastere_recurent`, `lipsa_reciprocitate_caldura` nu sunt în regex scanner — necesită cross-thread reasoning sau LLM (le marchează clasificator-ul Gemini).
