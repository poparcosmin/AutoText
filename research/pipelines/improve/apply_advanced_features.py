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
    # Closings — high variation
    "mts": (
        "[[random:Mulțumim!|"
        "Vă mulțumim!|"
        "Mulțumim pentru încredere!|"
        "Mulțumim mult!|"
        "Vă mulțumim pentru comandă!|"
        "Cu drag, mulțumim!]]"
    ),
    "mts_short": "Mulțumim!",
    # Confirmation: plata
    "confirm-plata": (
        "[[random:Plata din [[date:DD.MM.YYYY]] a fost confirmată — mulțumim.|"
        "Am primit plata azi, [[date:DD.MM.YYYY]]. Mulțumim!|"
        "Plata a intrat în cont — mulțumim.|"
        "Confirmăm primirea plății din [[date:DD.MM.YYYY]] — mulțumim.|"
        "Plata confirmată azi, [[date:DD.MM]] — mulțumim.|"
        "Mulțumim, plata e confirmată în contul nostru.]]"
    ),
    # Transition: ce facem după plată
    "tranzitie-pleaca": (
        "[[random:Astăzi pregătim coletele pentru curier.|"
        "Coletele intră acum în pregătire pentru expediere.|"
        "Pregătim coletele pentru expedierea prin serviciul de curierat.|"
        "Astăzi se pregătesc coletele pentru livrare.|"
        "Coletele se pregătesc imediat pentru expediere.]]"
    ),
    "tranzitie-pleaca-buc": (
        "[[random:Coletele pleacă spre București cu mașinile noastre.|"
        "Pregătim coletele pentru livrarea în București cu flota proprie.|"
        "Coletele intră astăzi în pregătire pentru livrarea cu mașinile noastre.|"
        "Astăzi pregătim livrarea în București cu mașinile PAFF.]]"
    ),
    # CTAs cu variație
    "cta-mod": (
        "[[random:Pentru orice modificare la adresă sau cantitate, răspundeți la acest email cât mai curând posibil.|"
        "Dacă apar modificări la adresă sau cantitate, scrieți-ne pe acest email cât mai repede.|"
        "Pentru schimbări la adresă sau cantitate, ne anunțați aici cât mai curând.|"
        "Dacă vreți să schimbați ceva (adresă, cantitate), răspundeți rapid la acest email.]]"
    ),
    "cta-primire": (
        "[[random:Pentru orice nelămurire la primire, răspundeți direct la acest email.|"
        "La primire, dacă observați ceva ce nu e în regulă, scrieți-ne — rezolvăm rapid.|"
        "Dacă coletele par deteriorate la primire, refuzați semnătura și scrieți-ne.|"
        "La primire, dacă există probleme cu coletele, ne anunțați aici.]]"
    ),
    # Promise: trimitem AWB
    "promise-awb": (
        "[[random:Vă trimitem numărul de AWB și factura imediat ce pachetul pleacă.|"
        "Imediat ce coletele pleacă din depozit, vă trimitem AWB-ul și factura.|"
        "Cum coletele ies din depozit, primiți de la noi AWB-ul și factura fiscală.|"
        "Vă transmitem AWB-ul și factura imediat ce pachetul iese spre livrare.]]"
    ),
    # Reply scaffolding (standardized 3-option pattern)
    "reply-yn": (
        "Răspundeți scurt:\n"
        ' ✓ "OK" → continuăm\n'
        ' ✓ "modificare: ___" → schimb ceva\n'
        ' ✓ "amân" → lăsăm în coadă'
    ),
    # ETAs — single source of truth
    "eta-curier": "Termen estimat livrare: 4-7 zile lucrătoare.",
    "eta-paff": "Termen estimat livrare: 1-3 zile lucrătoare (București).",
    # Signatures — per-user via [[var:my_name]] + [[var:my_phone]]
    "sig-personal": "Cu stimă,\n[[var:my_name]]\n[[var:my_phone]]",
    "sig-short": "Cu stimă,\n[[user]]",
    "sig-equipe": "Cu stimă,\nEchipa PAFF",
    # Tracking links per courier
    "track-fan": "Tracking: [[var:track_fan]]",
    "track-dragon": "Tracking: [[var:track_dragon]]",
    # Closing line variations (after main message body)
    "closing": (
        "[[random:Mulțumim pentru încredere!|"
        "Vă mulțumim pentru colaborare!|"
        "Mulțumim mult — rămânem la dispoziție.|"
        "Cu drag, mulțumim pentru încredere.]]"
    ),
}


