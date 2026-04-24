# 🚀 AutoText - Deployment Guide

Ghid complet pentru deployment pe `autotext.zua.ro`

---

## Quick reference (2026-04 — după migrare la uv + pyproject)

| Vechi | Nou |
|---|---|
| `python -m venv .venv && uv sync  # creează venv + instalează deps din pyproject.toml + uv.lock` | `uv sync` (creează venv automat din `pyproject.toml` + `uv.lock`) |
| `.venv/bin/python manage.py <cmd>` | `uv run python manage.py <cmd>` |
| `pip install gunicorn` | deja în dependencies; vine cu `uv sync` |
| `python manage.py test` | `uv run python manage.py test` |

Profiling opt-in (dev only):
```bash
ENABLE_SILK=True uv run python manage.py migrate  # aplică migrațiile silk
ENABLE_SILK=True uv run python manage.py runserver
# Dashboard: http://localhost:8000/silk/
```

Restul pașilor de mai jos sunt valabili — doar înlocuiește comenzile `pip install` și
`python manage.py` cu echivalentele `uv` din tabel. Tot ce ține de Gunicorn, Nginx,
SSL rămâne neschimbat.

---

## 📋 Prezentare Generală

### Arhitectură:
- **Backend Django**: `https://autotext.zua.ro` (sursa adevărului)
- **Chrome Extension**: Rulează local în browser
- **Date**: Sincronizate automat, funcționează offline

### Offline Functionality:
- ✅ Extensia salvează TOTUL în `chrome.storage.local`
- ✅ Funcționează 100% offline după prima sincronizare
- ✅ Sync automat când are internet (la fiecare 5 minute)
- ✅ Dacă serverul e down, extensia continuă cu datele vechi

---

## 🔐 Securitate - Checklist OBLIGATORIU Înainte de Deployment

### ⚠️ CRITICE - TREBUIE Rezolvate:

#### ✅ 1. SECRET_KEY Securizat
- [x] **Status**: Generat și actualizat în `.env`
- **Test**: Verifică că `.env` conține un SECRET_KEY nou (nu placeholder-ul)
- **Risc dacă ignorat**: Sesiuni, tokens, și signing compromise

#### ✅ 2. DEBUG=False în Producție
- [x] **Status**: Configurat conditional în settings.py
- **Test**: Setează `DEBUG=False` în `.env` pentru producție
- **Risc dacă ignorat**: Expune stack traces, query-uri SQL, settings către atacatori

#### ✅ 3. ALLOWED_HOSTS Configurare Corectă
- [x] **Status**: Conditional pe baza DEBUG
- **Dev**: `ALLOWED_HOSTS_DEBUG=localhost,127.0.0.1`
- **Prod**: `ALLOWED_HOSTS_PROD=autotext.zua.ro`
- **Risc dacă ignorat**: Host Header attacks

#### ✅ 4. SSL/HTTPS Enforcement
- [x] **Status**: Configurat automat când DEBUG=False
- **Setări active**:
  - `SECURE_SSL_REDIRECT = True` - forțează HTTPS
  - `SECURE_HSTS_SECONDS = 31536000` - HSTS 1 an
  - `SESSION_COOKIE_SECURE = True` - cookies doar pe HTTPS
  - `CSRF_COOKIE_SECURE = True` - CSRF protection pe HTTPS
- **Risc dacă ignorat**: Token-uri interceptate, man-in-the-middle attacks

#### ✅ 5. Rate Limiting Activ
- [x] **Status**: Configurat în REST_FRAMEWORK
- **Limite**:
  - Anonymous: 100 requests/oră
  - Authenticated: 1000 requests/oră
- **Risc dacă ignorat**: Brute force attacks pe autentificare

#### ✅ 6. CORS Restrâns
- [x] **Status**: Headers specifice (nu wildcard)
- **Allowed origins**: Doar localhost (dev) și autotext.zua.ro (prod)
- **Risc dacă ignorat**: Cross-origin attacks

