"""
Apply advanced AutoText features on top body-template shortcuts.

Adoptă features verificate funcționale în `extension/content.js`:
  - [[greeting]]            — Bună dimineața / ziua / seara (auto pe ora)
  - [[date]], [[date+Nd]], [[date:DD.MM.YYYY]]  — date dinamice
  - [[day]]                 — ziua săptămânii
  - [[user]]                — username expandor
  - [[var:NAME]]            — variabile per-user (cu fallback)
  - [[random:A|B|C]]        — variație micro-frază
  - [[%s(other)]]           — atomic snippet nesting
  - {{name:Label|default}}  — form placeholder la expand
  - $|$                     — cursor positioning după expand

Strategy:
  1. Setup user variables comune (telefon Marius/Picu/Aura, IBAN, FAQ url)
  2. Create atomic snippet shortcuts (salut, mts, cta-mod, eta-*, sig-*)
  3. Refactor top body templates folosind features

Backup: db.sqlite3.bak.20260429-pre-advanced
"""
import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[3] / "db.sqlite3"


# ============================================================
# 1. USER VARIABLES — shared values for all 4 users
# ============================================================
USER_VARIABLES = {
    "tel_aura": "074.466.7233",
    "tel_marius": "0756.119.864",
    "tel_marius_2": "0737.642.346",
    "tel_picu": "0745.992.533",
    "tel_office": "072.169.7233",
    # iban_boxpack — populated at runtime from existing `fb` shortcut value
    # to avoid duplicating the bank identifier in source.
    "webfaq": "https://www.paff.ro/intrebari-frecvente#q3",
    "firma_brand": "PAFF :: Producător ambalaje",
    "track_dragon": "https://dragonstar.ro/tracking/",
    "track_fan": "https://www.fancourier.ro/tracking/",
}


# Per-user variables — different value per user (signature data).
# Keyed by username (must match auth_user.username), then var_name → value.
PER_USER_VARIABLES = {
    "cosmin": {
        "my_name": "Popa R. Cosmin",
        "my_phone": "0756.562.229",
    },
    "bogdan": {
        "my_name": "Bogdan Popa",
        "my_phone": "0756.119.876",
    },
    "aura": {
        "my_name": "Aura Chițulescu",
        "my_phone": "074.466.7233",
    },
    "florian": {
        "my_name": "Popa Florian",
        "my_phone": "0756.119.875",
    },
}


def _extract_iban_from_fb(con: sqlite3.Connection) -> str | None:
    """Read IBAN from fb shortcut. Falls back to backup file if current `fb`
    has been refactored to use [[var:iban_boxpack]] (chicken-and-egg).
    """
    import re
    cur = con.execute("SELECT value FROM textsync_shortcut WHERE key = 'fb';")
    row = cur.fetchone()
    if row:
        match = re.search(r"RO\d{2}[A-Z0-9]{20}", row[0])
        if match:
            return match.group(0)
    # Fallback to backup snapshot taken before text refactor
    backup_path = DB.parent / "db.sqlite3.bak.20260429-pre-text-improve"
    if backup_path.exists():
        try:
            bcon = sqlite3.connect(str(backup_path))
            bcur = bcon.execute("SELECT value FROM textsync_shortcut WHERE key='fb';")
            brow = bcur.fetchone()
            bcon.close()
            if brow:
                match = re.search(r"RO\d{2}[A-Z0-9]{20}", brow[0])
                if match:
                    return match.group(0)
        except Exception:
            pass
    return None


