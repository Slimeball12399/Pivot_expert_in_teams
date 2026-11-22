"""Short-lived TURN credentials for coturn (its use-auth-secret mode, see the
coturn service in docker-compose.yml). No accounts on the TURN server: whoever
knows TURN_SECRET signs a username that carries its own expiry, and coturn
checks the signature with the same secret. The live process gets them for its
own peers, the browser (later) from Django with its offer.
"""

import base64
import hashlib
import hmac
import time

# How long a login is valid. The browser's (from Django, with the offer) is
# short, so a leaked one stops working soon: 2 hours covers a session, and a
# reconnect gets a fresh one. The live process makes a new one for every peer.
BROWSER_TTL_SECONDS = 2 * 60 * 60
LIVE_TTL_SECONDS = 24 * 60 * 60


def turn_credentials(secret: str, name: str, ttl_seconds: int) -> tuple[str, str]:
    """(username, password) valid for ttl_seconds: the username is
    "<expiry unix time>:<name>", the password its HMAC-SHA1 with the secret,
    base64, as coturn expects. `name` only shows up in coturn's logs: "live"
    for the live process, the user id for a browser."""
    username = f"{int(time.time()) + ttl_seconds}:{name}"
    password = base64.b64encode(
        hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()).decode()
    return username, password
