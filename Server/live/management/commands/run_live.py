"""python manage.py run_live: starts the live process in development, which
holds the WebRTC connections and serves the internal API Django calls
(live/views.py), on LIVE_INTERNAL_HOST and LIVE_INTERNAL_PORT.

It runs uvicorn with pivot/live_asgi.py (its own settings, pivot/settings_live.py,
and exactly one worker) in a process of its own: this command's process is
already set up with the web settings and can't switch. Ctrl+C stops both;
open connections and recordings are closed on the way out (live_asgi).

In Docker the "live" service starts the same uvicorn command directly.
"""

import os
import subprocess
import sys

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the live process: the WebRTC connections of live sessions."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            f"Live process on http://{settings.LIVE_INTERNAL_HOST}:{settings.LIVE_INTERNAL_PORT}."
            " Ctrl+C to stop."))
        self.stdout.write(f"  ICE servers: {', '.join(settings.RTC_ICE_SERVERS) or 'none'}"
                          f"{' (relay only)' if settings.RTC_RELAY_ONLY else ''}")
        self.stdout.write(f"  Files: {settings.FILES_DIR}")
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "pivot.live_asgi:application",
             "--host", settings.LIVE_INTERNAL_HOST, "--port", str(settings.LIVE_INTERNAL_PORT),
             "--workers", "1", "--lifespan", "on"],
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "pivot.settings_live"})
        try:
            process.wait()
        except KeyboardInterrupt:
            # uvicorn got the Ctrl+C too and shuts down by itself (closing the
            # connections and recordings): wait for it to finish.
            process.wait()
            self.stdout.write("Live process stopped.")
