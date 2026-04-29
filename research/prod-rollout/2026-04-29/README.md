# PAFF AutoText — production deploy 2026-04-29

Bundle conține TOATE modificările sesiunii (engine + shortcuts + variabile + atomic snippets).

## Conținut

| File | Rol |
|---|---|
| `textsync_data.json` | Dump 137 obiecte (85 shortcuts + 48 uservariables + 4 shortcutsets), `--natural-keys` pentru portabilitate |
| `apply_to_prod.sh` | Script idempotent: migrate + truncate textsync + loaddata + sanity check |
| `verify_prod.py` | Quick check post-deploy: numără shortcuts, listează atomic snippets noi, verifică variants column |
| `README.md` | acest fișier |

## Pre-flight (ÎNAINTE de a rula pe producție)

```bash
# Pe SERVER (SSH în autotext.zua.ro):
cd /path/to/autotext  # adaptează cale

# 1. Backup DB-ul curent (CRITIC)
cp db.sqlite3 db.sqlite3.bak.before-deploy-$(date +%Y%m%d-%H%M)
ls -la db.sqlite3*  # verifică dimensiune backup

# 2. Verifică Django pornit (ar trebui să răspundă)
curl -sI http://127.0.0.1:8000/api/health/ || echo "Django down — verifică systemd"

# 3. Verifică git pull a adus codul nou (engine features)
git log --oneline -3
# Trebuie să vezi commits cu: "conditional logic", "enterprise pack", etc.
```

## Apply (pe producție)

```bash
# 1. Git pull modificări de cod (extension/content.js + lib/site-parsers.js + textsync/migrations)
git pull origin main

# 2. Rulează migrațiile noi (0008, 0009, 0010 — adaugă variants column)
.venv/bin/python manage.py migrate textsync

# 3. Aplică data dump (înlocuiește shortcuts + variabile cu cele refactorate)
chmod +x apply_to_prod.sh
./apply_to_prod.sh

# 4. Restart Django (adaptează la serviciul tău — systemd/supervisor/docker)
sudo systemctl restart autotext  # SAU: docker compose restart autotext
# SAU: kill -HUP <pid uwsgi/gunicorn>

# 5. Verificare
.venv/bin/python verify_prod.py
```

## Pe utilizatori (Aura, Bogdan, Florian)

După deploy, fiecare utilizator cu extension AutoText în Chrome:

1. Open extension popup
2. Click **Sync Now** (force fresh sync)
3. Verifică în popup: ar trebui să vezi 85 shortcuts (în loc de 62 anterior)
4. Test: tastează `mj2` în Gmail draft → ar trebui să vezi prompt-uri pentru "Procent ajustare", "Data aplicare", "Categorii afectate"

## Rollback dacă merge prost

```bash
# Pe server:
cp db.sqlite3.bak.before-deploy-* db.sqlite3
git revert <commit-hash>  # opțional, pentru cod
sudo systemctl restart autotext
```

## Ce conține deploy-ul

### Engine features noi (extension/content.js)
- `[[user]]` capitalize prima literă
- `[[recipient_first]]` prenume only
- `[[recipient_email]]` email destinatar
- `[[date+Nwd]]` working days (sare SS)
- `[[greeting]]` sezonal (15-31 dec, 1-7 ian, iul-aug)
- `[[if:LHS op RHS]]A[[else]]B[[endif]]` conditional logic

### Shortcuts noi (toate cu primary + variants + features avansate)
- 11 top body refactorate: mc1, op, ffd, ffan, mp1, mc2, mr, pi, ia1, nu1, fb
- 4 secondary: la2 (consolidat din la1/la3/la4), mj2, bc2, dx
- 8 follow-up: op-fu1, op-fu2, op-fu3, op-accept, op-rej, proba, urg, ret
- 8 subject lines: subj-op, subj-mc1, subj-mp1, subj-ffd, subj-ffan, subj-nu1, subj-fu1, subj-fu3
- 18 atomic snippets reutilizabile (salut, mts, eta-curier, sig-personal, reply-yn, etc.)
- 11 duplicate șterse (mc0, mc3, mp2, nu2, la1, la3, la4, mj1, bc1, livrare1, ia2)

### Variabile per-user (Aura/Bogdan/Cosmin/Florian)
- `my_name` + `my_phone` per utilizator → semnătură automată din `[[%s(sig-personal)]]`
- 10 variabile shared: tel_aura/marius/picu, iban_boxpack, webfaq, track_*, firma_brand
