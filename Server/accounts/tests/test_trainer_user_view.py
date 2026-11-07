from datetime import date

from django.test import TestCase
from django.utils import timezone

from accounts.dbviews import TrainerUser
from accounts.models import User
from accounts.services.invites import USER_FILTERS, get_users

from .utils import make_invite, make_speaker, make_trainer

# The accounts_trainer_user view (migration 0006_trainer_user_view) and the
# TrainerUser model are kept in sync by hand, and the invite status rules
# exist twice: in the view's SQL and in UserInvite.status. These tests fail
# when they drift apart, e.g. after a field the view reads is renamed or
# removed, a column is added on one side only, or a rule changes in one place.
# A model change without a migration is caught in test_migrations.py.


class TrainerUserViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", cls.trainer)
        now = timezone.now()
        cls.pending = make_invite(cls.trainer, "pending@example.com", days_old=1)
        cls.declined = make_invite(cls.trainer, "declined@example.com", days_old=2, declined_at=now)
        cls.revoked = make_invite(cls.trainer, "revoked@example.com", days_old=3, revoked_at=now)
        cls.expired = make_invite(cls.trainer, "expired@example.com", days_old=10)

    def emails(self, status="all", query="", trainer=None):
        return {row.email for row in get_users(trainer or self.trainer, status, query)}

    def test_columns_match_the_model(self):
        """Reads every TrainerUser field, so a column missing from the view,
        or named differently, fails here."""
        fields = [field.attname for field in TrainerUser._meta.concrete_fields]
        rows = list(TrainerUser.objects.filter(trainer=self.trainer).values(*fields))
        self.assertEqual(len(rows), 5)  # 1 speaker + 4 invites

    def test_filters(self):
        cases = {
            "speakers": {"mikkel@example.com"},
            "invites": {"pending@example.com"},
            "active": {"mikkel@example.com", "pending@example.com"},
            "inactive": {"declined@example.com", "revoked@example.com", "expired@example.com"},
            "all": {"mikkel@example.com", "pending@example.com", "declined@example.com",
                    "revoked@example.com", "expired@example.com"},
        }
        self.assertEqual(set(cases), set(USER_FILTERS))  # a new filter needs a case here
        for status, expected in cases.items():
            with self.subTest(status=status):
                self.assertEqual(self.emails(status), expected)

        with self.subTest("speakers is the default"):
            self.assertEqual({row.email for row in get_users(self.trainer)},
                             {"mikkel@example.com"})
        with self.subTest("newest first"):
            since = [row.since for row in get_users(self.trainer, "all")]
            self.assertEqual(since, sorted(since, reverse=True))
        with self.subTest("unknown filter"):
            with self.assertRaises(ValueError):
                get_users(self.trainer, "everyone")

    def test_state_matches_userinvite_status(self):
        """The view's SQL and UserInvite.status must agree for every state."""
        states = {row.id: row.state for row in get_users(self.trainer, "all")}
        for invite in (self.pending, self.declined, self.revoked, self.expired):
            with self.subTest(invite.email):
                self.assertEqual(states[invite.pk], invite.status)

    def test_row_contents(self):
        with self.subTest("a speaker row carries the profile"):
            row = get_users(self.trainer, "speakers").get()
            self.assertEqual(
                (row.id, row.kind, row.state, row.first_name, row.last_name,
                 row.birth_date, row.phone, row.expires),
                (self.speaker.speaker_profile.pk, TrainerUser.Kind.SPEAKER, "active",
                 "Mikkel", "Jensen", date(1996, 1, 1), "+4520123456", None))
            self.assertIsNotNone(row.age)

        with self.subTest("an invite row has only the email, state and dates"):
            row = get_users(self.trainer, "invites").get()
            self.assertEqual((row.id, row.kind, row.email, row.state),
                             (self.pending.pk, TrainerUser.Kind.INVITE, "pending@example.com",
                              "pending"))
            self.assertEqual((row.first_name, row.last_name, row.birth_date, row.phone, row.age),
                             (None, None, None, None, None))
            self.assertEqual((row.since, row.expires),
                             (self.pending.created_at, self.pending.expires_at))

    def test_which_rows_exist(self):
        with self.subTest("only the latest invite per email, in any letter case"):
            make_invite(self.trainer, "Pending@Example.com")
            rows = [row for row in get_users(self.trainer, "all")
                    if row.email.lower() == "pending@example.com"]
            self.assertEqual([row.email for row in rows], ["Pending@Example.com"])

        with self.subTest("an accepted latest invite hides the older ones"):
            make_invite(self.trainer, "declined@example.com", accepted_at=timezone.now())
            self.assertNotIn("declined@example.com", self.emails())

        with self.subTest("no invites for the trainer's own speakers"):
            make_invite(self.trainer, "MIKKEL@example.com")
            kinds = [row.kind for row in get_users(self.trainer, "all")
                     if row.email.lower() == "mikkel@example.com"]
            self.assertEqual(kinds, [TrainerUser.Kind.SPEAKER])

        with self.subTest("other trainers' rows never show"):
            other = make_trainer("bo@example.com")
            make_speaker("other@example.com", other)
            make_invite(other, "theirs@example.com")
            self.assertEqual(self.emails() & {"other@example.com", "theirs@example.com"}, set())
            self.assertEqual(self.emails(trainer=other), {"other@example.com", "theirs@example.com"})

        # Last, because it changes the speaker.
        with self.subTest("deactivated speakers are left out"):
            User.objects.filter(pk=self.speaker.pk).update(is_active=False)
            self.assertEqual(self.emails("speakers"), set())

    def test_search(self):
        cases = [
            ("first name, any part", "speakers", "ikke", {"mikkel@example.com"}),
            ("last name, any case", "speakers", "JENSEN", {"mikkel@example.com"}),
            ("email of an invite", "all", "expired", {"expired@example.com"}),
            ("nothing matches", "all", "nobody", set()),
            ("only spaces: no search", "invites", "   ", {"pending@example.com"}),
        ]
        for label, status, query, expected in cases:
            with self.subTest(label, query=query):
                self.assertEqual(self.emails(status, query), expected)
