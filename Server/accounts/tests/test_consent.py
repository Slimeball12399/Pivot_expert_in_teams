from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Consent, User


def make_user(email="user@example.com"):
    return User.objects.create_user(
        email, "Str0ng-test-pass!", first_name="Test", last_name="User")


class ConsentTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def grant(self, purpose=Consent.Purpose.PRIVACY_NOTICE, version="1", user=None, **extra):
        return Consent.objects.create(
            user=user or self.user, purpose=purpose, notice_version=version, **extra)

    def test_versions_and_settings(self):
        with self.subTest("every purpose has a version in settings"):
            for purpose in Consent.Purpose.values:
                self.assertTrue(settings.CONSENT_VERSIONS.get(purpose), purpose)
                self.assertEqual(Consent.current_version(purpose), settings.CONSENT_VERSIONS[purpose])

        with self.subTest("each purpose is read separately"):
            with override_settings(CONSENT_VERSIONS={"privacy_notice": "3", "research": "7"}):
                self.assertEqual(Consent.current_version("privacy_notice"), "3")
                self.assertEqual(Consent.current_version("research"), "7")

        with self.subTest("a missing version is a configuration error"):
            with override_settings(CONSENT_VERSIONS={"privacy_notice": "1"}):
                with self.assertRaises(ImproperlyConfigured):
                    Consent.current_version("research")

        with self.subTest("required purposes are real purposes"):
            self.assertTrue(Consent.REQUIRED_FOR_SPEAKERS)
            self.assertLessEqual(set(Consent.REQUIRED_FOR_SPEAKERS), set(Consent.Purpose.values))

    def test_new_consent(self):
        before = timezone.now()
        consent = self.grant(version="2")

        self.assertGreaterEqual(consent.granted_at, before)
        self.assertLessEqual(consent.granted_at, timezone.now())
        self.assertIsNone(consent.withdrawn_at)
        self.assertEqual(str(consent), "user@example.com privacy_notice v2")

    def test_one_row_per_user_purpose_and_version(self):
        self.grant(version="1")

        with self.subTest("the same version twice is rejected"):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    self.grant(version="1")

        with self.subTest("a new version, another purpose or another user is a new row"):
            self.grant(version="2")
            self.grant(purpose=Consent.Purpose.RESEARCH, version="1")
            self.grant(version="1", user=make_user("other@example.com"))
            self.assertEqual(Consent.objects.count(), 4)
            self.assertEqual(self.user.consents.count(), 3)

    def test_history_is_kept(self):
        now = timezone.now()
        old = self.grant(version="1", granted_at=now - timedelta(days=30))
        new = self.grant(version="2", granted_at=now)

        with self.subTest("newest first"):
            self.assertEqual(list(self.user.consents.all()), [new, old])

        with self.subTest("withdrawing keeps the row"):
            old.withdrawn_at = now
            old.save()
            self.assertEqual(self.user.consents.count(), 2)
            self.assertIsNotNone(self.user.consents.get(pk=old.pk).withdrawn_at)

        with self.subTest("deleted together with the user"):
            self.user.delete()
            self.assertEqual(Consent.objects.count(), 0)
