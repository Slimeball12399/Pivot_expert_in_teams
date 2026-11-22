import base64
import hashlib
import hmac
import time

from django.test import SimpleTestCase

from live.turn import BROWSER_TTL_SECONDS, turn_credentials

# turn_credentials: the short-lived TURN login coturn checks in its
# use-auth-secret mode (the coturn service in docker-compose.yml).


class TurnCredentialsTests(SimpleTestCase):
    def test_signed_username_with_its_own_expiry(self):
        username, password = turn_credentials("s3cret", "live", ttl_seconds=600)
        expiry, name = username.split(":")

        with self.subTest("the username: expiry in unix time, then the name"):
            self.assertEqual(name, "live")
            self.assertAlmostEqual(int(expiry), time.time() + 600, delta=5)
        with self.subTest("the password: base64 HMAC-SHA1 of the username, as coturn computes it"):
            expected = base64.b64encode(hmac.new(b"s3cret", username.encode(), hashlib.sha1).digest()).decode()
            self.assertEqual(password, expected)
        with self.subTest("a browser's login: valid for 2 hours"):
            self.assertEqual(BROWSER_TTL_SECONDS, 2 * 60 * 60)
            browser_username, _ = turn_credentials("s3cret", "3f2a", BROWSER_TTL_SECONDS)
            self.assertAlmostEqual(int(browser_username.split(":")[0]), time.time() + 2 * 60 * 60, delta=5)
        with self.subTest("another secret: another password"):
            self.assertNotEqual(turn_credentials("other", "live", ttl_seconds=600)[1], password)