# ============================================================
# 3. SHORTCUT REFACTORS — primary + 2 variants cu features
# ============================================================
# (id) → (primary, [variant_warm, variant_concise])

SHORTCUT_REFACTORS = {
    # mc1 — Confirmare plată curier (maximum variation)
    107: (
        "[[%s(salut)]]\n\n[[%s(confirm-plata)]]\n\n[[%s(tranzitie-pleaca)]]\n\n"
        "----------------\n\n"
        "INFORMAȚII EXPEDIERE:\n"
        " - [[%s(eta-curier)]]\n"
        " - [[%s(promise-awb)]]\n\n"
        "----------------\n\n"
        "[[%s(cta-mod)]]\n\n"
        "[[%s(mts)]]\n$|$",
        [
            # Cald — narrative flow
            "[[%s(salut)]]\n\n[[%s(confirm-plata)]]\n\n"
            "[[random:Coletele intră astăzi în pregătire pentru expediere prin curier.|"
            "Astăzi se pregătesc coletele pentru curier.|"
            "Pregătim astăzi coletele și le predăm curier-ului în maxim 24h.]] "
            "[[%s(eta-curier)]] [[%s(promise-awb)]]\n\n"
            "[[random:Dacă apar modificări la adresă sau cantitate, scrieți-ne pe acest email.|"
            "Pentru schimbări la adresă sau cantitate, ne anunțați aici cât mai repede.|"
            "Dacă vreți să schimbați ceva, răspundeți rapid la acest email.]]\n\n"
            "[[%s(closing)]]\n$|$",
            # Scurt — minimal
            "[[%s(salut)]]\n\n[[random:Plata confirmată azi, [[date:DD.MM]].|"
            "Plata a intrat azi, [[date:DD.MM]].|"
            "Plata e în cont — mulțumim.]] "
            "[[random:Coletele pleacă în curând prin curier (4-7 zile lucrătoare).|"
            "Coletele pleacă imediat la curier — livrare 4-7 zile lucrătoare.|"
            "Coletele se duc la curier în următoarele zile (4-7 zile lucrătoare).]]\n\n"
            "[[random:Pentru orice modificare, răspundeți la acest email.|"
            "Pentru schimbări, scrieți aici.|"
            "Modificări? Răspundeți la acest email.]]\n\n"
            "[[%s(mts)]]\n$|$",
        ],
    ),
    # ffd — Factură + AWB Dragon Star (max variation)
    91: (
        "[[%s(salut)]]\n\nAWB: $|$ (Dragon Star)\n[[%s(track-dragon)]]\n\n"
        "[[random:Atașat: factura fiscală pentru produsele expediate.|"
        "Atașăm factura fiscală pentru produsele expediate prin Dragon Star.|"
        "Factura fiscală pentru această expediere e atașată mai jos.]] "
        "Disponibilă și în e-Factura.\n\n"
        "[[%s(cta-primire)]]\n\n[[%s(closing)]]",
        [
            "[[%s(salut)]]\n\n[[random:Coletele au plecat astăzi prin Dragon Star.|"
            "Astăzi coletele au ieșit din depozit cu Dragon Star.|"
            "Coletele sunt deja la Dragon Star pentru livrare.]]\n\n"
            "AWB: $|$\n[[%s(track-dragon)]]\n"
            "[[random:Factură atașată (și disponibilă în e-Factura).|"
            "Atașăm factura fiscală — disponibilă și în e-Factura.|"
            "Factura e atașată; aceeași e și în e-Factura.]]\n\n"
            "[[%s(cta-primire)]]\n\n[[%s(mts)]]",
            "[[%s(salut)]]\n\nAWB: $|$ (Dragon Star)\n[[%s(track-dragon)]]\n"
            "[[random:Factura atașată + e-Factura.|"
            "Factură atașată; aceeași în e-Factura.|"
            "Atașat factura — disponibilă și în e-Factura.]]\n\n"
            "[[%s(mts_short)]]",
        ],
    ),
    # ffan — Factură + AWB Fan Courier (max variation)
    90: (
        "[[%s(salut)]]\n\nAWB: $|$ (Fan Courier)\n[[%s(track-fan)]]\n\n"
        "[[random:Atașat: factura fiscală pentru produsele expediate.|"
        "Atașăm factura fiscală pentru produsele expediate prin Fan Courier.|"
        "Factura fiscală pentru această expediere e atașată mai jos.]] "
        "Disponibilă și în e-Factura.\n\n"
        "[[%s(cta-primire)]]\n\n[[%s(closing)]]",
        [
            "[[%s(salut)]]\n\n[[random:Coletele au plecat astăzi prin Fan Courier.|"
            "Astăzi coletele au ieșit din depozit cu Fan Courier.|"
            "Coletele sunt deja la Fan Courier pentru livrare.]]\n\n"
            "AWB: $|$\n[[%s(track-fan)]]\n"
            "[[random:Factură atașată (și disponibilă în e-Factura).|"
            "Atașăm factura fiscală — disponibilă și în e-Factura.|"
            "Factura e atașată; aceeași e și în e-Factura.]]\n\n"
            "[[%s(cta-primire)]]\n\n[[%s(mts)]]",
            "[[%s(salut)]]\n\nAWB: $|$ (Fan Courier)\n[[%s(track-fan)]]\n"
            "[[random:Factura atașată + e-Factura.|"
            "Factură atașată; aceeași în e-Factura.|"
            "Atașat factura — disponibilă și în e-Factura.]]\n\n"
            "[[%s(mts_short)]]",
        ],
    ),
    # op — Confirmare comandă + proformă (max variation, SINGLE-CTA)
    115: (
        "[[%s(salut)]]\n\n[[random:Mulțumim pentru comandă!|Vă mulțumim pentru comandă!|"
        "Mulțumim mult pentru comandă!|Cu drag, mulțumim pentru comandă!]] "
        "[[random:Atașat: proforma|Găsiți atașată proforma|"
        "Mai jos găsiți proforma|În atașament e proforma]] {{nr:Număr proformă|}}.\n\n"
        "[[%s(reply-yn)]]\n\n"
        "[[random:După plată, producem și ajunge la dvs. în 4-7 zile lucrătoare.|"
        "După confirmarea plății, intrăm imediat în producție; livrare 4-7 zile lucrătoare.|"
        "Imediat ce confirmăm plata, începem producția. Livrare 4-7 zile lucrătoare.|"
        "Plătiți, intrăm în producție, livrăm în 4-7 zile lucrătoare.]]\n\n"
        "[[%s(mts)]]\n$|$",
        [
            # Cald — checklist verification
            "[[%s(salut)]]\n\n[[random:Mulțumim pentru comandă!|"
            "Vă mulțumim pentru comandă!|"
            "Cu drag, mulțumim pentru comandă!]] "
            "Găsiți atașată proforma {{nr:Număr proformă|}}.\n\n"
            "[[random:Vă rugăm să verificați:|Înainte de plată, verificați:|"
            "Două lucruri rapide de verificat:]]\n"
            " - prețul, cantitatea și dimensiunile sunt cele agreate?\n"
            " - dacă da, după plată trimiteți-ne un printscreen al ordinului — "
            "[[random:accelerează start-ul producției.|"
            "intrăm imediat în producție.|"
            "ne ajută să intrăm rapid în execuție.]]\n\n"
            "[[random:Pregătim imediat după confirmarea plății; ajung la dvs. în 4-7 zile lucrătoare.|"
            "Cum confirmăm plata, intrăm în producție; livrare 4-7 zile lucrătoare.|"
            "Imediat după plată producem și expediem — total 4-7 zile lucrătoare.]]\n\n"
            "[[%s(mts)]]\n$|$",
            # Scurt
            "[[%s(salut)]]\n\n[[random:Mulțumim pentru comandă.|Mulțumim mult.|"
            "Mulțumim!]] [[random:Atașat: proforma|Atașată proforma|"
            "Proformă atașată]] {{nr:Nr proformă|}}.\n\n"
            "[[random:După plată, dacă ne trimiteți printscreen al ordinului, începem pregătirea imediat.|"
            "Trimiteți-ne printscreen-ul ordinului după plată — intrăm imediat în producție.|"
            "Plată confirmată cu printscreen → producție imediată.]] Livrare 4-7 zile lucrătoare.\n\n"
            "[[%s(mts_short)]]\n$|$",
        ],
    ),
    # mp1 — Livrare PAFF gratuit București (max variation)
    110: (
        "[[%s(salut)]]\n\n[[%s(confirm-plata)]]\n\n[[%s(tranzitie-pleaca-buc)]] "
        "Astfel, [[%s(eta-paff)]]\n\n"
        "----------------\n\n"
        "[[random:CONDIȚII LIVRARE PAFF (GRATUITĂ):|DETALII LIVRARE PAFF:|"
        "DESPRE LIVRAREA NOASTRĂ:]]\n\n"
        " - [[random:Livrarea se face până la sediul dumneavoastră.|"
        "Aducem coletele la sediul dvs.|"
        "Livrarea e la sediul dvs.]]\n"
        " - [[random:Produsele se predau în cel mai apropiat loc de parcare sau în curtea sediului.|"
        "Predăm coletele la cel mai apropiat loc de parcare sau în curtea sediului.|"
        "Coletele se lasă la parcare/curte (locul cel mai apropiat).]]\n"
        " - [[random:Șoferul nu poate muta coletele din mașină în incinta clădirii.|"
        "Șoferul nu urcă coletele în clădire (etaj/birou).|"
        "Coletele rămân la mașină — nu intrăm în clădire.]]\n\n"
        "----------------\n\n"
        "[[random:Detalii suplimentare: [[var:webfaq]]|"
        "Pentru întrebări frecvente: [[var:webfaq]]|"
        "Vezi FAQ: [[var:webfaq]]]]\n\n"
        "[[%s(mts)]]\n$|$",
        [
            # Cald
            "[[%s(salut)]]\n\n[[random:Plata a intrat — mulțumim!|"
            "Plata e confirmată — mulțumim!|"
            "Plata din [[date:DD.MM]] e în cont — mulțumim!]]\n\n"
            "[[%s(tranzitie-pleaca-buc)]] [[%s(eta-paff)]]\n\n"
            "Câteva detalii practice:\n"
            " - livrarea e până la sediul dvs., gratuită.\n"
            " - șoferul lasă coletele la cel mai apropiat loc de parcare/curte.\n"
            " - nu poate urca în clădire — pregătiți cineva la primire dacă e cazul.\n\n"
            "FAQ: [[var:webfaq]]\n\n[[%s(closing)]]\n$|$",
            # Scurt
            "[[%s(salut)]]\n\n[[random:Plata confirmată|Plata a intrat|"
            "Mulțumim, plata e în cont]], [[random:coletele pleacă cu mașinile noastre|"
            "trimitem cu flota proprie|expediem cu flota PAFF]] "
            "(1-3 zile lucrătoare, gratuit, predare la parcare/curte).\n\n"
            "Detalii: [[var:webfaq]]\n\n[[%s(mts_short)]]\n$|$",
        ],
    ),
    # mr — Contact șofer Marius (max variation)
    105: (
        "[[random:Pentru livrarea cu flota PAFF în București, șoferul nostru este Marius.|"
        "Pe traseu pe București cu mașinile PAFF e Marius, șoferul nostru.|"
        "Livrarea cu flota PAFF e gestionată de Marius pe traseul București.]] "
        "[[random:Îl puteți contacta la|Sunați-l direct la|Apelați-l la]] "
        "[[var:tel_marius]] [[random:sau|/]] [[var:tel_marius_2]] "
        "[[random:(apel/WhatsApp).|(apel sau WhatsApp).|— și WhatsApp.]] "
        "[[random:Disponibil L-V 08-17.|Program: L-V 08-17.|Răspunde L-V între 08:00-17:00.]]",
        [
            "[[random:Pentru detalii livrare, sunați direct pe Marius|"
            "Marius e direct disponibil pentru detalii livrare|"
            "Pentru orice despre livrare, vorbiți direct cu Marius]] "
            "(șoferul nostru pe București): [[var:tel_marius]] / [[var:tel_marius_2]] "
            "[[random:— apel sau WhatsApp.|(apel/WhatsApp).|pe orice canal preferați.]]",
            "Marius (șofer PAFF București) — [[var:tel_marius]] / [[var:tel_marius_2]] "
            "(apel/WhatsApp, L-V 08-17).",
        ],
    ),
    # pi — Contact șofer Picu (max variation)
    114: (
        "[[random:Pentru livrarea cu flota PAFF în București, șoferul nostru este Picu (Marales Gheorghe).|"
        "Pe traseu pe București cu mașinile PAFF e Picu (Marales Gheorghe), șoferul nostru.|"
        "Livrarea cu flota PAFF pe această rută e gestionată de Picu (Marales Gheorghe).]] "
        "[[random:Îl puteți contacta la|Sunați-l direct la|Apelați-l la]] "
        "[[var:tel_picu]] [[random:(apel/WhatsApp).|(apel sau WhatsApp).|— și WhatsApp.]] "
        "[[random:Disponibil L-V 08-17.|Program: L-V 08-17.|Răspunde L-V între 08:00-17:00.]]",
        [
            "[[random:Pe traseu pe București vă întâlniți cu Picu|"
            "Cu Picu vorbiți direct dacă e ceva|"
            "Picu e omul nostru pe București]] (Marales Gheorghe), șoferul nostru. "
            "Direct la el: [[var:tel_picu]] — apel sau WhatsApp.",
            "Picu (Marales Gheorghe), șofer PAFF — [[var:tel_picu]] (apel/WhatsApp, L-V 08-17).",
        ],
    ),
    # ia1 — Concediu (max variation pe greeting + closing)
    95: (
        "[[%s(salut)]]\n\n[[random:PAFF e în concediu între|"
        "Suntem în concediu între|"
        "Echipa PAFF e în vacanță între]] "
        "{{start:Data început|22.12}} și {{end:Data sfârșit|07.01}}.\n\n"
        "[[random:Comenzile primite acum intră în coadă pentru prima parte a lunii|"
        "Comenzile sosite în această perioadă se procesează după revenire, în prima parte a lunii|"
        "Comenzile noi se rețin în coadă și intră în producție în prima parte a lunii]] "
        "{{revenire:Luna revenire|ianuarie}}, în ordinea sosirii.\n\n"
        "Răspundeți cu:\n"
        ' ✓ "păstrez" → ținem comanda activă, trimitem proforma după revenire\n'
        ' ✓ "anulez" → dezactivăm comanda\n\n'
        "[[random:Sărbători liniștite!|Vă dorim sărbători frumoase!|"
        "Vacanță plăcută și sărbători cu spor!|Sărbători cu pace și liniște!]]\n$|$",
        [
            # Cald
            "[[%s(salut)]]\n\n[[random:În perioada|Între datele|"
            "Pe perioada]] {{start:Data început|22.12}} - {{end:Data sfârșit|07.01}} "
            "[[random:PAFF e în concediu.|suntem în vacanță.|echipa PAFF e off.]]\n\n"
            "[[random:Comenzile primite acum se procesează după întoarcere|"
            "Cererile sosite acum intră în lucru după revenire|"
            "Tot ce primim acum intră în coadă pentru]] — în prima parte a lunii "
            "{{revenire:Luna revenire|ianuarie}}.\n\n"
            "[[random:Dacă sunteți de acord, păstrăm comanda în coadă și vă trimitem proforma "
            "imediat ce reluăm activitatea.|"
            "Dacă confirmați, ținem comanda activă și vă trimitem proforma imediat după concediu.|"
            "Cu acordul dvs., păstrăm comanda și revenim cu proforma după întoarcere.]] "
            "Așteptăm un OK scurt.\n\n"
            "[[random:Sărbători liniștite!|Vă dorim sărbători frumoase!|"
            "Sărbători cu pace și spor!]]\n$|$",
            # Scurt
            "[[%s(salut)]]\n\n[[random:Suntem în concediu între|"
            "PAFF e off între|"
            "Concediu între]] {{start:Început|22.12}} și {{end:Sfârșit|07.01}}. "
            "Comanda dvs. intră în prima parte a lunii {{revenire:Luna revenire|ianuarie}} — "
            "confirmați dacă o păstrăm.\n\n"
            "[[random:Mulțumim și sărbători frumoase!|"
            "Mulțumim — sărbători cu spor!|"
            "Mulțumim și vacanță plăcută!]]\n$|$",
        ],
    ),
    # nu1 — Refuz cu form placeholder + max variation pe empathy & alternative
    112: (
        "[[%s(salut)]]\n\n[[random:Mulțumim pentru interesul acordat produselor PAFF.|"
        "Mulțumim că v-ați gândit la noi.|"
        "Vă mulțumim pentru interes.|"
        "Mulțumim mult pentru interesul acordat produselor noastre.]]\n\n"
        "[[random:Din păcate, nu putem da curs cererii dumneavoastră deoarece|"
        "Din păcate, nu vă putem ajuta în acest caz —|"
        "Ne pare rău, nu reușim să acoperim această cerere —]] "
        "{{motiv:Motivul refuzului|nu intră în portofoliul nostru}}.\n\n"
        "[[%s(sig-personal)]]\n$|$",
        [
            # Cu sugestie partener + empathy
            "[[%s(salut)]]\n\n[[random:Mulțumim că v-ați gândit la noi pentru|"
            "Vă mulțumim pentru interesul acordat — pentru|"
            "Apreciem că v-ați gândit la PAFF pentru]] "
            "{{produs:Ce a cerut clientul|}}.\n\n"
            "[[random:Din păcate|Ne pare rău|Din păcate, în acest caz]] "
            "{{motiv:Motiv|nu producem acest tip de produs}} — "
            "[[random:specializarea PAFF e ambalaje carton ondulat.|"
            "noi facem doar ambalaje carton ondulat.|"
            "ne specializăm exclusiv pe carton ondulat.]]\n\n"
            "[[random:Pentru ce căutați, încercați [recomandare partener / motor căutare].|"
            "Pentru această cerere, vă putem recomanda [partener] dacă e util.|"
            "Pentru produsul respectiv, încercați [recomandare].]] "
            "[[random:Pentru cutii ondulate, suntem aici.|"
            "Pentru ambalaje carton ondulat, oricând.|"
            "Cu plăcere oricând pentru cutii carton.]]\n\n"
            "[[%s(sig-personal)]]\n$|$",
            # Scurt
            "[[%s(salut)]]\n\n[[random:Din păcate|Ne pare rău|Din păcate, în acest caz]], "
            "{{motiv:Motiv (frază completă)|nu putem da curs acestei cereri}}.\n\n"
            "[[random:Pentru acest tip de cerere|Pentru această problemă|"
            'Pentru produsul respectiv]], [recomandare partener / sugestie / "ne pare rău"].\n\n'
            "[[%s(sig-personal)]]\n$|$",
        ],
    ),
    # mc2 — Up-sell București (max variation pe framing + closing)
    108: (
        "[[%s(salut)]]\n\n[[%s(confirm-plata)]]\n\n"
        "[[random:Adresa dumneavoastră din București ne permite să vă oferim o opțiune de "
        "transport mai rapidă decât cea standard, folosind mașinile noastre.|"
        "Pentru că adresa e în București, vă putem trimite cu flota proprie — mai rapid și gratuit.|"
        "Fiind în București, avem o opțiune mai rapidă și gratuită cu mașinile noastre, "
        "dacă vă convine.]]\n\n"
        "[[random:Ce variantă preferați:|Aveți două variante:|"
        "Două opțiuni de livrare:]]\n\n"
        "----------------\n\n"
        "OPȚIUNEA 1: LIVRARE RAPIDĂ PAFF (RECOMANDAT)\n"
        " - 1-3 zile lucrătoare, fără înfoliere.\n"
        " - Predare în cel mai apropiat loc de parcare sau curtea sediului.\n\n"
        "OPȚIUNEA 2: LIVRARE PRIN CURIER (STANDARD)\n"
        " - 4-7 zile lucrătoare, cu AWB și înfoliere.\n"
        " - Condițiile firmei de curierat.\n\n"
        "----------------\n\n"
        '[[random:Răspundeți cu "PAFF" sau "curier" și pregătesc expedierea.|'
        'Spuneți-mi "PAFF" sau "curier" și pregătim expedierea.|'
        'Un cuvânt scurt — "PAFF" sau "curier" — și pregătesc totul.]]\n\n'
        "[[%s(mts)]]\n$|$",
        [
            # Cald — emphasis on benefit
            "[[%s(salut)]]\n\n[[random:Mulțumim pentru plată!|"
            "Plata e confirmată — mulțumim!|"
            "Plata din [[date:DD.MM]] a intrat — mulțumim!]]\n\n"
            "[[random:Pentru București, vă putem trimite cu mașinile noastre — vă scapă de costul "
            "curier și vă scurtează termenul.|"
            "Fiind în București, vă putem servi cu flota proprie — fără cost de curier și "
            "ajunge mai rapid.|"
            "Pentru zona dvs., flota PAFF e o opțiune mai bună: gratuit și mai rapid.]]\n\n"
            "OPȚIUNEA 1 — LIVRARE PAFF (recomandat: rapid, gratuit)\n"
            " - 1-3 zile lucrătoare, fără înfoliere\n"
            " - șoferul predă la parcare/curte (nu urcă în clădire)\n\n"
            "OPȚIUNEA 2 — CURIER STANDARD\n"
            " - 4-7 zile lucrătoare, cu AWB și înfoliere\n\n"
            "[[random:Care preferați? Aștept un OK scurt și pregătesc expedierea.|"
            "Care variantă alegeți? Pregătesc expedierea cum confirmați.|"
            "Spuneți-mi care vă convine și pregătim totul.]]\n\n[[%s(mts)]]\n$|$",
            # Scurt
            "[[%s(salut)]]\n\n[[random:Plata confirmată.|Plata a intrat.|"
            "Plata e în cont, mulțumim.]] "
            "[[random:Pentru București vă putem trimite cu flota proprie:|"
            "În București avem 2 opțiuni:|Pentru zona dvs.:]]\n"
            " 1) PAFF: 1-3 zile, gratuit, predare parcare/curte.\n"
            " 2) Curier: 4-7 zile, cu înfoliere și AWB.\n\n"
            "[[random:Care preferați?|Care variantă alegeți?|Care e ok?]]\n\n"
            "[[%s(mts_short)]]\n$|$",
        ],
    ),
    # fb — Facturare Boxpack (max variation)
    88: (
        "[[random:Facturarea se face pe firma noastră Boxpack SRL.|"
        "Pentru această comandă, factura va fi pe firma noastră Boxpack SRL.|"
        "Factura emitem pe firma Boxpack SRL.]]\n\n"
        "[[random:Plata se face în contul ING:|Cont bancar (ING):|"
        "IBAN ING:]] [[var:iban_boxpack]]\n\nBeneficiar: BOXPACK SRL",
        [
            "[[random:Pentru această comandă, facturarea se face pe firma noastră Boxpack SRL.|"
            "Factura va fi emisă pe firma Boxpack SRL pentru această comandă.|"
            "Detalii facturare: pe firma Boxpack SRL.]]\n\n"
            "Cont bancar (ING):\n[[var:iban_boxpack]]\n\n"
            "Beneficiar: BOXPACK SRL\n\n"
            "[[random:(IBAN-ul se poate folosi direct, fără spații, dacă aplicația dvs. de banking "
            "nu acceptă formatul cu spații.)|"
            "(Dacă banking-ul dvs. nu acceptă spații în IBAN, folosiți forma fără spații.)|"
            "(IBAN-ul funcționează în orice format de banking.)]]",
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
    per_user_count = sum(len(PER_USER_VARIABLES.get(uname, {})) for _, uname in users)
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
        print(
            f"  atomic snippets present: {len(atomics)} / {len(ATOMIC_SNIPPETS)} → {atomics}"
        )
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
