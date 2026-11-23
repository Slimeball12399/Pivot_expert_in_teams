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
| `live`     | WebRTC connections of live sessions (its own process, `run_live`) |

## Development

In development you run the two Django processes yourself and only the
databases and the object store in Docker:

| Process | Command | Address |
|---|---|---|
| Web app (pages, API) | `python manage.py runserver` | http://127.0.0.1:8000/ |
| Live process (WebRTC) | `python manage.py run_live` | http://127.0.0.1:8100/ (internal API, only Django calls it) |
| Postgres, TimescaleDB, MinIO | `docker compose up db timeseries minio minio-init` | localhost:5432, 5433, 9090 |

### First time

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # Windows (cp on macOS / Linux)
```

Then in `.env`:

- set `DJANGO_SECRET_KEY` (see Notes for how to generate one);
- set `LIVE_INTERNAL_TOKEN` to something long and random: `run_live` doesn't
  start without it, and `runserver` sends it with every call to the live process;
- leave `RTC_ICE_SERVERS` empty and `RTC_RELAY_ONLY=False`: the browser reaches
  the live process on localhost directly, no STUN/TURN needed;
- leave `LIVE_INTERNAL_HOST`, `LIVE_INTERNAL_PORT`, `LIVE_INTERNAL_URL` and
  `FILES_DIR` empty (defaults: 127.0.0.1, 8100, and `Server/files` for the
  recordings both processes share);
- `S3_ENDPOINT` must be `http://localhost:9090` (Django runs outside Docker).

Start the services (with the bucket), then set up the database:

```bash
docker compose up -d db timeseries minio minio-init
```

`minio-init` creates the bucket named in `S3_BUCKET` and exits (it does
nothing if the bucket is already there). The MinIO console is at
http://localhost:9091 (log in with `MINIO_USER` / `MINIO_PASSWORD`). Then:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py seed           # optional: demo trainer, speakers and sessions
```

### Every day

Three terminals, each with the venv activated:

```bash
docker compose up db timeseries minio minio-init   # 1: databases, object store and its bucket
python manage.py runserver              # 2: the web app
python manage.py run_live               # 3: the live process
```

- App: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

`run_live` prints where it listens, the ICE servers and the files folder.
Ctrl+C stops it and closes its open connections and recordings. It doesn't
reload on code changes like `runserver` does: restart it after changing
anything in `live/`. Without it the web app still works, but the live screen
(`/sessions/<id>/live/`) can't connect.

## Common commands

```bash
python manage.py makemigrations   # after changing models
python manage.py migrate
python manage.py test
```
## Docker
```bash
docker compose up --build                              # build 
docker compose exec server python manage.py migrate    # apply database migrations
docker compose exec server python manage.py createsuperuser
docker compose down -v     # deletes the volumes, so all DB data is lost
```
Check it works: open http://localhost:8000/api/health/ 
## Notes

- The database is Postgres, in Docker also in development (see Development).
- Config comes from `.env` (loaded by `python-dotenv`). See `.env.example` for the variables. `.env` is git-ignored.
- Generate a secret key with:
  `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`
- **TODO:** API authentication isn't set up yet. The plan is token auth with DRF `TokenAuthentication` or `djangorestframework-simplejwt`.