# ============================================================
# 2. ATOMIC SNIPPETS — building blocks reused via [[%s(...)]]
# ============================================================
ATOMIC_SNIPPETS = {
    # Greeting — usable standalone or chained
    "salut": "[[greeting]],",

    # Closings — variation between formal and warm
    "mts": "[[random:Mulțumim!|Vă mulțumim!|Mulțumim pentru încredere!]]",
    "mts_short": "Mulțumim!",

    # CTAs reusable
    "cta-mod": "Pentru orice modificare la adresă sau cantitate, răspundeți la acest email cât mai curând posibil.",

    # Reply scaffolding (standardized 3-option pattern)
    "reply-yn": "Răspundeți scurt:\n ✓ \"OK\" → continuăm\n ✓ \"modificare: ___\" → schimb ceva\n ✓ \"amân\" → lăsăm în coadă",

    # ETAs — single source of truth (schimbi 1 dată, propagă în toate)
    "eta-curier": "Termen estimat livrare: 4-7 zile lucrătoare.",
    "eta-paff": "Termen estimat livrare: 1-3 zile lucrătoare (București).",

    # Signatures — per-user via [[var:my_name]] + [[var:my_phone]]
    # [[user]] retornează username capitalizat (Aura, Bogdan, Cosmin, Florian)
    # [[var:my_name]] / [[var:my_phone]] sunt per-user (PER_USER_VARIABLES)
    "sig-personal": "Cu stimă,\n[[var:my_name]]\n[[var:my_phone]]",
    "sig-short": "Cu stimă,\n[[user]]",
    "sig-equipe": "Cu stimă,\nEchipa PAFF",

    # Tracking links per courier
    "track-fan": "Tracking: [[var:track_fan]]",
    "track-dragon": "Tracking: [[var:track_dragon]]",
}


# ============================================================
# 3. SHORTCUT REFACTORS — primary + 2 variants cu features
# ============================================================
# (id) → (primary, [variant_warm, variant_concise])

