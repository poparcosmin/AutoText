"""
Apply improved primary text + 2 variants on top body-template shortcuts.

Strategy:
  - Primary `value` = neutral/official version with safe improvements
    (diacritics, polish, CTA at end). NO factual changes (timing, names,
    prices) without explicit user confirmation.
  - `variants` JSON = [warm-tone, concise-tone] alternative bodies.
  - Extension picks uniformly across [primary, ...variants] at expand time.

Backup is the caller's responsibility (see filesystem snapshot).
"""
import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[3] / "db.sqlite3"


# id → (primary, [variant_warm, variant_concise])
UPDATES: dict[int, tuple[str, list[str]]] = {
    # mc1 — Confirmare plată curier (2.680 utilizări)
    # NOTE: păstrat "4-7 zile" în toate textele — schimbarea la 3-5 cere
    # confirmare ETA real de la user. Adăugat CTA modificare la final.
    107: (
        "Bună ziua,\n\n"
        "Vă mulțumim pentru plată.\n\n"
        "Pregătim coletele pentru expedierea prin serviciul de curierat.\n\n"
        "----------------\n\n"
        "INFORMAȚII EXPEDIERE:\n"
        " - Termenul estimat de livrare este de 4-7 zile lucrătoare.\n"
        " - Vă vom trimite numărul de AWB și factura fiscală imediat ce pachetul pleacă.\n\n"
        "----------------\n\n"
        "Pentru orice modificare la adresă sau cantitate, vă rugăm să ne răspundeți "
        "la acest email cât mai curând posibil.\n\n"
        "Vă mulțumim!",
        [
            # Cald
            "Bună ziua,\n\n"
            "Plata a intrat — mulțumim.\n\n"
            "Coletele intră astăzi în pregătire pentru expediere prin curier. "
            "În 4-7 zile lucrătoare ar trebui să ajungă la dvs., iar imediat ce "
            "pleacă din depozit vă trimitem AWB-ul și factura fiscală.\n\n"
            "Dacă apar modificări la adresă sau cantitate, scrieți-ne pe acest email "
            "cât mai repede.\n\n"
            "Mulțumim pentru încredere!",
            # Scurt
            "Bună ziua,\n\n"
            "Plata confirmată, coletele pleacă în curând prin curier "
            "(4-7 zile lucrătoare). Trimitem AWB-ul imediat ce iese din depozit.\n\n"
            "Pentru orice modificare, răspundeți la acest email.\n\n"
            "Mulțumim!",
        ],
    ),

    # ffd — Factură + AWB Dragon Star (2.738)
    91: (
        "Bună ziua,\n\n"
        "Atașăm factura fiscală pentru produsele expediate prin Dragon Star.\n\n"
        "Numărul de AWB este: \n\n"
        "Factura fiscală poate fi descărcată și din e-Factura.\n\n"
        "Pentru orice nelămurire la primire, răspundeți direct la acest email.\n\n"
        "Vă mulțumim pentru încredere!",
        [
            "Bună ziua,\n\n"
            "Coletele au plecat astăzi prin Dragon Star.\n\n"
            "AWB: \n"
            "Factură atașată (și disponibilă în e-Factura).\n\n"
            "La primire, dacă observați ceva ce nu e în regulă, scrieți-ne — "
            "rezolvăm rapid.\n\n"
            "Mulțumim!",
            "Bună ziua,\n\n"
            "AWB:  (Dragon Star)\n"
            "Factura atașată + disponibilă în e-Factura.\n\n"
            "Mulțumim!",
        ],
    ),

    # ffan — Factură + AWB Fan Courier (1.830)
    90: (
        "Bună ziua,\n\n"
        "Atașăm factura fiscală pentru produsele expediate prin Fan Courier.\n\n"
        "Numărul de AWB este: \n\n"
        "Factura fiscală poate fi descărcată și din e-Factura.\n\n"
        "Pentru orice nelămurire la primire, răspundeți direct la acest email.\n\n"
        "Vă mulțumim pentru încredere!",
        [
            "Bună ziua,\n\n"
            "Coletele au plecat astăzi prin Fan Courier.\n\n"
            "AWB: \n"
            "Factură atașată (și disponibilă în e-Factura).\n\n"
            "La primire, dacă observați ceva ce nu e în regulă, scrieți-ne — "
            "rezolvăm rapid.\n\n"
            "Mulțumim!",
            "Bună ziua,\n\n"
            "AWB:  (Fan Courier)\n"
            "Factura atașată + disponibilă în e-Factura.\n\n"
            "Mulțumim!",
        ],
    ),

    # op — Confirmare comandă + proformă (1.381)
    # NOTE: păstrat "4-7 zile" — vezi nota mc1.
    115: (
        "Bună ziua,\n\n"
        "Vă mulțumim pentru comandă! Găsiți atașată factura proformă aferentă.\n\n"
        "Vă rugăm să verificați corectitudinea comenzii (preț, cantitate și dimensiuni). "
        "Pentru a grăbi procesul de pregătire a produselor, ne puteți trimite o copie "
        "(printscreen, poză) a ordinului de plată după efectuarea transferului bancar.\n\n"
        "Produsele vor fi pregătite pentru expediere imediat după confirmarea plății. "
        "În funcție de metoda de livrare aleasă, acestea vor ajunge la dvs. în "
        "4-7 zile lucrătoare.\n\n"
        "Vă mulțumim!",
        [
            "Bună ziua,\n\n"
            "Mulțumim pentru comandă! Găsiți atașată proforma.\n\n"
            "Vă rugăm să verificați:\n"
            " - prețul, cantitatea și dimensiunile sunt cele agreate?\n"
            " - dacă da, după plată trimiteți-ne un printscreen al ordinului — "
            "accelerează start-ul producției.\n\n"
            "Pregătim imediat după confirmarea plății; ajung la dvs. în "
            "4-7 zile lucrătoare.\n\n"
            "Mulțumim!",
            "Bună ziua,\n\n"
            "Mulțumim pentru comandă. Atașat: proforma.\n\n"
            "După plată, dacă ne trimiteți printscreen-ul ordinului, începem pregătirea "
            "imediat. Livrare 4-7 zile lucrătoare.\n\n"
            "Mulțumim!",
        ],
    ),

    # mp1 — Livrare PAFF gratuit București (1.252)
    # Primary păstrat aproape ca-este (e bine scris); doar variante diferite.
    110: (
        "Bună ziua,\n\n"
        "Vă mulțumim pentru plată.\n\n"
        "Pregătim coletele pentru livrarea în București cu mașinile noastre. "
        "Astfel, beneficiați de un termen de livrare mai rapid, estimat la "
        "1-3 zile lucrătoare.\n\n"
        "----------------\n\n"
        "CONDIȚII LIVRARE PAFF (GRATUITĂ):\n\n"
        " - Livrarea se face până la sediul dumneavoastră.\n"
        " - Produsele se predau în cel mai apropiat loc de parcare sau în curtea sediului.\n"
        " - Șoferul nu poate muta coletele din mașină în incinta clădirii "
        "(ex. produse livrate la etaj sau birou).\n\n"
        "----------------\n\n"
        "Pentru detalii suplimentare, puteți consulta pagina Întrebări frecvente:\n"
        "https://www.paff.ro/intrebari-frecvente#q3\n\n"
        "Vă mulțumim!",
        [
            "Bună ziua,\n\n"
            "Plata a intrat — mulțumim!\n\n"
            "Coletele pleacă spre București cu mașinile noastre, deci ajung la dvs. "
            "în 1-3 zile lucrătoare.\n\n"
            "Câteva detalii practice:\n"
            " - livrarea e până la sediul dvs., gratuită.\n"
            " - șoferul lasă coletele la cel mai apropiat loc de parcare sau în "
            "curtea sediului.\n"
            " - nu poate urca în clădire (la etaj/birou) — pregătiți cineva la primire "
            "dacă e cazul.\n\n"
            "Detalii suplimentare: https://www.paff.ro/intrebari-frecvente#q3\n\n"
            "Mulțumim!",
            "Bună ziua,\n\n"
            "Plata confirmată, coletele pleacă spre București cu mașinile noastre "
            "(1-3 zile lucrătoare, gratuit, predare la parcare/curte).\n\n"
            "Detalii: https://www.paff.ro/intrebari-frecvente#q3\n\n"
            "Mulțumim!",
        ],
    ),

    # mr — Contact șofer Marius (4.337)
    # Adăugat: diacritice + context "flota PAFF în București"
    105: (
        "Pentru livrarea cu flota PAFF în București, șoferul nostru este Marius. "
        "Îl puteți contacta la 0756.119.864 sau 0737.642.346.",
        [
            "Pentru orice detalii legate de livrare, sunați direct pe Marius "
            "(șoferul nostru pe București): 0756.119.864 / 0737.642.346.",
            "Marius (șofer PAFF București): 0756.119.864 / 0737.642.346.",
        ],
    ),

    # pi — Contact șofer Picu (824)
    # Adăugat: diacritice + context
    114: (
        "Pentru livrarea cu flota PAFF în București, șoferul nostru este Picu "
        "(Marales Gheorghe). Îl puteți contacta la 0745 992 533.",
        [
            "Pe traseu pe București vă întâlniți cu Picu (Marales Gheorghe), "
            "șoferul nostru. Direct la el: 0745 992 533.",
            "Picu (Marales Gheorghe), șofer PAFF: 0745 992 533.",
        ],
    ),

    # ia1 — Concediu (469) — datele 2023 BUG OBVIOUS, înlocuit cu placeholder
    95: (
        "Bună ziua,\n\n"
        "Din cauza aglomerației de sezon ne vedem nevoiți să amânăm comenzile primite "
        "în perioada următoare pentru prima parte a lunii [LUNA ___].\n\n"
        "Comenzile sunt procesate în ordinea sosirii. Dacă sunteți de acord, "
        "menținem comanda activă și vă trimitem proforma imediat după revenirea "
        "din vacanță.\n\n"
        "Vă rugăm să confirmați dacă păstrăm comanda.\n\n"
        "Perioada de concediu: [DATA ÎNCEPUT] - [DATA SFÂRȘIT].\n\n"
        "Vă mulțumim pentru înțelegere și vă dorim Sărbători Liniștite!",
        [
            "Bună ziua,\n\n"
            "În perioada [___] PAFF e în concediu, iar comenzile primite acum se "
            "procesează după întoarcere — în prima parte a lunii [___].\n\n"
            "Dacă sunteți de acord, păstrăm comanda în coadă și vă trimitem proforma "
            "imediat ce reluăm activitatea. Așteptăm un OK scurt din partea dvs.\n\n"
            "Sărbători liniștite!",
            "Bună ziua,\n\n"
            "Suntem în concediu între [___] și [___]. Comanda dvs. intră în prima "
            "parte a lunii [___] — confirmați dacă o păstrăm.\n\n"
            "Mulțumim și sărbători frumoase!",
        ],
    ),

    # nu1 — Refuz (171) — adăugat diacritice + placeholder reason
    112: (
        "Bună ziua,\n\n"
        "Vă mulțumim pentru interesul acordat produselor PAFF. Din păcate, nu putem "
        "da curs cererii dumneavoastră deoarece [____].\n\n"
        "Cu stimă,\n"
        "Echipa PAFF",
        [
            "Bună ziua,\n\n"
            "Mulțumim că v-ați gândit la noi pentru [___]. Din păcate nu producem "
            "acest tip de produs — specializarea PAFF este pe ambalaje din carton "
            "ondulat.\n\n"
            "Pentru ce căutați dvs., vă putem recomanda colaboratorii noștri [___]. "
            "Spuneți-ne dacă doriți datele lor de contact.\n\n"
            "Cu stimă,\n"
            "Echipa PAFF",
            "Bună ziua,\n\n"
            "Din păcate nu putem produce [___]. Pentru acest tip de cerere, "
            "[recomandare partener / sugestie / \"ne pare rău\"].\n\n"
            "Cu stimă,\n"
            "Echipa PAFF",
        ],
    ),

    # mc2 — Up-sell București (80) — primary OK, variante alternative
    108: (
        "Bună ziua,\n\n"
        "Vă mulțumim pentru plată.\n\n"
        "Am observat că adresa dumneavoastră din București ne permite să vă oferim "
        "o opțiune de transport mai rapidă decât cea standard, folosind mașinile "
        "noastre.\n\n"
        "Vă rugăm să ne comunicați ce variantă preferați:\n\n"
        "----------------\n\n"
        "OPȚIUNEA 1: LIVRARE RAPIDĂ PAFF (RECOMANDAT)\n"
        " - Termen de livrare mai scurt (aprox. 1-3 zile lucrătoare, fără înfoliere).\n"
        " - CONDIȚII: Produsele se predau în cel mai apropiat loc de parcare sau "
        "în curtea sediului (șoferul nu poate muta coletele în incinta clădirii/la etaj).\n\n"
        "----------------\n\n"
        "OPȚIUNEA 2: LIVRARE PRIN CURIER (STANDARD)\n"
        " - Termen standard de livrare (aprox. 4-7 zile lucrătoare, cu AWB și înfoliere).\n"
        " - Condițiile de livrare sunt cele ale firmei de curierat.\n"
        " \n"
        "----------------\n\n"
        "Așteptăm răspunsul pentru a finaliza organizarea expedierii. \n\n"
        "Vă mulțumim!",
        [
            "Bună ziua,\n\n"
            "Mulțumim pentru plată!\n\n"
            "Pentru că livrarea e în București, vă putem trimite coletele cu "
            "mașinile noastre — vă scapă de costul de curier și vă scurtează "
            "termenul.\n\n"
            "Cele două variante:\n\n"
            "OPȚIUNEA 1 — LIVRARE PAFF (recomandat: rapid, gratuit)\n"
            " - 1-3 zile lucrătoare, fără înfoliere\n"
            " - șoferul predă în cel mai apropiat loc de parcare / în curtea sediului "
            "(nu urcă în clădire)\n\n"
            "OPȚIUNEA 2 — CURIER STANDARD\n"
            " - 4-7 zile lucrătoare, cu AWB și înfoliere\n"
            " - condițiile sunt cele ale firmei de curierat\n\n"
            "Care variantă preferați? Aștept un OK scurt și pregătesc expedierea.\n\n"
            "Mulțumim!",
            "Bună ziua,\n\n"
            "Plata confirmată. Pentru București vă putem trimite cu flota proprie:\n"
            " 1) PAFF: 1-3 zile, gratuit, predare la parcare/curte.\n"
            " 2) Curier: 4-7 zile, cu înfoliere și AWB.\n\n"
            "Care preferați?\n\n"
            "Mulțumim!",
        ],
    ),
}

