# AutoText - Text Expansion System

A seamless text expansion system with a Django backend API and Chrome extension. Type shortcuts and press Tab to expand them into full text snippets.

## Features

- **Text Expansion**: Type a shortcut (e.g., `//sig`) and press Tab to expand it
- **Rich Text Support**: Shortcuts can contain HTML formatting
- **Shortcut Sets**: Organize shortcuts into sets (Global, Team, Personal)
- **Team Sharing**: Share shortcut sets with team members via `visible_to` permissions
- **Sync Across Devices**: Shortcuts sync from the server to all your browsers
- **Usage Analytics**: Track which shortcuts are used most frequently
- **Offline Support**: Cached shortcuts work even when offline

## Architecture

```
AutoText/
├── config/              # Django project settings
├── textsync/            # Django app - API backend
│   ├── models.py        # ExpiringToken, ShortcutSet, Shortcut, ShortcutUsageLog
│   ├── views.py         # REST API viewsets
│   ├── serializers.py   # DRF serializers
│   ├── authentication.py # Custom token auth with 180-day expiration
│   └── admin.py         # Django admin configuration
└── extension/           # Chrome extension (Manifest V3)
    ├── background.js    # Service worker for sync
    ├── content.js       # Injected script for text expansion
    ├── popup.html/js    # Quick actions popup
    └── options.html/js  # Settings and shortcut management
```

## Tech Stack

**Backend:**
- Django 5.2 with Django REST Framework
- SQLite database (easily switchable to PostgreSQL)
- Redis for caching
- Gunicorn for production deployment
- structlog for structured logging

**Extension:**
- Chrome Extension Manifest V3
- Vanilla JavaScript (no framework dependencies)
- Chrome Storage API for local caching

## Quick Start

### Backend Setup

1. **Clone and install dependencies:**
   ```bash
   cd AutoText
   uv sync
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser:**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run development server:**
   ```bash
   python manage.py runserver
   ```

### Chrome Extension Setup

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `extension/` directory
5. Open extension options and log in with your credentials

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health/` | GET | Health check |
| `/api/auth/login/` | POST | Login and get token |
| `/api/auth/logout/` | POST | Invalidate token |
| `/api/auth/verify/` | POST | Verify token validity |
| `/api/auth/refresh/` | POST | Refresh expiring token |
| `/api/sets/` | GET | List shortcut sets |
| `/api/shortcuts/` | GET | List all accessible shortcuts |
| `/api/shortcuts/my/` | GET | List user's own shortcuts |
| `/api/sync/bulk/` | POST | Bulk sync operation |
| `/api/track-usage/` | POST | Track shortcut usage |

## Shortcut Set Types

- **Global**: Visible to all authenticated users
- **Team**: Visible to owner + specified users via `visible_to`
- **Personal**: Visible only to the owner

## Keyboard Shortcuts (Extension)

| Shortcut | Action |
|----------|--------|
| `Alt+Shift+S` | Sync shortcuts from server |
| `Alt+Shift+A` | Toggle AutoText on/off |
| `Alt+Shift+O` | Open options page |
| `Alt+Shift+T` | Open popup |

## Development

### Running Tests

```bash
python manage.py test textsync
```

### Admin Interface

Access Django admin at `/admin/` to manage:
- Users and tokens
- Shortcut sets and shortcuts
- Usage analytics

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed production deployment instructions including:
- Gunicorn configuration
- Nginx reverse proxy setup
- SSL/TLS with Let's Encrypt
- Systemd service configuration

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_SECRET_KEY` | Django secret key | `dev-secret-key-...` |
| `DEBUG` | Debug mode | `True` |
| `ALLOWED_HOSTS_DEBUG` | Debug hosts | `localhost,127.0.0.1` |
| `ALLOWED_HOSTS_PROD` | Production hosts | `autotext.zua.ro` |
| `REDIS_URL` | Redis connection URL | `redis://127.0.0.1:6379/1` |
| `APP_VERSION` | Application version | `1.0.0` |

## License

Private - All rights reserved.