SHORTCUT_REFACTORS = {
    # mc1 — Confirmare plată curier
    107: (
        "[[%s(salut)]]\n\nPlata din [[date:DD.MM.YYYY]] confirmată — mulțumim.\n\n"
        "[[random:Pregătim coletele pentru expedierea prin curier.|Coletele intră astăzi în pregătire pentru curier.|Astăzi pregătim coletele pentru curier.]]\n\n"
        "----------------\n\n"
        "INFORMAȚII EXPEDIERE:\n"
        " - [[%s(eta-curier)]]\n"
        " - Vă trimitem numărul de AWB și factura imediat ce pachetul pleacă.\n\n"
        "----------------\n\n"
        "[[%s(cta-mod)]]\n\n"
        "[[%s(mts)]]\n$|$",
        [
            # Cald
            "[[%s(salut)]]\n\nPlata a intrat — mulțumim.\n\n"
            "Coletele intră astăzi în pregătire pentru expediere prin curier. "
            "[[%s(eta-curier)]] Imediat ce pleacă din depozit, vă trimitem AWB-ul "
            "și factura fiscală.\n\n"
            "Dacă apar modificări la adresă sau cantitate, scrieți-ne pe acest email.\n\n"
            "Mulțumim pentru încredere!\n$|$",
            # Scurt
            "[[%s(salut)]]\n\nPlata confirmată azi, [[date:DD.MM]]. "
            "Coletele pleacă în curând prin curier (4-7 zile lucrătoare).\n\n"
            "Pentru orice modificare, răspundeți la acest email.\n\n"
            "Mulțumim!\n$|$",
        ],
    ),

    # ffd — Factură + AWB Dragon Star
    91: (
        "[[%s(salut)]]\n\nAWB: $|$ (Dragon Star)\n[[%s(track-dragon)]]\n\n"
        "Atașat: factura fiscală pentru produsele expediate. "
        "Disponibilă și în e-Factura.\n\n"
        "[[random:Pentru orice nelămurire la primire, răspundeți direct la acest email.|"
        "La primire, dacă observați ceva ce nu e în regulă, scrieți-ne — rezolvăm rapid.|"
        "Dacă coletele par deteriorate la primire, refuzați semnătura și scrieți-ne.]]\n\n"
        "Mulțumim pentru încredere!",
        [
            "[[%s(salut)]]\n\nColetele au plecat astăzi prin Dragon Star.\n\n"
            "AWB: $|$\n[[%s(track-dragon)]]\n"
            "Factură atașată (și disponibilă în e-Factura).\n\n"
            "La primire, dacă observați ceva ce nu e în regulă, scrieți-ne.\n\n"
            "Mulțumim!",
            "[[%s(salut)]]\n\nAWB: $|$ (Dragon Star)\n[[%s(track-dragon)]]\n"
            "Factura atașată + e-Factura.\n\n"
            "Mulțumim!",
        ],
    ),

    # ffan — Factură + AWB Fan Courier
    90: (
        "[[%s(salut)]]\n\nAWB: $|$ (Fan Courier)\n[[%s(track-fan)]]\n\n"
        "Atașat: factura fiscală pentru produsele expediate. "
        "Disponibilă și în e-Factura.\n\n"
        "[[random:Pentru orice nelămurire la primire, răspundeți direct la acest email.|"
        "La primire, dacă observați ceva ce nu e în regulă, scrieți-ne — rezolvăm rapid.|"
        "Dacă coletele par deteriorate la primire, refuzați semnătura și scrieți-ne.]]\n\n"
        "Mulțumim pentru încredere!",
        [
            "[[%s(salut)]]\n\nColetele au plecat astăzi prin Fan Courier.\n\n"
            "AWB: $|$\n[[%s(track-fan)]]\n"
            "Factură atașată (și disponibilă în e-Factura).\n\n"
            "La primire, dacă observați ceva ce nu e în regulă, scrieți-ne.\n\n"
            "Mulțumim!",
            "[[%s(salut)]]\n\nAWB: $|$ (Fan Courier)\n[[%s(track-fan)]]\n"
            "Factura atașată + e-Factura.\n\n"
            "Mulțumim!",
        ],
    ),

    # op — Confirmare comandă + proformă (SINGLE-CTA cu reply scaffolding)
    115: (
        "[[%s(salut)]]\n\nMulțumim pentru comandă! Atașat: proforma {{nr:Număr proformă|}}.\n\n"
        "[[%s(reply-yn)]]\n\n"
        "După plată, producem și ajunge la dvs. în 4-7 zile lucrătoare.\n\n"
        "Mulțumim!\n$|$",
        [
            # Cald
            "[[%s(salut)]]\n\nMulțumim pentru comandă! Găsiți atașată proforma {{nr:Număr proformă|}}.\n\n"
            "Vă rugăm să verificați:\n"
            " - prețul, cantitatea și dimensiunile sunt cele agreate?\n"
            " - dacă da, după plată trimiteți-ne un printscreen al ordinului — "
            "accelerează start-ul producției.\n\n"
            "Pregătim imediat după confirmarea plății; ajung la dvs. în 4-7 zile lucrătoare.\n\n"
            "Mulțumim!\n$|$",
            # Scurt
            "[[%s(salut)]]\n\nMulțumim pentru comandă. Atașat: proforma {{nr:Nr proformă|}}.\n\n"
            "După plată, dacă ne trimiteți printscreen al ordinului, începem pregătirea imediat. "
            "Livrare 4-7 zile lucrătoare.\n\n"
            "Mulțumim!\n$|$",
        ],
    ),

    # mp1 — Livrare PAFF gratuit București
    110: (
        "[[%s(salut)]]\n\nPlata din [[date:DD.MM.YYYY]] confirmată — mulțumim.\n\n"
        "[[random:Coletele pleacă spre București cu mașinile noastre.|Pregătim coletele pentru livrarea în București cu flota proprie.|Coletele intră astăzi în pregătire pentru livrarea cu mașinile noastre.]] "
        "Astfel, [[%s(eta-paff)]]\n\n"
        "----------------\n\n"
        "CONDIȚII LIVRARE PAFF (GRATUITĂ):\n\n"
        " - Livrarea se face până la sediul dumneavoastră.\n"
        " - Produsele se predau în cel mai apropiat loc de parcare sau în curtea sediului.\n"
        " - Șoferul nu poate muta coletele din mașină în incinta clădirii.\n\n"
        "----------------\n\n"
        "Detalii suplimentare: [[var:webfaq]]\n\n"
        "[[%s(mts)]]\n$|$",
        [
            "[[%s(salut)]]\n\nPlata a intrat — mulțumim!\n\n"
            "Coletele pleacă spre București cu mașinile noastre — ajung la dvs. "
            "în 1-3 zile lucrătoare.\n\n"
            "Detalii practice:\n"
            " - livrarea e până la sediul dvs., gratuită.\n"
            " - șoferul lasă coletele la cel mai apropiat loc de parcare/curte.\n"
            " - nu poate urca în clădire — pregătiți cineva la primire.\n\n"
            "FAQ: [[var:webfaq]]\n\nMulțumim!\n$|$",
            "[[%s(salut)]]\n\nPlata confirmată, coletele pleacă cu mașinile noastre "
            "(1-3 zile lucrătoare, gratuit, predare la parcare/curte).\n\n"
            "Detalii: [[var:webfaq]]\n\nMulțumim!\n$|$",
        ],
    ),

    # mr — Contact șofer Marius (cu var pentru telefon)
    105: (
        "Pentru livrarea cu flota PAFF în București, șoferul nostru este Marius. "
        "Îl puteți contacta la [[var:tel_marius]] sau [[var:tel_marius_2]] (apel/WhatsApp). "
        "Disponibil L-V 08-17.",
        [
            "Pentru detalii livrare, sunați direct pe Marius (șoferul nostru pe București): "
            "[[var:tel_marius]] / [[var:tel_marius_2]] — apel sau WhatsApp.",
            "Marius (șofer PAFF București) — [[var:tel_marius]] / [[var:tel_marius_2]] (apel/WhatsApp, L-V 08-17).",
        ],
    ),

    # pi — Contact șofer Picu
    114: (
        "Pentru livrarea cu flota PAFF în București, șoferul nostru este Picu (Marales Gheorghe). "
        "Îl puteți contacta la [[var:tel_picu]] (apel/WhatsApp). Disponibil L-V 08-17.",
        [
            "Pe traseu pe București vă întâlniți cu Picu (Marales Gheorghe), șoferul nostru. "
            "Direct la el: [[var:tel_picu]] — apel sau WhatsApp.",
            "Picu (Marales Gheorghe), șofer PAFF — [[var:tel_picu]] (apel/WhatsApp, L-V 08-17).",
        ],
    ),

    # ia1 — Concediu (cu form placeholders pentru date)
    95: (
        "[[%s(salut)]]\n\nPAFF e în concediu între {{start:Data început|22.12}} și "
        "{{end:Data sfârșit|07.01}}.\n\n"
        "Comenzile primite acum intră în coadă pentru prima parte a lunii "
        "{{revenire:Luna revenire|ianuarie}}, în ordinea sosirii.\n\n"
        "Răspundeți cu:\n"
        " ✓ \"păstrez\" → ținem comanda activă, trimitem proforma după revenire\n"
        " ✓ \"anulez\" → dezactivăm comanda\n\n"
        "Sărbători liniștite!\n$|$",
        [
            "[[%s(salut)]]\n\nÎn perioada {{start:Data început|22.12}} - {{end:Data sfârșit|07.01}} "
            "PAFF e în concediu.\n\n"
            "Comenzile primite acum se procesează după întoarcere — în prima parte a lunii "
            "{{revenire:Luna revenire|ianuarie}}.\n\n"
            "Dacă sunteți de acord, păstrăm comanda în coadă și vă trimitem proforma "
            "imediat ce reluăm activitatea. Așteptăm un OK scurt din partea dvs.\n\n"
            "Sărbători liniștite!\n$|$",
            "[[%s(salut)]]\n\nSuntem în concediu între {{start:Început|22.12}} și "
            "{{end:Sfârșit|07.01}}. Comanda dvs. intră în prima parte a lunii "
            "{{revenire:Luna revenire|ianuarie}} — confirmați dacă o păstrăm.\n\n"
            "Mulțumim și sărbători frumoase!\n$|$",
        ],
    ),

    # nu1 — Refuz cu form placeholder pentru reason
    112: (
        "[[%s(salut)]]\n\nMulțumim pentru interesul acordat produselor PAFF.\n\n"
        "Din păcate, nu putem da curs cererii dumneavoastră deoarece "
        "{{motiv:Motivul refuzului|nu intră în portofoliul nostru}}.\n\n"
        "[[%s(sig-personal)]]\n$|$",
        [
            "[[%s(salut)]]\n\nMulțumim că v-ați gândit la noi pentru "
            "{{produs:Ce a cerut clientul|}}. Din păcate {{motiv:Motiv|nu producem acest tip de produs}}"
            " — specializarea PAFF e ambalaje carton ondulat.\n\n"
            "Pentru ce căutați, încercați [recomandare partener / motor căutare]. "
            "Pentru cutii ondulate, suntem aici.\n\n"
            "[[%s(sig-personal)]]\n$|$",
            "[[%s(salut)]]\n\nDin păcate, {{motiv:Motiv (frază completă)|nu putem da curs acestei cereri}}.\n\n"
            "Pentru acest tip de cerere, [recomandare partener / sugestie / \"ne pare rău\"].\n\n"
            "[[%s(sig-personal)]]\n$|$",
        ],
    ),

    # mc2 — Up-sell București
    108: (
        "[[%s(salut)]]\n\nVă mulțumim pentru plată.\n\n"
        "Adresa dumneavoastră din București ne permite să vă oferim o opțiune de "
        "transport mai rapidă decât cea standard, folosind mașinile noastre.\n\n"
        "Ce variantă preferați:\n\n"
        "----------------\n\n"
        "OPȚIUNEA 1: LIVRARE RAPIDĂ PAFF (RECOMANDAT)\n"
        " - 1-3 zile lucrătoare, fără înfoliere.\n"
        " - Predare în cel mai apropiat loc de parcare sau curtea sediului.\n\n"
        "OPȚIUNEA 2: LIVRARE PRIN CURIER (STANDARD)\n"
        " - 4-7 zile lucrătoare, cu AWB și înfoliere.\n"
        " - Condițiile firmei de curierat.\n\n"
        "----------------\n\n"
        "Răspundeți cu \"PAFF\" sau \"curier\" și pregătesc expedierea.\n\n"
        "Mulțumim!\n$|$",
        [
            "[[%s(salut)]]\n\nMulțumim pentru plată!\n\n"
            "Pentru București, vă putem trimite cu mașinile noastre — vă scapă de costul curier "
            "și vă scurtează termenul.\n\n"
            "OPȚIUNEA 1 — LIVRARE PAFF (recomandat: rapid, gratuit)\n"
            " - 1-3 zile lucrătoare, fără înfoliere\n"
            " - șoferul predă la parcare/curte (nu urcă în clădire)\n\n"
            "OPȚIUNEA 2 — CURIER STANDARD\n"
            " - 4-7 zile lucrătoare, cu AWB și înfoliere\n\n"
            "Care preferați? Aștept un OK scurt și pregătesc expedierea.\n\nMulțumim!\n$|$",
            "[[%s(salut)]]\n\nPlata confirmată. Pentru București vă putem trimite cu flota proprie:\n"
            " 1) PAFF: 1-3 zile, gratuit, predare parcare/curte.\n"
            " 2) Curier: 4-7 zile, cu înfoliere și AWB.\n\n"
            "Care preferați?\n\nMulțumim!\n$|$",
        ],
    ),

    # fb — Facturare Boxpack (cu var pentru IBAN)
    88: (
        "Facturarea se face pe firma noastră Boxpack SRL.\n\n"
        "Plata se face în contul ING: [[var:iban_boxpack]]\n\n"
        "Beneficiar: BOXPACK SRL",
        [
            "Pentru această comandă, facturarea se face pe firma noastră Boxpack SRL.\n\n"
            "Cont bancar (ING):\n[[var:iban_boxpack]]\n\n"
            "Beneficiar: BOXPACK SRL\n\n"
            "(IBAN-ul se poate folosi direct, fără spații, dacă aplicația dvs. de banking "
            "nu acceptă formatul cu spații.)",
            "Factură pe Boxpack SRL.\nIBAN ING: [[var:iban_boxpack]]",
        ],
    ),
}