# fb — Facturare Boxpack (118): IBAN-ul real preluat din value-ul existent.
# Tratat separat ca să evităm hard-coding-ul IBAN-ului în acest fișier.


def fmt_iban_full(value: str) -> str:
    """Extract IBAN literal from existing fb shortcut value."""
    import re

    m = re.search(r"RO\d{2}[A-Z0-9]{20}", value)
    return m.group(0) if m else "[IBAN]"


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # Load fb existing IBAN
    cur.execute("SELECT id, value FROM textsync_shortcut WHERE key = 'fb';")
    row = cur.fetchone()
    if row:
        fb_id, fb_value = row
        iban = fmt_iban_full(fb_value)
        UPDATES[fb_id] = (
            f"Facturarea se face pe firma - Boxpack SRL.\n\n"
            f"Plata se face în contul ING: {iban}",
            [
                "Pentru această comandă, facturarea se face pe firma noastră Boxpack SRL.\n\n"
                f"Cont bancar (ING):\n{iban}\n\n"
                "Beneficiar: BOXPACK SRL\n\n"
                "(IBAN-ul de mai sus se poate folosi direct, fără spații, dacă "
                "aplicația dvs. de banking nu acceptă formatul cu spații.)",
                f"Factură pe Boxpack SRL.\nIBAN ING: {iban}",
            ],
        )

    cur.execute("BEGIN;")
    try:
        for sid, (primary, variants) in UPDATES.items():
            assert isinstance(variants, list), f"variants must be list for id {sid}"
            assert len(variants) <= 3, f"max 3 variants (id {sid})"
            cur.execute(
                "UPDATE textsync_shortcut "
                "SET value = ?, variants = ?, updated_at = datetime('now') "
                "WHERE id = ?;",
                (primary, json.dumps(variants, ensure_ascii=False), sid),
            )
            print(f"  id={sid:>3} updated: primary={len(primary)} chars, "
                  f"variants={len(variants)}")
        con.commit()
    except Exception:
        con.rollback()
        raise

    print(f"\nApplied {len(UPDATES)} shortcut updates with variants.")

    # Verify
    print("\n=== Verification ===")
    keys = ("mr", "ffd", "ffan", "mc1", "op", "mp1", "pi", "ia1", "nu1", "mc2", "fb")
    for k in keys:
        cur.execute(
            "SELECT id, length(value), length(variants), "
            "json_array_length(variants) FROM textsync_shortcut WHERE key = ?;",
            (k,),
        )
        row = cur.fetchone()
        if row:
            sid, vlen, vrlen, vrcount = row
            print(f"  {k:<6} (id={sid}): primary={vlen} chars, "
                  f"variants={vrcount} entries ({vrlen} chars json)")

    con.close()


if __name__ == "__main__":
    main()
