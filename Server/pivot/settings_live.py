"""Settings of the live process: the normal ones (pivot/settings.py, the same
.env), with only the live app's internal API as URLs (live/urls.py) and no
middleware. Nothing here is for browsers: no sessions, CSRF or logins; the
views check the internal token themselves.

Used by pivot/live_asgi.py, which python manage.py run_live and the "live"
service in docker-compose.yml start.
"""

from .settings import *  # noqa: F401,F403

ROOT_URLCONF = "live.urls"
MIDDLEWARE = []