#### ✅ 7. Logging pentru Security Events
- [x] **Status**: Configurat în settings.py
- **Log files**:
  - `logs/django.log` - general warnings/errors
  - `logs/security.log` - security-specific events
- **Test**: Verifică că directorul `logs/` există

### 📝 Checklist Final Înainte de Deployment:

```bash
# Pe mașina locală, verifică configurația:

# 1. Verifică .env pentru producție
cat .env
# Trebuie să conțină:
# - DJANGO_SECRET_KEY=<long-random-string>
# - DEBUG=False
# - ALLOWED_HOSTS_PROD=autotext.zua.ro

# 2. Test cu DEBUG=False local
DEBUG=False python manage.py check --deploy

# 3. Verifică că logs/ directory există
ls -la logs/

# 4. Test collectstatic
python manage.py collectstatic --noinput

# 5. Verifică .gitignore conține:
# - .env
# - logs/
# - db.sqlite3
# - staticfiles/
```

### 🔒 Recomandări Suplimentare (Opționale):

#### PostgreSQL pentru Producție
- **Status**: Opțional (SQLite OK pentru trafic mic/mediu)
- **Când trebuie**: Dacă > 100 utilizatori concurrent
- **Setup**: Editează `DATABASES` în settings.py și instalează `psycopg2`

#### Backup Regulat
```bash
# Backup database (zilnic)
cp /var/www/autotext/db.sqlite3 /backups/db_$(date +%Y%m%d).sqlite3

# Backup .env (păstrează în siguranță)
```

#### Monitorizare Logs
```bash
# Monitorizează security events
tail -f /var/www/autotext/logs/security.log

# Alert la erori critice (setup cu cron)
grep "ERROR" /var/www/autotext/logs/django.log | mail -s "AutoText Errors" admin@zua.ro
```

### 🎯 Quick Security Test După Deployment:

```bash
# Test 1: Verifică HTTPS redirect
curl -I http://autotext.zua.ro
# Trebuie să returneze: 301 redirect la https://

# Test 2: Verifică HSTS header
curl -I https://autotext.zua.ro
# Trebuie să conțină: Strict-Transport-Security

# Test 3: Test rate limiting
# Rulează > 100 requests rapid fără auth
# Trebuie să returneze: 429 Too Many Requests

# Test 4: Verifică că DEBUG=False
curl https://autotext.zua.ro/api/invalid-endpoint
# NU trebuie să afișeze stack trace detaliat
```

---

## 🔧 Part 1: Deployment Backend (autotext.zua.ro)

### Pregătire Locală:

#### 1. Generează SECRET_KEY Nou
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Copiază key-ul generat.

#### 2. Actualizează .env pentru Producție
Editează `/home/cosmin/Work/AutoText/.env`:

```env
DJANGO_SECRET_KEY=<paste-generated-key-here>
DEBUG=False
ALLOWED_HOSTS_DEBUG=localhost,127.0.0.1
ALLOWED_HOSTS_PROD=autotext.zua.ro
```

**Notă**: Settings.py alege automat între `ALLOWED_HOSTS_DEBUG` și `ALLOWED_HOSTS_PROD` pe baza valorii `DEBUG`.

#### 3. Colectează Static Files
```bash
cd /home/cosmin/Work/AutoText
source .venv/bin/activate
python manage.py collectstatic --noinput
```

Creează folderul `staticfiles/` cu toate fișierele statice.

---

### Pe Server (autotext.zua.ro):

#### 1. Transferă Codul
```bash
# De pe mașina locală, transferă proiectul:
scp -r /home/cosmin/Work/AutoText user@autotext.zua.ro:/var/www/autotext/
```

Sau folosește git:
```bash
# Pe server:
cd /var/www/
git clone <repository-url> autotext
cd autotext
```

#### 2. Setup Virtual Environment
```bash
cd /var/www/autotext
python3 -m venv .venv
source .venv/bin/activate
uv sync  # creează venv + instalează deps din pyproject.toml + uv.lock
```

