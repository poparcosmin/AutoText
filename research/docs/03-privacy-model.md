# Privacy Model — GDPR & Threat Model

> **Versiune:** 1.0
> **Status:** STABLE pentru Etapa 2 ingestion
> **Legal basis:** Articolul 6(1)(f) GDPR — interes legitim (îmbunătățire serviciu pentru clienți)

---

## 1. Principles

1. **Privacy by design** — toate stages după `corpus/raw/` sunt pseudonymized. PII apare ONLY în `corpus/raw/` și `corpus/pii_mapping/` (gitignored, file permissions restrictive).
2. **Data minimization** — păstrăm doar ce e necesar pentru research; atașamente, conținut binar, header-uri intrusive eliminate la stage `pseudonymized`.
3. **Storage limitation** — corpus original (raw) șters la +12 luni de la finalul cercetării (parking lot reminder).
4. **No third-party PII exposure** — Gemini CLI primește exclusiv text pseudonymized. Mapping table nu părăsește disk-ul local.
5. **Reversibility for legitimate need** — mapping `<TOKEN> → real value` păstrat ca JSON local pentru re-identificare manuală dacă apare necesar (ex: un client cere ștergere → găsim toate mesajele lui).
6. **Layered protection (no encryption overhead)** — protecție prin (a) gitignore strict, (b) pre-commit hook, (c) file permissions Linux, (d) disk encryption la nivel OS (LUKS/dm-crypt). NU folosim GPG/gpg per fișier — overhead operațional fără beneficiu marginal pe sistem single-user.

---

## 2. Datele procesate

### 2.1 Categorii de PII identificate

| Categorie | Exemple | Tratament |
|---|---|---|
| **Nume persoane fizice** | Aura Chitulescu (PAFF), client Anca Oprea | Token `<PERSON_N>` sau persona pentru PAFF (`Aura`, `Florentina`, etc.) |
| **Adrese email** | `client@firma.ro`, `contact@paff.ro` | `<EMAIL_N>`; `contact@paff.ro` păstrat (entitate cunoscută public) |
| **Numere telefon** | `0721234567`, `+40 740 467 233` | `<PHONE>` sau `<PAFF_PHONE>` pentru telefoanele oficiale PAFF |
| **CIF / CUI** | `RO12345678`, `J15/1583/1993` | `<CIF_N>` sau `<PAFF_CIF>` (RO4807535 e public) |
| **IBAN** | `RO32RNCB...` | `<IBAN_N>` sau `<PAFF_IBAN>` |
| **Numere AWB** | `1Z999AA...`, `AWB123456789` | `<AWB_N>` |
| **Numere comandă internă** | `Comanda #12345` | Păstrat (nu identifică persoană) |
| **Adrese fizice** | `Str. Florilor 12, București` | `<ADDRESS_N>` |
| **Numere CNP** | apărere defensive | `<CNP>` (probabil absent în context B2B, dar regex preventiv) |
| **Card / numere bancare** | rare în email | `<CARD>` — block + alert |

### 2.2 Date care **NU** sunt PII (păstrate ca atare)

- Numele firmelor publice (3f.ro, Modadora, Maxoll, etc.) → push în `<ORG_N>` din precauție, dar retention extins
- Numele de produs PAFF (E-flute, Pantone XX, BOPP, etc.)
- Date tehnice (dimensiuni, gramaj, materiale)
- Politețuri standard ("Bună ziua", "Cu stimă")
- Denumirea publică PAFF, brand strings, telefoane oficiale (publicate pe paff.ro)

---

## 3. Pseudonymization pipeline

### 3.1 Order of operations

```
raw/                           Step 1: spaCy NER (ro_core_news_lg)
  ↓                                    → identifică PERSON, ORG, LOC
  ↓                            Step 2: Regex pass
  ↓                                    → CIF, IBAN, telefon, AWB, email, IBAN
  ↓                            Step 3: Lookup table populate
  ↓                                    → assign stable token IDs (<PERSON_47> = "Anca Oprea" mereu)
  ↓                            Step 4: Replace în text_plain
  ↓                            Step 5: Sanity check
  ↓                                    → final regex scan: 0 detection-uri reziduale
pseudonymized/
```

### 3.2 Token format

| Pattern | Format |
|---|---|
| Persoane | `<PERSON_N>` unde N e int incremental (stabil per persoană) |
| Organizații | `<ORG_N>` |
| Email | `<EMAIL_N>` (corespunde aceleiași persoane când e cazul) |
| Telefon | `<PHONE>` (NU N — toate telefoanele de client = `<PHONE>`, prezența contează, nu identitatea) |
| CIF | `<CIF_N>` |
| IBAN | `<IBAN_N>` |
| AWB | `<AWB>` (idem cu PHONE) |
| Adrese | `<ADDRESS_N>` |

