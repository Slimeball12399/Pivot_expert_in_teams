"""ASGI entry point of the live process: the live app's internal API with
pivot/settings_live.py, plus what Django doesn't do for an ASGI app: checking
the live settings at startup and closing the connections and recordings at
shutdown (uvicorn's "lifespan" messages).

Run with exactly one worker (the connections live in this process's memory):
python manage.py run_live does that, and so does the "live" service in
docker-compose.yml:

  python -m uvicorn pivot.live_asgi:application --host 0.0.0.0 --port 8100 --workers 1
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pivot.settings_live")

django_application = get_asgi_application()

# After Django is set up: builds the services from settings.
from django.conf import settings  # noqa: E402
from django.core.exceptions import ImproperlyConfigured  # noqa: E402

from live import runtime  # noqa: E402


async def application(scope, receive, send):
    """Django for the requests; startup and shutdown here."""
    if scope["type"] != "lifespan":
        await django_application(scope, receive, send)
        return
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            try:
                if not settings.LIVE_INTERNAL_TOKEN:
                    raise ImproperlyConfigured(
                        "Set LIVE_INTERNAL_TOKEN in .env: Django needs it to call the live process.")
                if settings.RTC_RELAY_ONLY and not (settings.TURN_SECRET and any(
                        url.startswith(("turn:", "turns:")) for url in settings.RTC_ICE_SERVERS)):
                    raise ImproperlyConfigured(
                        "RTC_RELAY_ONLY needs a turn: URL in RTC_ICE_SERVERS and TURN_SECRET:"
                        " without them nothing could connect.")
                # The shared working folder (FILES_DIR); the recordings go in it.
                settings.FILES_DIR.mkdir(parents=True, exist_ok=True)
            except Exception as error:
                await send({"type": "lifespan.startup.failed", "message": str(error)})
                return
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await runtime.close()
            await send({"type": "lifespan.shutdown.complete"})
            return
