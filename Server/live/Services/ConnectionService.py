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
import uuid

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from django.core.exceptions import ValidationError
from django.utils import timezone

from live.models import Connection

# Error codes (ValidationError.code) the internal API turns into responses.
CONNECTION_NOT_FOUND = "connection_not_found"
NOT_WAITING_FOR_ANSWER = "not_waiting_for_answer"
CONNECTION_REPLACED = "connection_replaced"


class ConnectionService:
    """The live process's current connections, and what can be done with them."""

    def __init__(self, ice_servers: list[str], offer_timeout: float = 30):
        # STUN/TURN server URLs every peer is made with (settings.RTC_ICE_SERVERS).
        self.ice_servers = ice_servers
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
        peer = RTCPeerConnection(RTCConfiguration(
            iceServers=[RTCIceServer(urls=url) for url in self.ice_servers]))
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
            elif peer.connectionState in ("disconnected", "failed"):
                # Pausing the open talk and the reconnect timeout come with
                # the talk side (CommandsService).
                connection.mark_disconnected(timezone.now())

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
