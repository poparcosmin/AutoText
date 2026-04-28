# Data Schema — Canonical Format

> **Versiune:** 1.0
> **Status:** STABLE pentru Etapa 2 ingestion

Schema canonică pentru toate entitățile din pipeline: `Message`, `Thread`, `Classification`, `Annotation`. Toate datele pe disk respectă aceste structuri (JSON). Schimbări breaking → bump major version + migration script.

---

## 1. Principii

1. **JSON over everything** — read/write din Python, parse cu `pydantic`, viewable cu `jq`
2. **Separation of stages** — `raw/` ≠ `pseudonymized/` ≠ `enriched/` (același message ID, layered enrichment)
3. **Idempotent writes** — orice script poate fi rerun fără duplicare (key = `message_id`)
4. **Schema versioning** — fiecare fișier are `_schema_version: "1.0"` în root
5. **Pydantic-first** — toate schemele definite ca `pydantic.BaseModel` în `pipelines/schemas.py`

---

## 2. Entitatea `Message`

Reprezentare canonică a unui email individual (un message Gmail).

```json
{
  "_schema_version": "1.0",
  "_stage": "raw|pseudonymized|enriched",
  "message_id": "gmail-message-id-rfc822",
  "thread_id": "gmail-thread-id",
  "in_reply_to": "<previous-message-id@domain> | null",
  "references": ["<msg1@domain>", "<msg2@domain>"],
  "timestamp": "2026-04-28T14:32:11+03:00",
  "direction": "inbound|outbound",
  "headers": {
    "from": {"name": "Aura Chitulescu", "email": "contact@paff.ro"},
    "to": [{"name": "...", "email": "..."}],
    "cc": [],
    "bcc": [],
    "subject": "Confirmare comandă PAFF #12345",
    "reply_to": "contact@paff.ro | null"
  },
  "body": {
    "text_plain": "Bună ziua,\n\n...",
    "text_html": "<div>Bună ziua,...</div> | null",
    "language_detected": "ro|en|other",
    "char_count": 487,
    "word_count": 84
  },
  "attachments": [
    {"filename": "proforma-12345.pdf", "mime_type": "application/pdf", "size_bytes": 84512, "content_hash": "sha256:..."}
  ],
  "labels": ["INBOX", "SENT", "..."],
  "is_template_response": null,
  "template_match_id": null,
  "metadata": {
    "fetched_at": "2026-04-28T16:00:00Z",
    "fetcher_version": "1.0",
    "source": "gmail-api"
  }
}
```

### 2.1 Field semantics

| Field | Tip | Stage | Note |
|---|---|---|---|
| `message_id` | string (RFC 822) | toate | PRIMARY KEY |
| `thread_id` | string | toate | Group-by pentru thread reconstruction |
| `direction` | enum | toate | `outbound` = `from.email == "contact@paff.ro"` |
| `body.text_plain` | string | `raw` original / `pseudonymized` redactat | Plain text canonic; HTML doar referință |
| `body.text_html` | string \| null | `raw` only | Eliminat după extragerea text_plain (storage saving) |
| `attachments[].content_hash` | string | toate | NU stocăm content; doar hash pentru tracking |
| `is_template_response` | bool \| null | `enriched` | True dacă match >85% cu shortcut din `textsync_shortcut` |
| `template_match_id` | int \| null | `enriched` | FK la `textsync_shortcut.id` dacă match |

### 2.2 Diferențe per stage

| Stage | Differences |
|---|---|
| `raw` | Conține PII real, encrypted at rest cu gpg, NU se commit-uie. `_stage: "raw"` |
| `pseudonymized` | PII înlocuit cu tokens (`<PERSON_47>`, `<ORG_12>`, `<PHONE>`, `<EMAIL>`, `<CIF>`, `<IBAN>`, `<AWB>`). Mapping table criptat separat. `_stage: "pseudonymized"` |
| `enriched` | Pseudonymized + classification fields adăugate (vezi §4). `_stage: "enriched"` |

---

## 3. Entitatea `Thread`

Group complete de mesaje cu același `thread_id`, cu metadata derivată.

```json
{
  "_schema_version": "1.0",
  "thread_id": "gmail-thread-id",
  "subject_root": "Confirmare comandă PAFF #12345",
  "participants": [
    {"role": "client", "token": "<PERSON_47>", "first_seen": "2026-04-15T09:12:00+03:00"},
    {"role": "paff", "token": "Aura", "first_seen": "2026-04-15T09:45:00+03:00"}
  ],
  "message_ids": ["msg-1", "msg-2", "msg-3"],
  "turn_count": 3,
  "started_at": "2026-04-15T09:12:00+03:00",
  "last_message_at": "2026-04-16T11:30:00+03:00",
  "duration_hours": 26.3,
  "client_segment": "1shot|occasional|recurring|strategic|unknown",
  "thread_metrics": {
    "first_response_time_minutes": 33,
    "avg_paff_response_time_minutes": 45,
    "longest_silence_minutes": 720,
    "client_msg_count": 1,
    "paff_msg_count": 2,
    "total_attachments": 1
  }
}
```

---

## 4. Entitatea `Classification` (per Message, doar inbound)

Pentru fiecare mesaj inbound (de la client), stocăm clasificările multi-dimensionale.

