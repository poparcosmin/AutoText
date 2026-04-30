"""Quarantine spam/newsletter threads from enriched/ to spam/.

NU șterge fizic — mută într-un folder paralel care e ignorat de pipeline analiza.
Reversibil prin mutare înapoi.

Uses tiered classifier:
1. HARD-NOISE — domain match (mailchimp, sendgrid, etc.) — auto-quarantine
2. NEWSLETTER-PATTERN — subject + body patterns specific newsletters/spam
3. AUTOMATED-NOTIFICATION — facturi automate, FAN courier no-reply, banci, ANAF

Logging: research/corpus/_quarantine.log cu motiv per thread mutat.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parents[3]
ENRICHED = REPO_ROOT / "research" / "corpus" / "enriched"
SPAM = REPO_ROOT / "research" / "corpus" / "spam"
LOG_PATH = REPO_ROOT / "research" / "corpus" / "_quarantine.log"


# ============================================================
# Tier 1 — HARD-NOISE: marketing platforms (instant quarantine)
# ============================================================
HARD_NOISE_DOMAINS = re.compile(
    r"@.*("
    r"mailchimp|mailchi\.mp|sendgrid|sendinblue|sendibm|brevomail|"
    r"mandrillapp|hubspot|elasticemail|constantcontact|"
    r"r\.netseo|netseomarketing|"
    r"news\.cursuri-functionari|nl\.|nl@|"
    r"campaign-archive|list-manage|"
    r"info\.pluxee|biz96\.r\.a\.d|sodexo\.ro|"
    r"\.sendinblue\.com|\.elasticemail\.com|\.amazonaws\.com|"
    r"reply\.constantcontact"
    r")",
    re.IGNORECASE,
)

# ============================================================
# Tier 2 — NEWSLETTER patterns
# ============================================================
NEWSLETTER_SUBJECT = re.compile(
    r"("
    r"newsletter|unsubscribe|view in browser|expo\b|"
    r"trade fair|fasttextile|robotics expo|"
    r"\bcurs(ul|uri)?\b|\bwebinar\b|\bconferinta\b|\bforum\b|\bsummit\b|"
    r"\bseminar\b|\bmasa rotunda\b|\bworkshop\b|"
    r"black friday|white friday|cyber monday|"
    r"\bpromo(ție|tie|tia|tii)?\b|\breducer[ei]\b|"
    r"^.*(strigare|promo).*(vacant|săr|toamn|vară|primăvar)|"
    r"\bofert(a|e) (de )?toamn|\bofert(a|e) (de )?primăvar|"
    r"^[🌍🚚🍂🍁🍃🌸🌷🌺🌹🎄☀️❄️🎁]+|"
    r"^👉|^✨|^📚|^🤫|^🎉|^💡|^🎁|^🚀|^📦 bobst|^📦 dumitru"
    r")",
    re.IGNORECASE,
)

NEWSLETTER_BODY = re.compile(
    r"("
    r"view this email in your browser|"
    r"click here to unsubscribe|"
    r"\bunsubscribe\b|"
    r"^<!doctype|"
    r"campaign delivered|"
    r"this email was sent to you because|"
    r"pentru a vizualiza (online|varianta on-?line) (acest mesaj|mesajul)|"
    r"pentru a vedea (online|conținutul) acest(ui)? (mail|mesaj)|"
    r"click(\s+aici)? pentru a (vedea|vizualiza)|"
    r"vizualizati on-?line"
    r")",
    re.IGNORECASE,
)


# Heuristic: HTML-heavy bodies (>30% HTML tags) → marketing email
def html_heavy(body: str) -> bool:
    if len(body) < 200:
        return False
    tags = len(re.findall(r"<[a-z][^>]{0,40}>", body, re.IGNORECASE))
    return tags > 20 and tags / max(1, len(body) / 100) > 5


# ============================================================
# Tier 3 — AUTOMATED notifications (curieri, banci, ANAF, e-Factura)
# ============================================================
AUTOMATED_DOMAINS = re.compile(
    r"@.*("
    r"fancourier|curierdragonstar|sameday|"
    r"anaf|afm\.ro|sistemetax|insse\.ro|"
    r"netopia|euplatesc|libra-bank|bcr\.ro|brd\.ro|ing\.ro|raiffeisen|btrl\.ro|"
    r"facebook|linkedin|booking\.com|airbnb|"
    r"google.*alerts|alerts@|notifications@|notification@|"
    r"factura_e@|factura@|facturare@|"
    r"^vanzari\.[^@]+@|^marketing@|^office@.*marketing|"
    r"no-?reply|noreply"
    r")",
    re.IGNORECASE,
)

AUTOMATED_SUBJECT = re.compile(
    r"("
    r"^FAN Courier|^Sameday|^DSC Expres|"
    r"^A fost emisa Factura|^Factura .{0,30}\d{6,}|"
    r"^Notificari ANAF|^\(AFM-Declaratii|^\[ANAF|"
    r"^Tranzactie efectuata|^Tranzactie aprobata|"
    r"^Sold facturi|^Sold debit|"
    r"^Confirmare comanda nr\.? \d+|"
    r"^E-Factura|^Factura electronica|"
    r"^Plata efectuata catre|^Aviz scadenta|"
    r"^Expeditii FAN|"
    r"^Tracking|^Awb"
    r")",
    re.IGNORECASE,
)

# ============================================================
# Tier 4 — B2B SALES PROSPECTING (cold outreach)
# ============================================================
COLD_OUTREACH_SUBJECT = re.compile(
    r"("
    r"propunere colaborare\b|"
    r"oferta personalizata.*colaborare|"
    r"\bcadou\b.*partener|"
    r"\bxgrow\b|\bfonduri\s+nerambursabile\b|"
    r"\baplica\s+(la|pentru)\b|"
    r"recuperare creante|recuperati facturile|"
    r"echipamente de protect|softlead|"
    r"prospectare|listare oferta|"
    r"^information for the (purchasing|procurement)|"
    r"^performanta si eficienta|"
    r"^revista (top|.*management)|"
    r"^.*magazin online destinat|"
    r"^auto[\s_-]*mail|^\[auto|"
    r"^happy (holidays|new year)|^merry christmas|^craciun fericit"
    r")",
    re.IGNORECASE,
)

# Cold outreach in body — "Dear Sir/Madam" sau prezentare manufacturer fara mention PAFF
COLD_OUTREACH_BODY = re.compile(
    r"("
    r"^\s*dear\s+(sir|madam|sirs|colleagues|customer)|"
    r"^\s*greetings\s*[,!]|"
    r"we are (a |the |one of )?(leading\s+)?(manufactur|suppl|produc)|"
    r"\bestablished in \d{4}|"
    r"please find (attached|enclosed) (our )?(catalog|product|company)"
    r")",
    re.IGNORECASE,
)

# Automated B2B confirmations (alta companie i-a trimis PAFF un AUTO MAIL)
AUTO_REPLY_SUBJECT = re.compile(
    r"("
    r"^\[auto[\s_-]*mail|"
    r"^\[automatic|"
    r"^automatic reply|^out of office|^auto-?reply|"
    r"^delivery (status|notification|failure)|"
    r"^undelivered mail|"
    r"^message blocked|"
    r"^id-?ul de caz|"
    r"sondaj de satisfac|^evaluati experienta|"
    r"^\[ticket\s*#?\d+|"
    r"^a apărut ediția|^a aparut editia"
    r")",
    re.IGNORECASE,
)

# Surveys
SURVEY_DOMAINS = re.compile(
    r"@.*("
    r"ipsos|qualtrics|surveymonkey|typeform|google\.forms|"
    r"feedback|surveys?\."
    r")",
    re.IGNORECASE,
)


def is_paff_mention(body: str) -> bool:
    """Check daca mesajul mentioneaza explicit PAFF / produsele lor."""
    if not body or len(body) < 20:
        return False
    return bool(
        re.search(
            r"\b(paff|cutii?\s+(carton|standard|personalizat)|carton\s+(ondulat|microondulat)|"
            r"separator(i)?|stante?|flexograf|placi de carton|ambalaj\s+(carton|hartie))\b",
            body,
            re.IGNORECASE,
        )
    )


# Foreign-language cold pitches (HU, PL, ES, DE, FR, TR, IT) — fără PAFF mention
FOREIGN_LANGUAGE_HINT = re.compile(
    r"^("
    r"\s*minőség|\s*tegye különleges|"  # HU
    r"\s*szanowny|\s*drodzy|"  # PL
    r"\s*estimado|\s*estimada|"  # ES
    r"\s*sehr geehrt|\s*hallo herr|"  # DE
    r"\s*sayın|\s*değerli|"  # TR
    r"\s*gentile (signor|cliente)"  # IT
    r")",
    re.IGNORECASE,
)


# Body short + only HTML signature blocks
def is_only_signature(body: str) -> bool:
    """Mesaj fara continut real — doar signature."""
    if not body:
        return True
    text_lines = [
        line.strip()
        for line in body.split("\n")
        if line.strip() and not line.strip().startswith(">")
    ]
    if not text_lines:
        return True
    # Daca toate liniile sunt < 5 cuvinte si suma < 30 cuvinte = signature only
    total_words = sum(len(line.split()) for line in text_lines)
    return total_words < 5  # ex: "OK:O ZIBUNA !" sau "Multumesc, X"


@dataclass
class ClassifyResult:
    is_noise: bool
    tier: str
    reason: str


def classify_thread(thread: dict) -> ClassifyResult:
    """Returneaza tier + reason pentru un thread."""
    msgs = thread.get("messages", [])
    if not msgs:
        return ClassifyResult(False, "n/a", "no messages")

    # Threads cu OUTBOUND ÎN PRIMUL MESAJ = PAFF a inițiat (NU spam, păstrăm)
    msgs_sorted = sorted(msgs, key=lambda m: m.get("timestamp") or "")
    first_msg = msgs_sorted[0]
    if first_msg.get("direction") == "outbound":
        return ClassifyResult(False, "paff_initiated", "PAFF a initiat thread-ul")

    # Threads cu CEL PUTIN UN OUTBOUND PAFF = a fost legitim (s-a raspuns)
    has_paff_response = any(m.get("direction") == "outbound" for m in msgs)
    # Cazul "spam" tipic e thread izolat fără răspuns. Dacă PAFF a răspuns,
    # presupunem că a meritat (nu mutăm chiar dacă match newsletter).
    # → Filter STRICT pe inbound-only.
    if has_paff_response:
        return ClassifyResult(False, "paff_responded", "PAFF a raspuns")

    # De aici: thread inbound-only, posibil spam
    first_inbound = first_msg
    headers = first_inbound.get("headers", {})
    from_h = headers.get("from") or {}
    from_email = (from_h.get("email") or "").strip()
    subject = (thread.get("subject_root") or "").strip()
    body = first_inbound.get("body", {}).get("text_plain") or ""

    # Tier 1: HARD-NOISE domains
    if HARD_NOISE_DOMAINS.search(from_email):
        return ClassifyResult(True, "tier1_hard_noise", f"domain={from_email}")

    # Tier 2: NEWSLETTER patterns
    if NEWSLETTER_SUBJECT.search(subject):
        return ClassifyResult(
            True, "tier2_newsletter_subject", f"subject={subject[:60]}"
        )
    if NEWSLETTER_BODY.search(body[:1000]):
        return ClassifyResult(
            True, "tier2_newsletter_body", "body has newsletter pattern"
        )
    if html_heavy(body):
        return ClassifyResult(True, "tier2_html_heavy", "body is HTML-heavy marketing")

    # Tier 3: AUTOMATED notifications
    if AUTOMATED_DOMAINS.search(from_email):
        return ClassifyResult(True, "tier3_automated", f"domain={from_email}")
    if AUTOMATED_SUBJECT.search(subject):
        return ClassifyResult(
            True, "tier3_automated_subject", f"subject={subject[:60]}"
        )

    # Tier 4: COLD OUTREACH
    if COLD_OUTREACH_SUBJECT.search(subject):
        return ClassifyResult(
            True, "tier4_cold_outreach_subject", f"subject={subject[:60]}"
        )
    if COLD_OUTREACH_BODY.search(body[:500]):
        return ClassifyResult(True, "tier4_cold_outreach_body", "body cold pitch")

    # Tier 4b: AUTO-REPLY / surveys / tickets
    if AUTO_REPLY_SUBJECT.search(subject):
        return ClassifyResult(True, "tier4b_auto_reply", f"subject={subject[:60]}")
    if SURVEY_DOMAINS.search(from_email):
        return ClassifyResult(True, "tier4b_survey", f"domain={from_email}")

    # Tier 5: FOREIGN LANGUAGE pitches without PAFF mention
    if FOREIGN_LANGUAGE_HINT.search(body[:200]) and not is_paff_mention(body):
        return ClassifyResult(
            True, "tier5_foreign_pitch", "foreign-language cold pitch"
        )

    # Tier 6: subiect gol sau mesaj de conținut foarte scurt fără PAFF mention
    if (not subject or len(subject.strip()) < 3) and is_only_signature(body):
        return ClassifyResult(True, "tier6_empty", "empty subject + minimal body")

    # Heuristic combinata: subiect cu emoji + body cu link tracking
    if re.search(r"[👉✨📚🤫🎉💡🎁🚀❄️🎄☀️]", subject) and re.search(
        r"https?://[^\s]+(track|click|campaign|utm_)", body
    ):
        return ClassifyResult(True, "tier2_emoji_tracking", "emoji + tracking link")

    # Cold outreach 2: mesaj lung in engleza/alta limba straina, fara PAFF mention
    # si cu cuvinte cheie sales (manufacturer, supplier, etc.)
    if (
        len(body) > 300
        and not is_paff_mention(body)
        and re.search(
            r"\b(manufactur|supplier|producer|wholesale|export)\w*\b",
            body[:1500],
            re.IGNORECASE,
        )
        and re.search(
            r"\b(catalog|brochure|product line|range of)\b", body[:1500], re.IGNORECASE
        )
    ):
        return ClassifyResult(True, "tier4_cold_pitch_long", "long generic sales pitch")

    return ClassifyResult(False, "kept", "no spam pattern")


def main(dry_run: bool = False) -> None:
    SPAM.mkdir(parents=True, exist_ok=True)
    moved_log: list[dict] = []
    counts: Counter = Counter()

    for window_dir in sorted(ENRICHED.iterdir()):
        if not window_dir.is_dir():
            continue
        for thread_path in window_dir.glob("thread-*.json"):
            try:
                thread = json.loads(thread_path.read_text())
            except Exception as e:
                print(f"[SKIP] {thread_path}: {e}")
                continue

            result = classify_thread(thread)
            counts[result.tier] += 1

            if not result.is_noise:
                continue

            # Move to spam/<window>/
            dest_dir = SPAM / window_dir.name
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / thread_path.name

            log_rec = {
                "thread_id": thread.get("thread_id"),
                "window": window_dir.name,
                "tier": result.tier,
                "reason": result.reason,
                "from": (
                    (thread["messages"][0].get("headers", {}).get("from") or {}).get(
                        "email", ""
                    )
                ),
                "subject": (thread.get("subject_root") or "")[:120],
                "moved_at": datetime.now(timezone.utc).isoformat(),
            }
            moved_log.append(log_rec)

            if not dry_run:
                shutil.move(str(thread_path), str(dest_path))

    # Save log
    if not dry_run:
        with LOG_PATH.open("a") as f:
            for rec in moved_log:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\n{'DRY RUN — ' if dry_run else ''}Quarantine summary:")
    print(f"  Total threads procesate: {sum(counts.values())}")
    print(f"  Mutate in spam/: {len(moved_log)}")
    print()
    print("Distribution per tier:")
    for tier, c in counts.most_common():
        marker = "🔴" if "tier" in tier else "✅"
        print(f"  {marker} {tier:30s}  {c:>5d}")

    if moved_log:
        print(f"\nLog scris la: {LOG_PATH}")
        print(f"Spam files in: {SPAM}/")


if __name__ == "__main__":
    import sys

    main(dry_run="--dry-run" in sys.argv)