def upsert_user_variables(con: sqlite3.Connection):
    """Insert/update shared variables on all users + per-user signature data."""
    cur = con.cursor()
    cur.execute("SELECT id, username FROM auth_user WHERE is_active = 1;")
    users = cur.fetchall()  # [(id, username), ...]

    # Compose effective shared vars: static + dynamically extracted IBAN
    effective_shared = dict(USER_VARIABLES)
    iban = _extract_iban_from_fb(con)
    if iban:
        effective_shared["iban_boxpack"] = iban
    else:
        print("  ⚠️  fb shortcut missing or no IBAN matched — iban_boxpack skipped")

    shared_count = len(effective_shared) * len(users)
    per_user_count = sum(
        len(PER_USER_VARIABLES.get(uname, {})) for _, uname in users
    )
    print(f"  Shared: {len(effective_shared)} × {len(users)} = {shared_count} ops")
    print(f"  Per-user signatures: {per_user_count} ops")

    for uid, uname in users:
        # Shared vars (same value all users)
        for name, value in effective_shared.items():
            cur.execute(
                "INSERT INTO textsync_uservariable (user_id, name, value, updated_at) "
                "VALUES (?, ?, ?, datetime('now')) "
                "ON CONFLICT(user_id, name) DO UPDATE SET "
                "value = excluded.value, updated_at = datetime('now');",
                (uid, name, value),
            )
        # Per-user vars (different value per user)
        per_user = PER_USER_VARIABLES.get(uname, {})
        for name, value in per_user.items():
            cur.execute(
                "INSERT INTO textsync_uservariable (user_id, name, value, updated_at) "
                "VALUES (?, ?, ?, datetime('now')) "
                "ON CONFLICT(user_id, name) DO UPDATE SET "
                "value = excluded.value, updated_at = datetime('now');",
                (uid, name, value),
            )


