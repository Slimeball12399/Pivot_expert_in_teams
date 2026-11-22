"""The live process's WebRTC connections, kept in memory only.

Django checks who is asking (request.user has a live session) and passes the
session id, user id and kind to the live process's internal API; a
ConnectionService then creates, answers and closes the peer connections
(live.models.Connection). There is no database row for a connection: a live
restart forgets them all, and the browsers connect again (they have to, the
peers are gone).

One ConnectionService per live process, made by run_live and handed to the
internal API: it owns the current connections. One connection per session
and kind: a new offer for the same session and kind replaces the old peer (a
reload or a reconnect), so a second tab can't open a second mic. Only the user
the offer was made for can answer it, and only once.

All of it runs on the live process's one event loop, so no locks: but every
await is a point where another request can replace the same connection, so
the methods check after awaiting that theirs is still the current one.
"""

import asyncio
import logging
import uuid

from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCIceTransportPolicy,
    RTCPeerConnection,
    RTCSessionDescription,
)
from django.core.exceptions import ValidationError
from django.utils import timezone

from live.models import Connection
from live.Services.AudioService import AudioService
from live.Services.CommandsService import Command, CommandsService
from live.turn import LIVE_TTL_SECONDS, turn_credentials

logger = logging.getLogger(__name__)

# Error codes (ValidationError.code) the internal API turns into responses.
CONNECTION_NOT_FOUND = "connection_not_found"
NOT_WAITING_FOR_ANSWER = "not_waiting_for_answer"
CONNECTION_REPLACED = "connection_replaced"