#### 3. Configurează .env pe Server
Creează `/var/www/autotext/.env`:
```env
DJANGO_SECRET_KEY=<secret-key-from-step-1>
DEBUG=False
ALLOWED_HOSTS_DEBUG=localhost,127.0.0.1
ALLOWED_HOSTS_PROD=autotext.zua.ro
```

**IMPORTANT**: Cu `DEBUG=False`, Django va folosi automat `ALLOWED_HOSTS_PROD`.

#### 4. Database Setup
```bash
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
```

#### 5. Creează Superuser
```bash
python manage.py createsuperuser
# Username: admin
# Email: admin@zua.ro
# Password: <choose-secure-password>
```

#### 6. Import Data
```bash
# Transfer database from local (cu date existente)
scp /home/cosmin/Work/AutoText/db.sqlite3 user@autotext.zua.ro:/var/www/autotext/

# SAU creează manual seturile și shortcuts-urile în admin
```

---

### Setup Gunicorn + Nginx:

#### 7. Instalează Gunicorn
```bash
source .venv/bin/activate
pip install gunicorn
```

#### 8. Creează Gunicorn Service
Creează `/etc/systemd/system/autotext.service`:

```ini
[Unit]
Description=AutoText Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/autotext
Environment="PATH=/var/www/autotext/.venv/bin"
ExecStart=/var/www/autotext/.venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/var/www/autotext/autotext.sock \
    config.wsgi:application

[Install]
WantedBy=multi-user.target
```

#### 9. Start Gunicorn
```bash
sudo systemctl start autotext
sudo systemctl enable autotext
sudo systemctl status autotext  # Verifică că rulează
```

#### 10. Configurează Nginx
Creează `/etc/nginx/sites-available/autotext.zua.ro`:

```nginx
server {
    listen 80;
    server_name autotext.zua.ro;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name autotext.zua.ro;

    # SSL Certificate (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/autotext.zua.ro/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/autotext.zua.ro/privkey.pem;

    # Static files
    location /static/ {
        alias /var/www/autotext/staticfiles/;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://unix:/var/www/autotext/autotext.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 11. Enable Site & Restart Nginx
```bash
sudo ln -s /etc/nginx/sites-available/autotext.zua.ro /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

#### 12. Setup SSL (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d autotext.zua.ro
```

---

### Test Backend:

```bash
# Test API
curl https://autotext.zua.ro/api/sets/ \
  -H "Authorization: Token YOUR_TOKEN_HERE"

# Should return: JSON with sets
```

✅ **Backend deployment complet!**

---

## 🎨 Part 2: Update Chrome Extension

### Actualizare pentru Producție - SIMPLU!

#### 1. Editează extension/config.js - Schimbă UN SINGUR FLAG:
```javascript
const CONFIG = {
  // DEVELOPMENT → PRODUCTION: Schimbă false în true
  PRODUCTION: true,  // ← DOAR SCHIMBĂ ASTA!

  API_URL_DEV: 'http://localhost:8000/api',
  API_URL_PROD: 'https://autotext.zua.ro/api',
  DEV_TOKEN: '4bedda61f31040c3776258bcd33b2a59ec51db06'
};
```

**Gata! Extensia va folosi automat URL-ul de producție.**

#### 2. Reîncarcă Extensia în Chrome
1. `chrome://extensions/`
2. Găsește AutoText
3. Click **🔄** (reload)

#### 3. Verifică Sync
1. Click dreapta pe icon → **Options**
2. Ar trebui să vadă seturile de pe server
3. Selectează seturi și click **Save & Sync**

#### 4. Test în Gmail
- Tastează `b` + Tab → ar trebui să funcționeze!

✅ **Extensia conectată la producție!**

---

## 🔐 Setup Token per Utilizator (Opțional)

Pentru fiecare utilizator nou:

### 1. Creează User în Django Admin
```
https://autotext.zua.ro/admin
→ Users → Add User
```

### 2. Generează Token
În Django shell sau admin:
```python
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

user = User.objects.get(username='cosmin')
token, created = Token.objects.get_or_create(user=user)
print(f"Token for {user.username}: {token.key}")
```