```json
{
  "_schema_version": "1.0",
  "message_id": "gmail-message-id",
  "classified_at": "2026-04-29T10:00:00Z",
  "classifier_versions": {
    "intent": "v1.0-gemini-pro",
    "sentiment": "v1.0-gemini-pro",
    "responder": "regex+v1.0-fallback-llm"
  },
  "intent": {
    "primary": "cerere_oferta",
    "secondary": ["cerere_tehnica"],
    "confidence": 0.92
  },
  "sentiment": {
    "label": "neutru",
    "scale_value": 0.1,
    "confidence": 0.88
  },
  "urgency_signals": {
    "explicit_urgent": false,
    "deadline_mentioned": null,
    "complaint_keywords": []
  },
  "client_traits": {
    "politeness": "polite|neutral|terse|aggressive",
    "formality": "formal|business|casual",
    "language_quality": "native|business-ro|en-ro-mix"
  }
}
```

Pentru fiecare mesaj **outbound PAFF**:

```json
{
  "_schema_version": "1.0",
  "message_id": "gmail-message-id-paff",
  "thread_id": "gmail-thread-id",
  "responds_to": "gmail-message-id-client",
  "responder_persona": "aura|florentina|bogdan|florian|generic|unknown",
  "response_type": "template_pure|template_modified|ad_hoc|hybrid",
  "template_match": {
    "shortcut_id": 105,
    "shortcut_key": "mc0",
    "similarity": 0.94,
    "method": "fuzzy_chrf+embedding"
  },
  "quality_assessment": {
    "label": "excellent|good|acceptable|mismatch|harmful",
    "rubric_scores": {
      "context_addressed": 4,
      "tone_match": 5,
      "completeness": 3,
      "anti_pattern_count": 1
    },
    "anti_patterns_detected": ["copy_paste_4_7_zile"],
    "confidence": 0.81
  }
}
```

---

## 5. Entitatea `Annotation` (ground truth manual)

Format pentru cele 200 etichetări manuale + 50 ideal responses.

```json
{
  "_schema_version": "1.0",
  "annotation_id": "gt-2026-04-28-001",
  "annotator": "cosmin",
  "annotated_at": "2026-04-28T14:00:00Z",
  "message_id": "gmail-message-id",
  "labels": {
    "intent_primary": "cerere_oferta",
    "intent_secondary": ["cerere_tehnica"],
    "sentiment": "neutru",
    "client_segment_observed": "occasional"
  },
  "ideal_response": "Bună ziua,\n\n[exemplu de răspuns ideal scris manual de Cosmin]...",
  "ideal_response_template": "TPL-04-cotatie + variantă A",
  "notes": "Client vrea ofertă rapidă pentru clișee. Întreabă explicit despre Pantone matching.",
  "quality_of_actual_paff_response": "mismatch_template_too_generic"
}
```

---

## 6. File naming + folder layout

```
research/corpus/
├── raw/                                  # gpg-encrypted, gitignored
│   └── 2024-04/
│       ├── thread-{thread_id}.json.gpg
│       └── ...
├── pseudonymized/                        # plain JSON, gitignored
│   └── 2024-04/
│       ├── thread-{thread_id}.json
│       └── ...
├── enriched/                             # plain JSON + classifications, gitignored
│   └── 2024-04/
│       ├── thread-{thread_id}.json
│       └── ...
└── pii_mapping/                          # gpg-encrypted, gitignored
    └── tokens-2026-04.json.gpg

research/ground-truth/                    # versioned (committed)
├── annotations-v1.jsonl                  # 200 manual labels
├── ideal-responses-v1.jsonl              # 50 ideal pairs
└── README.md
```

**Pattern fișier:** un thread = un fișier JSON cu array de mesaje. Sortat după `started_at` ASC. Filename = `thread-{thread_id_first8chars}.json` pentru navigability.

---

## 7. Pydantic models (referință)

Implementare canonică în `research/pipelines/schemas.py` (de creat în Etapa 2):

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Optional

class Headers(BaseModel):
    from_: dict
    to: list[dict]
    subject: str
    # ...

class Message(BaseModel):
    schema_version: Literal["1.0"] = Field(alias="_schema_version", default="1.0")
    stage: Literal["raw", "pseudonymized", "enriched"] = Field(alias="_stage")
    message_id: str
    thread_id: str
    direction: Literal["inbound", "outbound"]
    timestamp: datetime
    headers: Headers
    body: "Body"
    # ...
```

Toate scripts vor importa de aici. NU duplicăm definiții.

---

## 8. Schema evolution policy

| Tip schimbare | Acțiune |
|---|---|
| Backward-compatible (add field opțional) | Bump minor (1.0 → 1.1), no migration |
| Backward-incompatible (rename, remove) | Bump major (1.x → 2.0), migration script obligatoriu |
| Breaking change la PII tokens | Necesită re-pseudonymization complet |

Toate scripts validează `_schema_version` la load și refuză input cu version major diferit.

---

## 9. Referințe

- Charter: `./00-charter.md`
- Privacy model (PII tokens definition): `./03-privacy-model.md`
- Eval methodology (annotation format): `./04-eval-methodology.md`
- Pydantic docs: https://docs.pydantic.dev/latest/
