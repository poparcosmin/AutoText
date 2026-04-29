"""
Add 8 follow-up body shortcuts + 8 subject line shortcuts.
Brevity audit: shorten mp1/mc2 PRIMARY to <125 words (Boomerang sweet spot).

Research source: ~/.claude/data/research/2026-04-29-imbunatatiri-mesaje-cheatsheet.md

All shortcuts use:
  [[%s(salut)]] / [[%s(sig-personal)]] / [[%s(mts)]] etc. atomic snippets
  [[date]] / [[date-Nd]] / [[date+Nwd]] for dynamic timing
  {{form:Label|default}} for inline customization
  $|$ cursor positioning
"""
import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[3] / "db.sqlite3"


# ============================================================
# Layer 1 — Body shortcuts (follow-up + utility)
# ============================================================

BODY_SHORTCUTS = {
    # op-fu1 — Day 3 follow-up post-proformă (soft check + value add)
    "op-fu1": (
        "[[%s(salut)]]\n\n"
        "[[random:Reluăm pe oferta {{produs:Produsul|}} din [[date-3d:DD.MM]] —|"
        "Mă întorc rapid pe proforma trimisă pe [[date-3d:DD.MM]] —|"
        "Reluez pe oferta din [[date-3d:DD.MM]] —]] "
        "[[random:voiam să mă asigur că proforma a ajuns ok la dvs.|"
        "să verific dacă a ajuns totul în regulă.|"
        "voiam să confirm că a ajuns proforma cu bine.]]\n\n"
        "[[random:Aveți vreo întrebare la care să ajut?|"
        "Dacă apare ceva neclar, scrieți un cuvânt scurt.|"
        "Dacă e ceva de clarificat, sunt aici.]]\n\n"
        "Dacă deja decizia s-a luat în altă direcție, nicio problemă — "
        "spuneți-mi și închid oferta din partea noastră.\n\n"
        "[[%s(sig-personal)]]\n$|$",
        [],  # No variants — single CTA pattern, simple is better
    ),

    # op-fu2 — Day 10 follow-up (objection preempt: pricing/timing)
    "op-fu2": (
        "[[%s(salut)]]\n\n"
        "[[random:Revin pe oferta {{produs:Produsul|}} din [[date-10d:DD.MM]] —|"
        "Mă întorc pe oferta din [[date-10d:DD.MM]] —|"
        "Reluez pe proforma trimisă acum 10 zile —]] "
        "ca să răspund la 2 întrebări pe care de obicei le primesc:\n\n"
        " 1. **Prețul.** Ce primiți reflectă materia primă (carton kraft) + "
        "munca de execuție + livrare. Pentru cantități mari putem discuta o "
        "ajustare — spuneți-mi ce volum aveți în vedere.\n"
        " 2. **Timing.** După plată producem și livrăm în 4-7 zile lucrătoare. "
        "Dacă aveți un deadline, încercăm să prioritizăm.\n\n"
        "Dacă ambele sunt OK, reply scurt cu 'OK' și mergem mai departe. "
        "Dacă e altceva — un termen lung, comparare ofertă, etc — spuneți și "
        "vedem împreună.\n\n"
        "[[%s(sig-personal)]]\n$|$",
        [],
    ),

    # op-fu3 — Day 17 BREAKUP (paradox: more replies than 2nd follow-up)
    "op-fu3": (
        "[[%s(salut)]]\n\n"
        "[[random:Pe oferta {{produs:Produsul|}} din [[date-17d:DD.MM]] —|"
        "Pe proforma din [[date-17d:DD.MM]] —|"
        "Pentru oferta trimisă acum 2-3 săptămâni —]] "
        "[[random:nu vreau să vă mai aglomerez căsuța de mail.|"
        "vă scriu ultima dată să nu vă mai bombardez cu mailuri.|"
        "preferăm să nu insistăm dacă nu mai e relevant.]]\n\n"
        "Dacă oferta nu mai e de actualitate, spuneți doar 'închide' și o "
        "scoatem din lista noastră — fără supărare, fără comentarii.\n\n"
        "Dacă încă vă interesează dar e doar timing, "
        "[[random:scrieți o dată orientativă|spuneți când să revin|"
        "spuneți-mi când vă convine să discutăm]] și revin atunci.\n\n"
        "[[random:Mulțumim pentru considerare!|"
        "Mulțumim oricum pentru atenție!|"
        "Apreciem că ne-ați considerat!]]\n\n"
        "[[%s(sig-personal)]]\n$|$",
        [],
    ),

    # op-accept — Comandă acceptată, transition la implementare
    "op-accept": (
        "[[%s(salut)]]\n\n"
        "[[random:Mulțumim pentru confirmare!|"
        "Super, mulțumim pentru OK!|"
        "Bine, mulțumim — pornim!]]\n\n"
        "Pașii următori:\n"
        " 1. Așteptăm dovada plății (printscreen ordin) la acest email.\n"
        " 2. La confirmarea plății, intrăm în producție în [[date+1wd:DD.MM]].\n"
        " 3. Estimare livrare: [[date+7wd:DD.MM]] - [[date+10wd:DD.MM]] "
        "(4-7 zile lucrătoare după producție).\n\n"
        "[[random:Pentru orice modificare la adresă sau cantitate, "
        "răspundeți cât mai curând.|"
        "Dacă apare o schimbare la adresă/cantitate, scrieți rapid aici.|"
        "Schimbări la datele comenzii? Răspundeți la acest email.]]\n\n"
        "[[%s(sig-personal)]]\n$|$",
        [],
    ),

    # op-rej — Comandă refuzată — gather feedback, leave door open
    "op-rej": (
        "[[%s(salut)]]\n\n"
        "[[random:Mulțumim pentru răspuns — înțelegem.|"
        "Mulțumim că ne-ați spus, înțelegem decizia.|"
        "Apreciem onestitatea — înțelegem.]]\n\n"
        "Dacă aveți 30 de secunde, ne ajută enorm să știm motivul "
        "(opțional — nu obligatoriu):\n"
        " - preț?\n"
        " - termen de livrare?\n"
        " - calitate ambalaj?\n"
        " - altceva?\n\n"
        "Răspunsul ne ajută să ne îmbunătățim — orice cuvânt scurt e binevenit.\n\n"
        "Pentru viitor, dacă apare o nevoie nouă pe carton ondulat, "
        "[[random:suntem aici.|reveniți oricând.|ne găsiți la aceeași adresă.]]\n\n"
        "[[%s(sig-personal)]]\n$|$",
        [],
    ),

    # proba — Mostre gratuite (door-opener)
    "proba": (
        "[[%s(salut)]]\n\n"
        "[[random:Cu plăcere, vă trimitem o mostră gratuită|"
        "Da, putem trimite mostre gratuit|"
        "Sigur, mostrele sunt gratuite]] pentru "
        "{{produs:Tip ambalaj|cutia agreată}} — fără obligație de comandă.\n\n"
        "Detalii practice:\n"
        " - Mostrele provin din surplusul de reglaj al mașinii (NU din producția "
        "specifică pentru dvs).\n"
        " - Termen de pregătire: 3-5 zile lucrătoare ([[date+5wd:DD.MM]]).\n"
        " - Livrare: cu mașinile noastre în București (gratuit) sau curier "
        "(taxa de transport în sarcina destinatarului — uzual 20-30 lei).\n\n"
        "Pentru a pregăti mostra, ne răspundeți cu:\n"
        "[[%s(reply-yn)]] și adresa de livrare.\n\n"
        "[[%s(sig-personal)]]\n$|$",
        [],
    ),

    # urg — Comandă urgentă (priority handling)
    "urg": (
        "[[%s(salut)]]\n\n"
        "[[random:Înțeleg că e urgent — putem prioritiza.|"
        "OK, urgent — încercăm să prioritizăm.|"
        "Înțeleg presiunea, prioritizăm.]]\n\n"
        "Pentru a încadra comanda în programul de azi/mâine:\n"
        " 1. Trimit proforma în următoarele 2 ore — verificați-o rapid.\n"
        " 2. La plată confirmată azi, intrăm în producție mâine "
        "([[date+1wd:DD.MM]]).\n"
        " 3. Livrare urgentă: 3-5 zile lucrătoare ([[date+5wd:DD.MM]]) cu curier "
        "rapid sau mâine ([[date+1wd:DD.MM]]) cu flota PAFF (București doar).\n\n"
        "Confirmați-mi:\n"
        " - Adresa de livrare\n"
        " - Dacă acceptăm cost suplimentar pentru curier rapid (≈15-25%)\n\n"
        "[[%s(sig-personal)]]\n$|$",
        [],
    ),

    # ret — Re-engagement client inactiv (>6 luni)
    "ret": (
        "[[%s(salut)]]\n\n"
        "Văd că nu am mai colaborat din "
        "{{ultima:Ultima dată comandă|primăvară}} — totul e bine la dvs?\n\n"
        "[[random:Pregătim oferte speciale pentru clienții recurenți —|"
        "Avem condiții speciale pentru clienții cu istoric —|"
        "Pentru parteneri vechi avem prețuri preferențiale —]] "
        "{{detaliu:Detaliu ofertă (procent, condiție)|reducere 5-10% pe a 2-a comandă din 2026}}.\n\n"
        "Dacă vă interesează, ne răspundeți cu un cuvânt scurt și trimit "
        "detaliile complete. Dacă nu, nicio supărare — rămânem la dispoziție "
        "pentru oricând.\n\n"
        "[[%s(sig-personal)]]\n$|$",
        [],
    ),
}


