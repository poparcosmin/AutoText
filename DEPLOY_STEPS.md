# 🚀 AutoText - Pași Deployment pe Server

## Status: Repository clonat pe server ✅

---

## 📍 Pasul 1: Setup Virtual Environment pe Server

```bash
# Conectează-te la server (dacă nu ești deja)
ssh user@autotext.zua.ro

# Navighează în directorul proiectului
cd /var/www/autotext  # sau unde ai clonat

# Creează virtual environment
python3 -m venv .venv

# Activează venv
source .venv/bin/activate

# Instalează dependencies
pip install -r requirements.txt

# Verifică instalarea
pip list | grep Django
```

**Verificare**: Ar trebui să vezi Django 5.2.7

---

## 📍 Pasul 2: Configurare .env pentru PRODUCȚIE

```bash
# Creează fișierul .env în root
nano .env
```

Conținut `.env` pentru **PRODUCȚIE**:
```env
# ==============================================
# AutoText - Production Configuration
# ==============================================

# Django Secret Key (IMPORTANT: Schimbă-l!)
DJANGO_SECRET_KEY=zclyrbub_ui0&q&kj!8s-*)^+i07_r5ztj*&=&xmxuvt1qcud=

# Debug mode - FALSE pentru producție
DEBUG=False

# Allowed hosts
ALLOWED_HOSTS_DEBUG=localhost,127.0.0.1
ALLOWED_HOSTS_PROD=autotext.zua.ro

# ==============================================
```

**IMPORTANT**: Poți genera SECRET_KEY nou (opțional):
```bash
source .venv/bin/activate
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
# Copiază output-ul și pune-l în .env
```

Salvează: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## 📍 Pasul 3: Database Setup

```bash
source .venv/bin/activate

# Rulează migrations
python manage.py migrate

# Verificare
python manage.py showmigrations
```

**Verificare**: Toate migrations ar trebui să aibă `[X]`

---

## 📍 Pasul 4: Creează Superuser

```bash
python manage.py createsuperuser

# Va întreba:
Username: admin
Email: admin@zua.ro
Password: [parola-sigură]
Password (again): [parola-sigură]
```

**Notează username și parola!** Vei avea nevoie pentru admin și pentru extensie.

---

## 📍 Pasul 5: Colectare Static Files

```bash
python manage.py collectstatic --noinput
```

Va crea folderul `staticfiles/` cu tot CSS/JS pentru admin.

---

## 📍 Pasul 6: Test Security Check

```bash
python manage.py check --deploy
```

**Rezultat așteptat**: `System check identified no issues (0 silenced).`

---

## 📍 Pasul 7: Setup Gunicorn

```bash
# Instalează Gunicorn în venv (dacă nu e deja)
pip install gunicorn

# Test manual că merge
gunicorn --bind 0.0.0.0:8000 config.wsgi:application

# Testează în alt terminal:
curl http://autotext.zua.ro:8000/admin/
# Ar trebui să vezi HTML
```

Dacă merge, `Ctrl+C` pentru a opri.

### Creează Gunicorn Service

```bash
sudo nano /etc/systemd/system/autotext.service
```

Conținut:
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

**IMPORTANT**: Schimbă `/var/www/autotext` cu path-ul tău real dacă e diferit!

```bash
# Dă permisiuni www-data
sudo chown -R www-data:www-data /var/www/autotext

# Reload systemd
sudo systemctl daemon-reload

# Start service
sudo systemctl start autotext

# Enable la boot
sudo systemctl enable autotext

# Verifică status
sudo systemctl status autotext
```

**Verificare**: Status ar trebui `active (running)` în verde.

---

## 📍 Pasul 8: Setup Nginx

```bash
sudo nano /etc/nginx/sites-available/autotext.zua.ro
```

Conținut:
```nginx
server {
    listen 80;
    server_name autotext.zua.ro;

    # Redirect HTTP to HTTPS (o să activăm după SSL)
    # return 301 https://$server_name$request_uri;

    # Deocamdată servește direct (pentru testare)
    location /static/ {
        alias /var/www/autotext/staticfiles/;
    }

    location / {
        proxy_pass http://unix:/var/www/autotext/autotext.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**IMPORTANT**: Schimbă path-urile dacă ai clonat în alt loc!

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/autotext.zua.ro /etc/nginx/sites-enabled/

# Test configurație
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

**Verificare**:
```bash
curl http://autotext.zua.ro/admin/
# Ar trebui să vezi HTML-ul paginii de admin
```

---

## 📍 Pasul 9: Setup SSL cu Let's Encrypt

```bash
# Instalează certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx -y

# Obține certificat SSL
sudo certbot --nginx -d autotext.zua.ro