class ConnectionService:
    """The live process's current connections, and what can be done with them."""

    def __init__(self, ice_servers: list[str], commands: CommandsService, audio: AudioService,
                 turn_secret: str = "", relay_only: bool = False, offer_timeout: float = 30):
        # STUN/TURN server URLs every peer is made with (settings.RTC_ICE_SERVERS).
        self.ice_servers = ice_servers
        # Signs the peers' own TURN credentials (settings.TURN_SECRET).
        self.turn_secret = turn_secret
        # Only relayed paths, through the TURN server (settings.RTC_RELAY_ONLY):
        # on the VPS, where the live process isn't reachable from outside and
        # coturn is the only way in. Off locally, where it connects directly.
        self.relay_only = relay_only
        # Runs what arrives on the connections' control channels, and pauses
        # the talk when a trainer's connection drops.
        self.commands = commands
        # Reads the trainer's audio track into the session's recording.
        self.audio = audio
        # Seconds an offer may wait to be answered and connected before it is thrown away.
        self.offer_timeout = offer_timeout
        # The current connections, by (session_id, kind) (Connection.key).
        self.connections: dict[tuple[uuid.UUID, Connection.Kind], Connection] = {}

    async def create_offer(self, session_id: uuid.UUID, user_id: uuid.UUID,
                           kind: Connection.Kind) -> str:
        """Creates the peer connection for this session and kind and returns
        its offer (an SDP). An existing one for the same session and kind is
        closed first: the newest request wins. Django has already checked that
        `user_id` may connect to `session_id` as `kind`.

        The offer has a "control" data channel and, for TRAINER_AUDIO, an
        audio track the server only receives. It holds every ICE candidate
        (aiortc gathers them all before setLocalDescription returns), so no
        trickle ICE. Not connected within offer_timeout seconds: closed and removed.
        """
        # TURN needs credentials, made fresh for each peer; STUN doesn't.
        ice_servers = []
        for url in self.ice_servers:
            if url.startswith(("turn:", "turns:")) and self.turn_secret:
                username, credential = turn_credentials(self.turn_secret, "live", LIVE_TTL_SECONDS)
                ice_servers.append(RTCIceServer(urls=url, username=username, credential=credential))
            else:
                ice_servers.append(RTCIceServer(urls=url))
        peer = RTCPeerConnection(RTCConfiguration(
            iceServers=ice_servers,
            iceTransportPolicy=RTCIceTransportPolicy.RELAY if self.relay_only else RTCIceTransportPolicy.ALL))
        if kind == Connection.Kind.TRAINER_AUDIO:
            peer.addTransceiver("audio", direction="recvonly")
        connection = Connection(
            session_id=session_id, user_id=user_id, kind=kind, peer=peer,
            channel=peer.createDataChannel("control"), now=timezone.now())

        # In first, so a request arriving during the awaits below replaces this one.
        old = self.connections.get(connection.key)
        self.connections[connection.key] = connection
        if old is not None:
            await old.close()

        @peer.on("connectionstatechange")
        async def on_state_change():
            # A replaced peer's last events (closing) say nothing about the current one.
            if self.connections.get(connection.key) is not connection:
                return
            if peer.connectionState == "connected":
                connection.mark_connected(timezone.now())
            elif (peer.connectionState in ("disconnected", "failed")
                    and connection.state != Connection.State.DISCONNECTED):
                await self.connection_dropped(connection)

        @peer.on("track")
        def on_track(track):
            # The trainer's mic. The reading task lives as long as the track;
            # kept on the connection, so it isn't garbage collected meanwhile.
            if (track.kind == "audio" and connection.kind == Connection.Kind.TRAINER_AUDIO
                    and self.connections.get(connection.key) is connection):
                connection.audio_task = asyncio.create_task(self.audio.read(connection, track))

        @connection.channel.on("message")
        async def on_message(message):
            if self.connections.get(connection.key) is connection:
                await self.commands.handle(connection, message)

        async def expire():
            await asyncio.sleep(self.offer_timeout)
            if (self.connections.get(connection.key) is connection
                    and connection.state != Connection.State.CONNECTED):
                del self.connections[connection.key]
                await peer.close()

        offer = await peer.createOffer()
        await peer.setLocalDescription(offer)
        if self.connections.get(connection.key) is not connection:
            # Replaced while the offer was being made: this peer is closed already.
            raise ValidationError("A newer connection request replaced this one.",
                                  code=CONNECTION_REPLACED)
        connection.expiry = asyncio.create_task(expire())
        return peer.localDescription.sdp

    async def connection_dropped(self, connection: Connection):
        """The connection was lost: marks it disconnected and, for the
        trainer's, runs the pause_talk command, the same as the trainer
        pausing, so the dropped stretch doesn't count as recorded. The trainer
        resumes after reconnecting; the reconnect timeout comes later. No
        reply: the channel is gone. No talk going on, or a paused one, is
        fine: then there is nothing to pause.

        The pause starts now, a few seconds after the last audio arrived (ICE
        takes that long to notice); with the audio side it becomes the time
        of the last frame."""
        connection.mark_disconnected(timezone.now())
        if connection.kind != Connection.Kind.TRAINER_AUDIO:
            return
        try:
            await self.commands.run_command(connection, Command.PAUSE_TALK)
        except ValidationError:
            # no_open_talk, or invalid_transition for a talk already paused.
            pass
        except Exception:
            logger.exception("Pausing the talk of dropped %s failed", connection)

    async def accept_answer(self, session_id: uuid.UUID, user_id: uuid.UUID,
                            kind: Connection.Kind, sdp: str) -> Connection:
        """Sets the browser's answer on the connection the offer was made for,
        and returns it. Only the same user, and only once: a connection that
        doesn't exist and someone else's give the same error, so the internal
        API doesn't reveal which sessions are connected. ICE and DTLS then run
        by themselves; the state change handler in create_offer marks it connected."""
        connection = self.connections.get((session_id, kind))
        if connection is None or connection.user_id != user_id:
            raise ValidationError("There is no connection waiting for you.",
                                  code=CONNECTION_NOT_FOUND)
        if connection.state != Connection.State.WAITING_FOR_ANSWER:
            raise ValidationError("This offer has been answered already.",
                                  code=NOT_WAITING_FOR_ANSWER)

        # Before the await, so a second answer arriving meanwhile is refused.
        connection.mark_answered()
        await connection.peer.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="answer"))
        return connection

    async def close_session(self, session_id: uuid.UUID) -> bool:
        """Closes and removes every connection of the session (ending or
        aborting it), and returns whether there was one."""
        connections = [connection for connection in self.connections.values()
                       if connection.session_id == session_id]
        for connection in connections:
            del self.connections[connection.key]
            await connection.close()
        return bool(connections)
