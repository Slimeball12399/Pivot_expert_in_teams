# PIVOT Server

Django 6.1 + Django REST Framework backend for the PIVOT project.

## Apps

| App        | Purpose                          |
|------------|----------------------------------|
| `pivot`    | Project settings and root URLs   |
| `accounts` | Users and authentication         |
| `api`      | REST API endpoints (for the mobile app) |
| `core`     | Shared domain models and logic   |
| `web`      | Server-rendered web views        |

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # Windows (cp on macOS / Linux), then set DJANGO_SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- App: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

## Common commands

```bash
python manage.py makemigrations   # after changing models
python manage.py migrate
python manage.py test
```

## Notes

- The database is SQLite (`db.sqlite3`) for development.
- Config comes from `.env` (loaded by `python-dotenv`). See `.env.example` for the variables. `.env` is git-ignored.
- Generate a secret key with:
  `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`
- `Dockerfile` and `docker-compose.yml` are placeholders and still empty.
- **TODO:** API authentication isn't set up yet. The plan is token auth with DRF `TokenAuthentication` or `djangorestframework-simplejwt`.