# ============================================================
# Layer 2 — Subject line shortcuts (ALL NEW)
# ============================================================
# Note: keys with "-" prefix to clearly distinguish from body shortcuts

SUBJECT_SHORTCUTS = {
    "subj-op": "Proformă PAFF #{{nr:Nr proformă|}}",
    "subj-mc1": "Plată confirmată — coletul intră în pregătire",
    "subj-mp1": "Plată confirmată — livrare PAFF București",
    "subj-ffd": "AWB Dragon Star — coletul a plecat",
    "subj-ffan": "AWB Fan Courier — coletul a plecat",
    "subj-nu1": "Răspuns cerere ofertă — PAFF",
    "subj-fu1": "Quick note pe oferta PAFF",
    "subj-fu3": "Să închid oferta din partea noastră?",
}


# ============================================================
# Brevity audit — shorten mp1 / mc2 PRIMARY to <125 words
# Research: Boomerang 75-100 words = 51% reply rate (peak)
# ============================================================

BREVITY_PRIMARY_REWRITES = {
    # mp1 — was 877 chars (~150 words). Compressed.
    110: (
        "[[%s(salut)]]\n\n[[%s(confirm-plata)]]\n\n"
        "Coletele pleacă spre București cu mașinile noastre. "
        "[[%s(eta-paff)]]\n\n"
        "Detalii rapide:\n"
        " - Livrare gratuită până la sediul dvs.\n"
        " - Predare la cel mai apropiat loc de parcare / curte.\n"
        " - Șoferul nu urcă în clădire (etaj/birou).\n\n"
        "Întrebări frecvente: [[var:webfaq]]\n\n[[%s(mts)]]\n$|$"
    ),
    # mc2 — was 971 chars (~165 words). Compressed.
    108: (
        "[[%s(salut)]]\n\n[[%s(confirm-plata)]]\n\n"
        "Adresa dvs. în București ne permite o opțiune mai rapidă: "
        "livrare cu mașinile noastre.\n\n"
        " 1) **PAFF** — 1-3 zile lucrătoare, gratuit, predare parcare/curte.\n"
        " 2) **Curier standard** — 4-7 zile lucrătoare, cu AWB și înfoliere.\n\n"
        "Răspundeți cu 'PAFF' sau 'curier' și pregătesc expedierea.\n\n"
        "[[%s(mts)]]\n$|$"
    ),
}