**De ce stable IDs (cu N) pentru persoane/firme:** păstrăm continuitate pentru analiza pattern-urilor (ex: "<PERSON_47> a scris 8 emailuri în 23 luni" = recurence). Fără ID stabil, această analiză e imposibilă.

### 3.3 Mapping table

**Locație:** `research/corpus/pii_mapping/tokens-{YYYY-MM}.json` (plain JSON, gitignored, `chmod 600`).

```json
{
  "_schema_version": "1.0",
  "generated_at": "2026-04-28T10:00:00Z",
  "tokens": {
    "<PERSON_47>": {
      "real_value": "Anca Oprea",
      "first_seen_message": "msg-id-...",
      "occurrence_count": 12
    },
    "<ORG_12>": {
      "real_value": "Modadora SRL",
      "first_seen_message": "msg-id-...",
      "occurrence_count": 8
    }
  }
}
```

**Protecție:**
- `.gitignore` blochează `**/pii_mapping/`
- Pre-commit hook blochează commit accidental
- `chmod 600` pe fișiere (read/write doar owner)
- `chmod 700` pe directorul `pii_mapping/`
- Sistem cu disk encryption (LUKS) la nivel OS — single layer suficient pentru threat model single-user local

### 3.4 Reverse lookup (when needed)

Pentru cazuri legitime (ex: cerere ștergere GDPR, debug findings):

```bash
jq '.tokens["<PERSON_47>"]' research/corpus/pii_mapping/tokens-2026-04.json
# → {"real_value": "Anca Oprea", ...}
```

Audit log obligatoriu în `research/audit.log`:
```
2026-05-15T14:00:00Z reverse-lookup token=<PERSON_47> reason="GDPR erasure request" actor=cosmin
```

---

## 4. Threat model

### 4.1 Assets de protejat

| Asset | Confidentiality | Integrity | Availability |
|---|---|---|---|
| `corpus/raw/` (PII real) | 🔴 Mare | 🟡 Med | 🟢 Mic |
| `corpus/pii_mapping/` (re-identification) | 🔴 Mare | 🔴 Mare | 🟡 Med |
| `corpus/pseudonymized/` | 🟡 Med (cu mapping = poate reidentifica) | 🟡 Med | 🟢 Mic |
| `corpus/enriched/` | 🟡 Med | 🟡 Med | 🟢 Mic |
| `ground-truth/` | 🟢 Mic | 🟡 Med | 🟢 Mic |

### 4.2 Threats considered

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **T1: Commit accidental `corpus/raw/` în public repo** | Med | Mare | `.gitignore` strict + pre-commit hook (vezi §6) |
| **T2: Mapping table compromis (laptop furat)** | Mică | Mare | Disk encryption (LUKS) la nivel OS — single layer suficient |
| **T3: PII leak la Gemini provider via CLI** | Med | Mediu | Pseudonymization PRE-CLI mandatory; sanity scan între `pseudonymized/` și CLI input |
| **T4: Re-identification din `enriched/` fără mapping** | Mică | Mediu | Token format atomic (`<PERSON_N>` indistinguishable), nu păstrăm hint-uri |
| **T5: Insider threat (alți useri pe sistem)** | Mică | Mare | Permisiuni `chmod 700 research/corpus/` + `chmod 600` pe fișiere |
| **T6: Cerere autorități / instanță** | Foarte mică | Mare | Cooperare cu legal; corpus accesibil doar local |
| **T7: Subiect cere ștergere date** | Sigur >0 | Mediu | Reverse lookup token → eliminate din corpus + ground truth, regenerează enriched |
| **T8: Backup necriptat (Time Machine, Dropbox)** | Med | Mare | Excludere explicită `research/corpus/` din backup paths |

---

## 5. Subject rights handling

GDPR Art. 15-22 — drepturile persoanelor vizate.

| Drept | Cum răspundem |
|---|---|
| **Acces (Art. 15)** | Reverse lookup token → mesaje în corpus → export mesaje pseudonymized + clasificări |
| **Rectificare (Art. 16)** | N/A (datele sunt corespondență istorică, nu se rectifică) |
| **Ștergere (Art. 17)** | Identifică token → șterge mesaje din toate stages → re-genereze enriched → audit log |
| **Restricție (Art. 18)** | Marchez token ca `restricted: true` în mapping; pipeline-ul skip-uiește la analyze |
| **Portabilitate (Art. 20)** | Export JSON al tuturor mesajelor pseudonymized (datele subiectului sunt deja în format structurat) |
| **Obiecție (Art. 21)** | Stop processing pentru subiectul respectiv; șterg din ground truth |