# Va întreba:
# Email: [emailul-tau]
# Terms: Y
# Share email: N (opțional)
# Redirect HTTP to HTTPS: 2 (Yes, redirect)
```

Certbot va:
- ✅ Genera certificat SSL gratuit
- ✅ Actualiza automat nginx config cu HTTPS
- ✅ Seta redirect de la HTTP la HTTPS
- ✅ Configura auto-renewal

**Verificare**:
```bash
curl https://autotext.zua.ro/admin/
# Ar trebui să meargă pe HTTPS!
```

---

## 📍 Pasul 10: Creează Date Inițiale în Admin

```bash
# Accesează admin
# https://autotext.zua.ro/admin

# Login cu superuser creat mai devreme
```

### În Django Admin, creează:

1. **Shortcut Sets** → Add
   - Name: `birou`
   - Set Type: `General (Birou)`
   - Description: "Shortcuts generale pentru echipă"
   - **Save**

2. **Shortcuts** → Add
   - Key: `b`
   - Value: `Bună ziua,`
   - HTML Value: `<strong>Bună ziua,</strong>`
   - Sets: Selectează `birou`
   - **Save**

3. **Expiring Tokens** → Verifică
   - Ar trebui să vezi token-ul pentru superuser (creat la login)

---

## 📍 Pasul 11: Test API Endpoints

```bash
# Login și obține token
curl -X POST https://autotext.zua.ro/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "parola-ta"}' | python3 -m json.tool

# Copiază token-ul din response
TOKEN="paste-token-aici"

# Test get sets
curl https://autotext.zua.ro/api/sets/ \
  -H "Authorization: Token $TOKEN" | python3 -m json.tool

# Test get shortcuts
curl "https://autotext.zua.ro/api/shortcuts/?sets=birou" \
  -H "Authorization: Token $TOKEN" | python3 -m json.tool
```

**Verificare**: Ar trebui să vezi JSON cu seturi și shortcuts.

---

## 📍 Pasul 12: Setup Chrome Extension pentru Production

Pe **mașina ta locală** (nu pe server):

```bash
cd /home/cosmin/Work/AutoText/extension

# Editează config.js
nano config.js
```

Schimbă:
```javascript
PRODUCTION: true,  // ← Schimbă false în true
```

Salvează și:

1. `chrome://extensions/`
2. Găsește **AutoText**
3. Click **🔄 Reload**
4. Click **Options**
5. **Login** cu username/password de admin
6. Selectează set `birou`
7. Click **Save & Sync**

---

## 📍 Pasul 13: Test Final în Gmail

1. Deschide Gmail
2. Compune email nou
3. Tastează `b` + `Tab`
4. **Ar trebui să se extindă în "Bună ziua,"**

---

## ✅ DEPLOYMENT COMPLET!

### Checklist Final:

- [x] Repository clonat
- [x] Virtual environment creat
- [x] Dependencies instalate
- [x] .env configurat cu DEBUG=False
- [x] Migrations rulate
- [x] Superuser creat
- [x] Static files colectate
- [x] Gunicorn service rulează
- [x] Nginx configurat
- [x] SSL activ (HTTPS)
- [x] Admin accesibil
- [x] API funcționează
- [x] Extension conectată la production
- [x] Text expansion funcționează

---

## 🔧 Comenzi Utile pentru Monitorizare

```bash
# Status servicii
sudo systemctl status autotext
sudo systemctl status nginx

# Logs Gunicorn
sudo journalctl -u autotext -f

# Logs Nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Logs Django (dacă sunt probleme)
tail -f /var/www/autotext/logs/django.log
tail -f /var/www/autotext/logs/security.log

# Restart servicii (după modificări)
sudo systemctl restart autotext
sudo systemctl reload nginx
```

---

## 🆘 Troubleshooting

### Gunicorn nu pornește
```bash
# Verifică logs
sudo journalctl -u autotext -n 50

# Verifică permisiuni
sudo chown -R www-data:www-data /var/www/autotext

# Restart
sudo systemctl restart autotext
```

### Nginx 502 Bad Gateway
```bash
# Verifică că Gunicorn rulează
sudo systemctl status autotext

# Verifică că socket-ul există
ls -la /var/www/autotext/autotext.sock

# Verifică nginx config
sudo nginx -t
```

### API returnează 403/401
```bash
# Verifică că token-ul e valid
curl https://autotext.zua.ro/api/auth/verify/ \
  -H "Authorization: Token YOUR_TOKEN"

# Creează token nou dacă e necesar
# Din Django shell pe server:
python manage.py shell
>>> from textsync.models import ExpiringToken
>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='admin')
>>> token = ExpiringToken.objects.create(user=user)
>>> print(token.key)
```

---

## 🎯 Următorii Pași (Opțional)

1. **Adaugă mai multe seturi** (cosmin, bogdan, aura) în admin
2. **Adaugă mai multe shortcuts** pentru fiecare set
3. **Creează useri** pentru fiecare membru al echipei
4. **Distribuie extensia** echipei (ZIP sau Chrome Web Store)
5. **Setup backup** pentru db.sqlite3 (cron job zilnic)

---

**Deployment realizat cu succes! 🚀**
