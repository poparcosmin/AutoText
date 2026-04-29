-- ============================================================
-- 2026-04-29: 22 variante noi pentru top 11 body templates
-- Backup ÎNTÂI, apoi INSERT-uri în ordine.
-- Niciun UPDATE pe textele existente — adaugă entry-uri noi.
-- ============================================================

CREATE TABLE IF NOT EXISTS textsync_shortcut_backup_20260429_v3 AS
  SELECT * FROM textsync_shortcut;

-- 1. mc1b, mc1c — variante mc1 (Confirmare plată curier)
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
VALUES
  ('mc1b', 'Bună ziua,

Plata a intrat — mulțumim.

Coletele intră astăzi în pregătire pentru expediere prin curier. În 3-5 zile lucrătoare ar trebui să ajungă la dvs., iar imediat ce pleacă din depozit vă trimitem AWB-ul și factura fiscală.

Dacă apar modificări la adresă sau cantitate, scrieți-ne pe acest email cât mai repede.

Mulțumim pentru încredere!', 'text', datetime('now')),
  ('mc1c', 'Bună ziua,

Plata confirmată, coletele pleacă astăzi/mâine prin curier (3-5 zile lucrătoare). Trimitem AWB-ul imediat ce iese din depozit.

Pentru orice modificare, răspundeți la acest email.

Mulțumim!', 'text', datetime('now'));

-- 2. ffdb, ffdc — variante ffd (Factură + AWB Dragon Star)
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
VALUES
  ('ffdb', 'Bună ziua,

Coletele au plecat astăzi prin Dragon Star.

AWB: ___
Factură atașată (și disponibilă în e-Factura).

La primire, dacă observați ceva ce nu e în regulă, scrieți-ne — rezolvăm rapid.

Mulțumim!', 'text', datetime('now')),
  ('ffdc', 'Bună ziua,

AWB: ___ (Dragon Star)
Factura atașată + disponibilă în e-Factura.

Mulțumim!', 'text', datetime('now'));

-- 3. ffanb, ffanc — variante ffan (Factură + AWB Fan Courier)
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
VALUES
  ('ffanb', 'Bună ziua,

Coletele au plecat astăzi prin Fan Courier.

AWB: ___
Factură atașată (și disponibilă în e-Factura).

La primire, dacă observați ceva ce nu e în regulă, scrieți-ne — rezolvăm rapid.

Mulțumim!', 'text', datetime('now')),
  ('ffanc', 'Bună ziua,

AWB: ___ (Fan Courier)
Factura atașată + disponibilă în e-Factura.

Mulțumim!', 'text', datetime('now'));

-- 4. opb, opc — variante op (Confirmare comandă + proformă)
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
VALUES
  ('opb', 'Bună ziua,

Mulțumim pentru comandă! Găsiți atașată proforma.

Vă rugăm să verificați:
 - prețul, cantitatea și dimensiunile sunt cele agreate?
 - dacă da, după plată trimiteți-ne un printscreen al ordinului — accelerează start-ul producției.

Pregătim imediat după confirmarea plății; ajung la dvs. în 3-5 zile lucrătoare.

Mulțumim!', 'text', datetime('now')),
  ('opc', 'Bună ziua,

Mulțumim pentru comandă. Atașat: proforma.

După plată, dacă ne trimiteți printscreen-ul ordinului, începem pregătirea imediat. Livrare 3-5 zile lucrătoare.

Mulțumim!', 'text', datetime('now'));

-- 5. mp1b, mp1c — variante mp1 (Livrare PAFF gratuită București)
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
VALUES
  ('mp1b', 'Bună ziua,

Plata a intrat — mulțumim!

Coletele pleacă spre București cu mașinile noastre, deci ajung la dvs. în 1-3 zile lucrătoare.

Câteva detalii practice:
 - livrarea e până la sediul dvs., gratuită.
 - șoferul lasă coletele la cel mai apropiat loc de parcare sau în curtea sediului.
 - nu poate urca în clădire (la etaj/birou) — pregătiți cineva la primire dacă e cazul.

Detalii suplimentare: https://www.paff.ro/intrebari-frecvente#q3

Mulțumim!', 'text', datetime('now')),
  ('mp1c', 'Bună ziua,

Plata confirmată, coletele pleacă spre București cu mașinile noastre (1-3 zile lucrătoare, gratuit, până la parcare/curte).

Detalii: https://www.paff.ro/intrebari-frecvente#q3

Mulțumim!', 'text', datetime('now'));

-- 6. mrb, mrc — variante mr (Contact șofer Marius)
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
VALUES
  ('mrb', 'Pentru orice detalii legate de livrare, sună direct pe Marius (șoferul nostru pe București): 0756.119.864 / 0737.642.346.', 'text', datetime('now')),
  ('mrc', 'Marius (șofer PAFF București): 0756.119.864 / 0737.642.346.', 'text', datetime('now'));

-- 7. pib, pic — variante pi (Contact șofer Picu)
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
VALUES
  ('pib', 'Pe traseu pe București vă întâlniți cu Picu (Marales Gheorghe), șoferul nostru. Direct la el: 0745 992 533.', 'text', datetime('now')),
  ('pic', 'Picu (Marales Gheorghe), șofer PAFF: 0745 992 533.', 'text', datetime('now'));

-- 8. ia1b, ia1c — variante ia1 (Concediu)
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
VALUES
  ('ia1b', 'Bună ziua,

În perioada [___] PAFF e în concediu, iar comenzile primite acum se procesează după întoarcere — în prima parte a lunii [___].

Dacă sunteți de acord, păstrăm comanda în coadă și vă trimitem proforma imediat ce reluăm activitatea. Așteptăm un OK scurt din partea dvs.

Sărbători liniștite!', 'text', datetime('now')),
  ('ia1c', 'Bună ziua,

Suntem în concediu între [___] și [___]. Comanda dvs. intră în prima parte a lunii [___] — confirmați dacă o păstrăm.

Mulțumim și sărbători frumoase!', 'text', datetime('now'));

-- 9. nu1b, nu1c — variante nu1 (Refuz)
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
VALUES
  ('nu1b', 'Bună ziua,

Mulțumim că v-ați gândit la noi pentru [___]. Din păcate nu producem acest tip de produs — specializarea PAFF este pe ambalaje din carton ondulat.

Pentru ce căutați dvs., vă putem recomanda colaboratorii noștri [___]. Spuneți-ne dacă doriți datele lor de contact.

Cu stimă,
Echipa PAFF', 'text', datetime('now')),
  ('nu1c', 'Bună ziua,

Din păcate nu putem produce [___]. Pentru acest tip de cerere, [recomandare partener / sugestie / "ne pare rău"].

Cu stimă,
Echipa PAFF', 'text', datetime('now'));

-- 10. mc2b, mc2c — variante mc2 (Up-sell București RAPID)
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
VALUES
  ('mc2b', 'Bună ziua,

Mulțumim pentru plată!

Pentru că livrarea e în București, vă putem trimite coletele cu mașinile noastre — vă scapă de costul de curier și vă scurtează termenul.

Cele două variante:

OPȚIUNEA 1 — LIVRARE PAFF (recomandat: rapid, gratuit)
 - 1-3 zile lucrătoare, fără înfoliere
 - șoferul predă în cel mai apropiat loc de parcare / în curtea sediului (nu urcă în clădire)

OPȚIUNEA 2 — CURIER STANDARD
 - 3-5 zile lucrătoare, cu AWB și înfoliere
 - condițiile sunt cele ale firmei de curierat

Care variantă preferați? Aștept un OK scurt și pregătesc expedierea.

Mulțumim!', 'text', datetime('now')),
  ('mc2c', 'Bună ziua,

Plata confirmată. Pentru București vă putem trimite cu flota proprie:
 1) PAFF: 1-3 zile, gratuit, predare la parcare/curte.
 2) Curier: 3-5 zile, cu înfoliere și AWB.

Care preferați?

Mulțumim!', 'text', datetime('now'));

-- 11. fbb, fbc — variante fb (Facturare Boxpack)
-- IBAN-ul real e în shortcut-ul `fb` existent; derivăm variantele din el
-- pentru a evita duplicarea identifier-ului bancar în repository.
INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
SELECT
  'fbb',
  'Pentru această comandă, facturarea se face pe firma noastră Boxpack SRL.

Cont bancar (ING):
' || trim(substr(value, instr(value, 'RO'))) || '

Beneficiar: BOXPACK SRL

(IBAN-ul de mai sus se poate folosi direct, fără spații, dacă aplicația dvs. de banking nu acceptă formatul cu spații.)',
  'text',
  datetime('now')
FROM textsync_shortcut WHERE key = 'fb';

INSERT INTO textsync_shortcut (key, value, content_type, updated_at)
SELECT
  'fbc',
  'Factură pe Boxpack SRL.
IBAN ING: ' || trim(substr(value, instr(value, 'RO'))),
  'text',
  datetime('now')
FROM textsync_shortcut WHERE key = 'fb';

-- ============================================================
-- VERIFY — listează cele 22 scurtături noi
-- ============================================================
SELECT id, key, length(value) AS chars, substr(replace(value, char(10), ' '), 1, 70) AS preview
FROM textsync_shortcut
WHERE key IN (
  'mc1b','mc1c','ffdb','ffdc','ffanb','ffanc','opb','opc',
  'mp1b','mp1c','mrb','mrc','pib','pic','ia1b','ia1c',
  'nu1b','nu1c','mc2b','mc2c','fbb','fbc'
)
ORDER BY key;