**SLA:** răspuns în max 30 zile per Art. 12(3).

---

## 6. Technical safeguards

### 6.1 .gitignore

Adăugat în `.gitignore` la root:

```gitignore
# Research — PII protection
research/corpus/
research/audit.log
research/.env
**/pii_mapping/
```

### 6.2 Pre-commit hook

Script în `research/scripts/pre-commit-corpus-guard.sh` (instalat ca `.git/hooks/pre-commit`):

```bash
#!/bin/bash
# Block accidental commit of corpus or PII mapping
if git diff --cached --name-only | grep -qE "research/corpus/|pii_mapping/|\.gpg$"; then
  echo "❌ BLOCK: attempting to commit research corpus or PII mapping"
  echo "   Files in stage:"
  git diff --cached --name-only | grep -E "research/corpus/|pii_mapping/|\.gpg$"
  exit 1
fi

# Detect PII leaks în restul fișierelor (regex sweep pe staged content)
LEAKS=$(git diff --cached -U0 | grep -E "RO[0-9]{2}[A-Z]{4}[0-9]+|\b07[0-9]{8}\b|\bRO[0-9]{6,10}\b" || true)
if [ -n "$LEAKS" ]; then
  echo "⚠️  POSSIBLE PII LEAK in staged content:"
  echo "$LEAKS"
  echo ""
  echo "Review and confirm? [y/N]"
  read -r confirm
  [ "$confirm" != "y" ] && exit 1
fi

exit 0
```

### 6.3 File permissions

```bash
chmod 700 research/corpus/
chmod 600 research/corpus/raw/*.json
chmod 700 research/corpus/pii_mapping/
chmod 600 research/corpus/pii_mapping/*.json
```

### 6.4 Audit log format

`research/audit.log` (gitignored):

```
2026-04-28T10:00:00Z action=ingest_window window=2024-04 messages=842 outcome=success
2026-04-28T10:30:00Z action=pseudonymize window=2024-04 tokens_created=312 outcome=success
2026-04-28T11:00:00Z action=llm_classify model=gemini-cli-0.39.1 messages=842 duration_s=3600 outcome=success
2026-05-15T14:00:00Z action=reverse_lookup token=<PERSON_47> reason="GDPR erasure request" actor=cosmin
```

---

## 7. Retention policy

| Stage | Retention | Trigger ștergere |
|---|---|---|
| `corpus/raw/` | **12 luni post-research finalizare** | Calendar trigger; manual confirmation; `rm -rf corpus/raw/` |
| `corpus/pii_mapping/` | **12 luni post-research** | Idem |
| `corpus/pseudonymized/` | **24 luni** (utilă pentru re-runs) | După 24m sau dacă schema bumps major |
| `corpus/enriched/` | **24 luni** | Idem |
| `ground-truth/` | **Indefinit** (anonymous, valoare educațională) | Doar la cerere subiect |
| `reports/` | **Indefinit** | Manual cleanup |
| `audit.log` | **5 ani** | Compliance / forensics |

---

## 8. Mental DPA (Data Processing Agreement)

Cu cine partajăm date și sub ce contract:

| Procesator | Date partajate | Bază contractuală |
|---|---|---|
| **Google (Gmail Workspace)** | Datele sunt deja la Google (originalul) | Workspace Terms + Romania DPA addendum (default Google) |
| **Google AI (Gemini CLI)** | TEXT PSEUDONYMIZED only — fără PII real | Google AI Terms; abonament Pro/Ultra |
| **Anthropic (Claude Code)** | Sumare + cod — fără PII real | Anthropic Privacy + Commercial Terms |
| **Niciun alt third party** | — | — |

**Important:** Gemini CLI primește exclusiv text post-pseudonymization. Mapping table NU părăsește disk-ul local.

---

## 9. Compliance checklist (pre-Etapa 2)

- [x] Legal basis articulat (Art. 6(1)(f) — interes legitim)
- [x] PII categories identified (§2.1)
- [x] Token format definit (§3.2)
- [x] Threat model documentat (§4)
- [x] Subject rights handling (§5)
- [x] Pre-commit hook instalat (`.git/hooks/pre-commit`)
- [ ] **TODO:** Test pseudonymization pipeline pe sample 10 mesaje + verify 0 PII reziduală (Etapa 2)
- [ ] **TODO:** `chmod 700 research/corpus/` după prima rulare ingestion (Etapa 2)

---

## 10. Referințe

- Charter: `./00-charter.md`
- Data schema (cum sunt persistate token-urile): `./01-data-schema.md`
- GDPR text: https://gdpr-info.eu/
- spaCy NER ro: https://spacy.io/models/ro
- Google AI Privacy: https://ai.google.dev/terms
