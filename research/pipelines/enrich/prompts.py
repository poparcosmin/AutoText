"""Prompt templates pentru clasificare via Gemini CLI.

Fiecare prompt e auto-suficient: include taxonomia, instructiunile, formatul de output.
Versionat in `_classifier_versions` din output JSON.
"""

from __future__ import annotations

CLASSIFIER_VERSION = "v1.0-gemini-cli"


THREAD_CLASSIFIER_PROMPT = """\
Ești un analist senior care studiază comunicarea email a unei firme românești de ambalaje (PAFF) cu clienții ei.

Analizează thread-ul de mai jos și clasifică FIECARE mesaj. Returnează STRICT un JSON valid (fără text suplimentar, fără markdown fence).

## Taxonomy

### Intent client (doar mesaje cu direction="inbound") — ALEGE UNA:
- `cerere_oferta`: client cere preț/disponibilitate fără comandă fermă
- `comanda_noua`: client transmite comandă fermă sau confirmă plata
- `urmarire_status`: client întreabă unde e comanda / când vine
- `reclamatie_calitate`: defect / produs neconform / lipsă
- `dispute_factura`: cost diferit de așteptat / clarificare factură
- `cerere_urgenta`: deadline strâns sau "urgent / azi / cât mai curând"
- `cerere_preventiva`: client cere atenție specială înainte de producție ("fără defecte", "ca la început")
- `feedback_pozitiv`: mulțumire, recomandare, recenzie
- `cerere_tehnica`: întrebare specs (Pantone, dimensiuni, materiale, stante)
- `salutari_protocol`: felicitări sărbători, schimb politețuri fără task concret
- `altceva`: nu se potrivește

### Sentiment client (doar inbound) — ALEGE UNUL:
- `entuziast`: mulțumire explicită, exclamații, emoji caldi (🤗🌷), recomandare
- `politicos`: formule complete politețe, ton respectuos
- `neutru`: tranzacțional, fără semnale emoționale
- `frustrat`: nemulțumire fără agresiune (ex: "din nou", "iar", "deja a 3-a oară")
- `agresiv`: acuzații, ALL CAPS, amenințare ANPC/legal

### Pentru mesaje OUTBOUND PAFF:
- `responder_persona`: aura | florentina | bogdan | florian | generic | unknown (din semnătură)
- `response_type`: template_pure | template_modified | ad_hoc | hybrid
- `quality_label`: excellent | good | acceptable | mismatch | harmful
- `tone_match`: 1-5 (cât de bine reciprocă tonul clientului)
- `context_addressed`: 1-5 (cât de bine răspunde la întrebările concrete)
- `anti_patterns_detected`: lista cu codurile aplicabile dintre:
  * `salut_fara_diacritice` ("Buna" în loc de "Bună")
  * `salut_fara_virgula` ("Bună ziua" fără virgulă)
  * `salut_cu_spatiu_punct` ("Buna ziua ." cu spațiu+punct)
  * `eta_47_zile_template` ("4-7 zile lucrătoare" copy-paste când contextul nu cere)
  * `cost_retroactiv` (cost menționat doar pe factură, nu în proformă)
  * `brand_string_inconsistent` ("Producator ambalaje"/"Fabrică" în loc de "Producător de Ambalaje")
  * `mode_telegrafic` (<30 cuvinte fără salut + fără semnătură)
  * `tacere_la_cerere_preventiva` (client cere "fără defecte" → PAFF nu acknowledge)
  * `lipsa_recunoastere_recurent` (client recurent primește template generic)
  * `lipsa_reciprocitate_caldura` (client cu emoji/formule calde → PAFF răspunde sec)
  * `lipsa_diacritice_partial` (text PAFF parțial fără diacritice)

## Thread de analizat

```json
{thread_json}
```

## Format output (STRICT JSON, fără markdown, fără explicații în afară):

```json
{{
  "thread_id": "...",
  "_classifier_version": "v1.0-gemini-cli",
  "thread_summary": "1-2 propoziții despre ce se petrece în thread",
  "client_traits": {{
    "politeness": "polite|neutral|terse|aggressive",
    "formality": "formal|business|casual",
    "language_quality": "native|business-ro|en-ro-mix"
  }},
  "messages": [
    {{
      "message_id": "...",
      "direction": "inbound|outbound|system_notification|unknown",
      "intent": "cerere_oferta|...|null (dacă outbound)",
      "sentiment": "neutru|...|null (dacă outbound)",
      "responder_persona": "aura|...|null (dacă inbound)",
      "response_type": "template_pure|...|null (dacă inbound)",
      "quality_label": "excellent|...|null (dacă inbound)",
      "tone_match": 1-5 sau null,
      "context_addressed": 1-5 sau null,
      "anti_patterns_detected": ["..."]
    }}
  ],
  "thread_quality_overall": "excellent|good|acceptable|mismatch|harmful",
  "improvement_opportunity": "1-2 propoziții — ce ar fi trebuit să facă PAFF diferit, dacă ceva"
}}
```

Returnează DOAR JSON-ul. Niciun alt text.
"""


def render_thread_prompt(thread_json: str) -> str:
    """Construieste prompt-ul finalpentru un thread serializat ca JSON."""
    return THREAD_CLASSIFIER_PROMPT.format(thread_json=thread_json)


__all__ = ["CLASSIFIER_VERSION", "THREAD_CLASSIFIER_PROMPT", "render_thread_prompt"]
