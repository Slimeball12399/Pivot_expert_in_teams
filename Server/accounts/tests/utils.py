from datetime import datetime, timezone
from unittest import mock

# Tests that depend on "today" run as if it were this moment.
FIXED_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


def frozen_now(moment=FIXED_NOW):
    """Make datetime.now() in accounts.validators return `moment`.

    Use as a context manager or start()/stop() it in setUp.
    """

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment if tz is not None else moment.replace(tzinfo=None)

    return mock.patch("accounts.validators.datetime", FrozenDatetime)


def code_in(message):
    """The one-time code in a code email (the "1234 5678" line), without spaces."""
    import re

    match = re.search(r"^\s+(\d[\d ]*\d)\s*$", message.body, re.MULTILINE)
    if match is None:
        raise AssertionError(f"No code in the email:\n{message.body}")
    return match.group(1).replace(" ", "")
