"""python manage.py run_live: starts the live process, which holds the WebRTC
connections (live.Services.ConnectionService) for as long as it runs.

For now it only starts and waits: the internal API Django calls (offer,
answer, close) comes next and runs inside run() below. Stop it with Ctrl+C;
open connections are closed on the way out.

Runs next to the web server, not inside it: in Docker as the "live" service
(docker-compose.yml), in development from the venv in a second terminal.
"""

import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand

from live.Services.ConnectionService import ConnectionService


class Command(BaseCommand):
    help = "Run the live process: the WebRTC connections of live sessions."

    def handle(self, *args, **options):
        # The shared working folder (FILES_DIR); talk recordings go in it later.
        settings.FILES_DIR.mkdir(parents=True, exist_ok=True)
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            self.stdout.write("Live process stopped.")

    async def run(self):
        service = ConnectionService(ice_servers=settings.RTC_ICE_SERVERS)
        self.stdout.write(self.style.SUCCESS("Live process running. Ctrl+C to stop."))
        self.stdout.write(f"  ICE servers: {', '.join(service.ice_servers) or 'none'}")
        self.stdout.write(f"  Files: {settings.FILES_DIR}")
        try:
            # Until the internal API serves requests here: wait forever.
            await asyncio.Event().wait()
        finally:
            # Ctrl+C cancels the wait: close what is still open.
            for connection in list(service.connections.values()):
                await connection.close()