def upsert_shortcut(con: sqlite3.Connection, key: str, value: str, variants_list: list[str] | None = None):
    """Insert new or update existing shortcut by key."""
    cur = con.cursor()
    variants_json = json.dumps(variants_list or [], ensure_ascii=False)
    cur.execute(
        "INSERT INTO textsync_shortcut "
        "(key, value, content_type, updated_at, variants, usage_count) "
        "VALUES (?, ?, 'text', datetime('now'), ?, 0) "
        "ON CONFLICT(key) DO UPDATE SET "
        "value = excluded.value, variants = excluded.variants, "
        "updated_at = datetime('now');",
        (key, value, variants_json),
    )


def update_primary_only(con: sqlite3.Connection, sid: int, primary: str):
    """Update only primary value (keep existing variants intact)."""
    cur = con.cursor()
    cur.execute(
        "UPDATE textsync_shortcut "
        "SET value = ?, updated_at = datetime('now') "
        "WHERE id = ?;",
        (primary, sid),
    )


def main():
    con = sqlite3.connect(DB)
    try:
        cur = con.cursor()
        cur.execute("BEGIN;")

        print("=== Layer 1: Body shortcuts (follow-up + utility) ===")
        for key, (primary, variants) in BODY_SHORTCUTS.items():
            upsert_shortcut(con, key, primary, variants)
            print(f"  {key:<10} added/updated ({len(primary)} chars)")

        print("\n=== Layer 2: Subject line shortcuts ===")
        for key, value in SUBJECT_SHORTCUTS.items():
            upsert_shortcut(con, key, value, [])
            print(f"  {key:<10} added/updated ({len(value)} chars)")

        print("\n=== Brevity audit: shorten mp1/mc2 PRIMARY ===")
        for sid, primary in BREVITY_PRIMARY_REWRITES.items():
            update_primary_only(con, sid, primary)
            print(f"  id={sid} primary updated ({len(primary)} chars)")

        con.commit()
        print("\n✓ All committed")

        # Verify
        print("\n=== Verification ===")
        body_keys = list(BODY_SHORTCUTS.keys())
        subj_keys = list(SUBJECT_SHORTCUTS.keys())
        all_new = body_keys + subj_keys
        cur.execute(
            "SELECT key, length(value) FROM textsync_shortcut "
            "WHERE key IN ({}) ORDER BY key;".format(
                ",".join(f"'{k}'" for k in all_new)
            )
        )
        print(f"  Total new/updated shortcuts: {len(all_new)}")
        for k, vlen in cur.fetchall():
            cat = "body" if k in body_keys else "subj"
            print(f"    [{cat}] {k:<10} {vlen} chars")

        cur.execute(
            "SELECT key, length(value) FROM textsync_shortcut WHERE id IN (110, 108);"
        )
        print("\n  Brevity audit results:")
        for k, vlen in cur.fetchall():
            print(f"    {k:<10} {vlen} chars (was 877 / 971)")

        cur.execute("SELECT COUNT(*) FROM textsync_shortcut;")
        print(f"\n  Total shortcuts in DB: {cur.fetchone()[0]}")

    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