### 3. User Setează Token în Extensie
În service worker Console:
```javascript
chrome.storage.local.set({
  auth_token: 'TOKEN_AICI'
}, () => console.log('Token setat!'));
```

---

## 📦 Distribuire Extensie

### Opțiunea A: Manual (Pentru Echipă Internă)

**1. Creează ZIP:**
```bash
cd /home/cosmin/Work/AutoText
zip -r autotext-extension.zip extension/
```

**2. Distribuie ZIP echipei**

**3. Fiecare member:**
- Deschide `chrome://extensions/`
- Enable Developer mode
- Dezarhivează ZIP
- Load unpacked → selectează folderul `extension/`

### Opțiunea B: Chrome Web Store (Public/Private)

**1. Pregătește pentru Store:**
- Adaugă icon-uri (deja ai)
- Verifică manifest.json
- Test complet

**2. Package:**
```bash
cd extension
zip -r ../autotext-extension.zip ./*
```

**3. Upload la Chrome Web Store:**
- https://chrome.google.com/webstore/devconsole
- One-time fee: $5
- Upload ZIP
- Completează detalii
- Publish (public sau unlisted pentru echipă)

---

## 🔄 Workflow Update Shortcuts

### Admin Workflow:
1. Django Admin → `https://autotext.zua.ro/admin`
2. Shortcuts → Add/Edit
3. Setează în ce seturi apare
4. Save

### User-side:
- Extensia sincronizează automat în max 5 minute
- SAU forțează sync: Options → **Sync Now**
- Funcționează offline cu date salvate local

---

## 🧪 Testing Checklist

### Backend:
- [ ] Server pornit și rulează
- [ ] SSL funcționează (https://)
- [ ] API returnează seturi: `/api/sets/`
- [ ] API returnează shortcuts: `/api/shortcuts/?sets=birou`
- [ ] Django Admin accesibil
- [ ] Token authentication funcționează

### Extension:
- [ ] URL actualizat în config.js
- [ ] Options page afișează seturi de pe server
- [ ] Sync funcționează
- [ ] Test `b` + Tab în Gmail → funcționează
- [ ] Test `pc` + Tab → funcționează
- [ ] Conflict resolution (personal > general) funcționează
- [ ] Funcționează offline (după sync)

---

## 🔍 Troubleshooting

### Backend Issues:

**Error: DisallowedHost**
- Verifică `ALLOWED_HOSTS` în .env
- Restart Gunicorn: `sudo systemctl restart autotext`

**API returnează 403/401**
- Verifică token-ul de autentificare
- Verifică permission classes în views.py

**CORS errors în Chrome**
- Verifică `CORS_ALLOWED_ORIGINS` în settings.py
- Include `https://autotext.zua.ro`

### Extension Issues:

**Nu se conectează la server**
- Verifică URL în config.js
- Verifică că serverul rulează
- Check Console pentru erori (F12)

**Sync failed**
- Verifică token în storage
- Service worker Console → verifică log-uri
- Test API manual cu curl

---

## 📊 Monitorizare

### Check Server Status:
```bash
sudo systemctl status autotext
sudo systemctl status nginx
```

### Check Logs:
```bash
# Gunicorn logs
sudo journalctl -u autotext -f

# Nginx logs
tail -f /var/log/nginx/error.log
tail -f /var/log/nginx/access.log
```

---

## 🎯 Rezultat Final

**Backend:**
- ✅ Django pe `https://autotext.zua.ro`
- ✅ API complet funcțional
- ✅ Admin pentru management
- ✅ SSL secure
- ✅ Multi-set support

**Extension:**
- ✅ Conectată la autotext.zua.ro
- ✅ Funcționează offline
- ✅ Sync automat la 5 minute
- ✅ Options page pentru selectare seturi
- ✅ Conflict resolution (personal > general)

**Users:**
- ✅ Selectează seturile lor (birou + personal)
- ✅ Text expansion instant
- ✅ Funcționează oriunde (Gmail, Google, orice site)
- ✅ Offline-first - nu depind de server

---

**Deployment complet! 🚀**

Pentru întrebări sau probleme, vezi [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
