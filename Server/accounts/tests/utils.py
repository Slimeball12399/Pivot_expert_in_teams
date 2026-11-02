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
