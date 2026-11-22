"""The live process's one AudioService, CommandsService and ConnectionService,
built from settings when the process starts. The views (live/views.py) use
them; the shutdown in pivot/live_asgi.py closes them (close()).

One of each per process, so the live process must run with exactly one
uvicorn worker: a second worker would have its own, empty, connections.
"""

from django.conf import settings

from live.Services.AudioService import AudioService
from live.Services.CommandsService import CommandsService
from live.Services.ConnectionService import ConnectionService

AUDIO = AudioService(settings.FILES_DIR)
COMMANDS = CommandsService(AUDIO)
CONNECTIONS = ConnectionService(
    ice_servers=settings.RTC_ICE_SERVERS, commands=COMMANDS, audio=AUDIO,
    turn_secret=settings.TURN_SECRET, relay_only=settings.RTC_RELAY_ONLY)


async def close():
    """The process stops: close the open connections, then the recordings.
    The recordings' files stay, so their talks can go on after a restart."""
    for connection in list(CONNECTIONS.connections.values()):
        await connection.close()
    CONNECTIONS.connections.clear()
    AUDIO.close()