def upsert_atomic_snippets(con: sqlite3.Connection):
    """Insert atomic snippet shortcuts (or update if existing keys collide)."""
    cur = con.cursor()
    print(f"  Upserting {len(ATOMIC_SNIPPETS)} atomic snippets")
    for key, value in ATOMIC_SNIPPETS.items():
        cur.execute(
            "INSERT INTO textsync_shortcut "
            "(key, value, content_type, updated_at, variants, usage_count) "
            "VALUES (?, ?, 'text', datetime('now'), '[]', 0) "
            "ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, updated_at = datetime('now');",
            (key, value),
        )


def update_top_shortcuts(con: sqlite3.Connection):
    """UPDATE primary value + variants JSON for top body templates."""
    cur = con.cursor()
    print(f"  Updating {len(SHORTCUT_REFACTORS)} top shortcuts with advanced features")
    for sid, (primary, variants) in SHORTCUT_REFACTORS.items():
        cur.execute(
            "UPDATE textsync_shortcut "
            "SET value = ?, variants = ?, updated_at = datetime('now') "
            "WHERE id = ?;",
            (primary, json.dumps(variants, ensure_ascii=False), sid),
        )
        print(f"    id={sid}: primary={len(primary)} chars, variants={len(variants)}")


def main():
    print(f"DB: {DB}")
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute("BEGIN;")

        print("\n=== Step 1: User variables (shared values) ===")
        upsert_user_variables(con)

        print("\n=== Step 2: Atomic snippets ===")
        # Need a UNIQUE constraint on `key` for ON CONFLICT to work.
        # Verify and add if missing.
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='textsync_shortcut' AND sql LIKE '%UNIQUE%key%';"
        )
        if not cur.fetchone():
            print("  Adding UNIQUE index on textsync_shortcut.key (idempotent)")
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "textsync_shortcut_key_unique ON textsync_shortcut(key);"
            )
        upsert_atomic_snippets(con)

        print("\n=== Step 3: Refactor top body templates ===")
        update_top_shortcuts(con)

        con.commit()
        print("\n✓ All committed")

        # Summary verification
        print("\n=== Verification ===")
        cur.execute("SELECT COUNT(*) FROM textsync_uservariable;")
        print(f"  user variables: {cur.fetchone()[0]}")
        cur.execute(
            "SELECT key FROM textsync_shortcut WHERE key IN ({}) ORDER BY key;".format(
                ",".join(f"'{k}'" for k in ATOMIC_SNIPPETS)
            )
        )
        atomics = [r[0] for r in cur.fetchall()]
        print(f"  atomic snippets present: {len(atomics)} / {len(ATOMIC_SNIPPETS)} → {atomics}")
        cur.execute(
            "SELECT key, length(value), json_array_length(variants) "
            "FROM textsync_shortcut WHERE id IN ({}) ORDER BY id;".format(
                ",".join(str(i) for i in SHORTCUT_REFACTORS)
            )
        )
        for k, vlen, vcount in cur.fetchall():
            print(f"  {k:<6} primary={vlen} chars, variants={vcount} entries")

    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
