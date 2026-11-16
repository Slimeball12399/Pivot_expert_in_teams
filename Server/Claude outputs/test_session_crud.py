import uuid
from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import AdminProfile, SpeakerProfile, User
from core.models import Session
from core.services.SessionsService import (
    INVALID_DISPLAY,
    INVALID_FILTER,
    INVALID_PAGE,
    INVALID_SCHEDULE,
    INVALID_TRANSITION,
    NOT_ADMIN,
    SESSION_NOT_YOURS,
    SPEAKER_ALREADY_LIVE,
    SPEAKER_INACTIVE,
    SPEAKER_NOT_YOURS,
    cancel_session,
    create_session,
    end_session,
    get_session,
    list_sessions,
    start_session,
    update_session,
)

# CRUD and state machine events of SessionsService: who may do what (admins
# manage their own sessions, speakers only see theirs), the status each event
# needs, and that only the intended fields change.


def make_admin(email):
    user = User.objects.create_user(
        email, first_name="Ada", last_name="Admin", role=User.Role.ADMIN)
    AdminProfile.objects.create(user=user)
    return user


def make_speaker(email, admin):
    user = User.objects.create_user(
        email, first_name="Sam", last_name="Speaker", role=User.Role.SPEAKER)
    return SpeakerProfile.objects.create(
        user=user, admin=admin.admin_profile, birth_date=date(1995, 1, 1), height_cm=180)


class SessionTestCase(TestCase):
    def setUp(self):
        self.admin = make_admin("admin@example.com")
        self.speaker = make_speaker("speaker@example.com", self.admin)
        self.other_admin = make_admin("other-admin@example.com")
        self.other_speaker = make_speaker("other-speaker@example.com", self.other_admin)

    def session(self, status=Session.Status.NOT_STARTED, speaker=None, admin=None, **fields):
        """A session made directly in the database, bypassing the service."""
        speaker = speaker or self.speaker
        admin = admin or self.admin
        return Session.objects.create(
            trainer=admin.admin_profile, speaker=speaker, status=status, **fields)

    def assertCode(self, ctx, code):
        self.assertEqual(ctx.exception.code, code)


class CreateSessionTests(SessionTestCase):
    def test_creates_not_started_session(self):
        when = timezone.now() + timedelta(days=1)
        session = create_session(
            trainer=self.admin, speaker_id=self.speaker.pk,
            display=Session.Display.BOTH, scheduled_at=when)

        self.assertEqual(session.status, Session.Status.NOT_STARTED)
        self.assertEqual(session.trainer, self.admin.admin_profile)
        self.assertEqual(session.speaker, self.speaker)
        self.assertEqual(session.display, Session.Display.BOTH)
        self.assertEqual(session.scheduled_at, when)
        self.assertIsNone(session.started_at)
        self.assertIsNone(session.ended_at)

    def test_defaults_to_web_without_schedule(self):
        session = create_session(trainer=self.admin, speaker_id=self.speaker.pk)
        self.assertEqual(session.display, Session.Display.WEB)
        self.assertIsNone(session.scheduled_at)

    def test_allows_several_not_started_sessions_per_speaker(self):
        create_session(trainer=self.admin, speaker_id=self.speaker.pk)
        create_session(trainer=self.admin, speaker_id=self.speaker.pk)
        self.assertEqual(Session.objects.filter(speaker=self.speaker).count(), 2)

    def test_rejects_other_admins_speaker(self):
        with self.assertRaises(ValidationError) as ctx:
            create_session(trainer=self.admin, speaker_id=self.other_speaker.pk)
        self.assertCode(ctx, SPEAKER_NOT_YOURS)

    def test_unknown_speaker_gives_same_error(self):
        with self.assertRaises(ValidationError) as ctx:
            create_session(trainer=self.admin, speaker_id=uuid.uuid4())
        self.assertCode(ctx, SPEAKER_NOT_YOURS)

    def test_speaker_as_trainer_has_no_speakers(self):
        with self.assertRaises(ValidationError) as ctx:
            create_session(trainer=self.speaker.user, speaker_id=self.speaker.pk)
        self.assertCode(ctx, SPEAKER_NOT_YOURS)

    def test_rejects_inactive_speaker(self):
        self.speaker.user.is_active = False
        self.speaker.user.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError) as ctx:
            create_session(trainer=self.admin, speaker_id=self.speaker.pk)
        self.assertCode(ctx, SPEAKER_INACTIVE)

    def test_rejects_unknown_display(self):
        with self.assertRaises(ValidationError) as ctx:
            create_session(trainer=self.admin, speaker_id=self.speaker.pk, display="TV")
        self.assertCode(ctx, INVALID_DISPLAY)

    def test_rejects_schedule_without_time_zone(self):
        with self.assertRaises(ValidationError) as ctx:
            create_session(trainer=self.admin, speaker_id=self.speaker.pk,
                           scheduled_at=datetime(2099, 1, 1, 10, 0))
        self.assertCode(ctx, INVALID_SCHEDULE)

    def test_rejects_schedule_in_the_past(self):
        with self.assertRaises(ValidationError) as ctx:
            create_session(trainer=self.admin, speaker_id=self.speaker.pk,
                           scheduled_at=timezone.now() - timedelta(minutes=1))
        self.assertCode(ctx, INVALID_SCHEDULE)
        self.assertFalse(Session.objects.exists())


class ListSessionsTests(SessionTestCase):
    def test_returns_a_list(self):
        self.session()
        self.assertIsInstance(list_sessions(user=self.admin), list)

    def test_admin_sees_only_own_sessions(self):
        own = self.session()
        self.session(speaker=self.other_speaker, admin=self.other_admin)
        self.assertEqual(list_sessions(user=self.admin), [own])

    def test_speaker_sees_only_own_sessions(self):
        own = self.session()
        self.session(speaker=self.other_speaker, admin=self.other_admin)
        self.assertEqual(list_sessions(user=self.speaker.user), [own])

    def test_filters_by_status(self):
        live = self.session(status=Session.Status.LIVE)
        self.session(status=Session.Status.FINISHED)
        self.assertEqual(list_sessions(user=self.admin, statuses=["LIVE"]), [live])

    def test_rejects_unknown_status(self):
        with self.assertRaises(ValidationError) as ctx:
            list_sessions(user=self.admin, statuses=["SLEEPING"])
        self.assertCode(ctx, INVALID_FILTER)

    def test_filters_by_speaker(self):
        second = make_speaker("second@example.com", self.admin)
        self.session()
        theirs = self.session(speaker=second)
        self.assertEqual(list_sessions(user=self.admin, speaker_id=second.pk), [theirs])

    def test_newest_first_with_limit_and_offset(self):
        now = timezone.now()
        sessions = [self.session() for _ in range(3)]
        for age, session in enumerate(sessions):  # sessions[0] is the newest
            Session.objects.filter(pk=session.pk).update(created_at=now - timedelta(minutes=age))

        self.assertEqual(list_sessions(user=self.admin), sessions)
        self.assertEqual(list_sessions(user=self.admin, limit=2), sessions[:2])
        self.assertEqual(list_sessions(user=self.admin, limit=2, offset=2), sessions[2:])

    def test_rejects_bad_paging(self):
        for kwargs in ({"limit": 0}, {"offset": -1}):
            with self.subTest(**kwargs):
                with self.assertRaises(ValidationError) as ctx:
                    list_sessions(user=self.admin, **kwargs)
                self.assertCode(ctx, INVALID_PAGE)


class GetSessionTests(SessionTestCase):
    def test_admin_gets_own_session_in_any_status(self):
        # Only one LIVE session per speaker is allowed, so each status gets its own speaker.
        for status in Session.Status.values:
            with self.subTest(status=status):
                speaker = make_speaker(f"{status.lower()}@example.com", self.admin)
                session = self.session(status=status, speaker=speaker)
                self.assertEqual(get_session(user=self.admin, session_id=session.pk), session)

    def test_speaker_gets_own_session(self):
        session = self.session()
        self.assertEqual(get_session(user=self.speaker.user, session_id=session.pk), session)

    def test_others_and_unknown_sessions_give_same_error(self):
        others = self.session(speaker=self.other_speaker, admin=self.other_admin)
        cases = [(self.admin, others.pk), (self.speaker.user, others.pk), (self.admin, uuid.uuid4())]
        for user, session_id in cases:
            with self.subTest(user=user.email, session_id=session_id):
                with self.assertRaises(ValidationError) as ctx:
                    get_session(user=user, session_id=session_id)
                self.assertCode(ctx, SESSION_NOT_YOURS)


class UpdateSessionTests(SessionTestCase):
    def test_changes_only_given_fields(self):
        when = timezone.now() + timedelta(days=2)
        session = self.session(display=Session.Display.WEB, scheduled_at=when)

        updated = update_session(trainer=self.admin, session_id=session.pk,
                                 display=Session.Display.MOBILE)

        self.assertEqual(updated.display, Session.Display.MOBILE)
        session.refresh_from_db()
        self.assertEqual(session.display, Session.Display.MOBILE)
        self.assertEqual(session.scheduled_at, when)

    def test_none_removes_schedule(self):
        session = self.session(scheduled_at=timezone.now() + timedelta(days=1))
        update_session(trainer=self.admin, session_id=session.pk, scheduled_at=None)
        session.refresh_from_db()
        self.assertIsNone(session.scheduled_at)

    def test_no_changes_returns_session(self):
        session = self.session()
        self.assertEqual(update_session(trainer=self.admin, session_id=session.pk), session)

    def test_rejects_speaker(self):
        session = self.session()
        with self.assertRaises(ValidationError) as ctx:
            update_session(trainer=self.speaker.user, session_id=session.pk,
                           display=Session.Display.BOTH)
        self.assertCode(ctx, NOT_ADMIN)

    def test_rejects_other_admins_session(self):
        session = self.session(speaker=self.other_speaker, admin=self.other_admin)
        with self.assertRaises(ValidationError) as ctx:
            update_session(trainer=self.admin, session_id=session.pk,
                           display=Session.Display.BOTH)
        self.assertCode(ctx, SESSION_NOT_YOURS)

    def test_rejects_started_session(self):
        session = self.session(status=Session.Status.LIVE)
        with self.assertRaises(ValidationError) as ctx:
            update_session(trainer=self.admin, session_id=session.pk,
                           display=Session.Display.BOTH)
        self.assertCode(ctx, INVALID_TRANSITION)

    def test_invalid_values_save_nothing(self):
        session = self.session(display=Session.Display.WEB)
        cases = [
            ({"display": "TV"}, INVALID_DISPLAY),
            ({"scheduled_at": timezone.now() - timedelta(hours=1)}, INVALID_SCHEDULE),
        ]
        for kwargs, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(ValidationError) as ctx:
                    update_session(trainer=self.admin, session_id=session.pk, **kwargs)
                self.assertCode(ctx, code)
        session.refresh_from_db()
        self.assertEqual(session.display, Session.Display.WEB)
        self.assertIsNone(session.scheduled_at)


class StartSessionTests(SessionTestCase):
    def test_starts_and_sets_started_at(self):
        session = self.session()
        started = start_session(trainer=self.admin, session_id=session.pk)

        self.assertEqual(started.status, Session.Status.LIVE)
        self.assertIsNotNone(started.started_at)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.LIVE)

    def test_refuses_second_live_session_for_speaker(self):
        self.session(status=Session.Status.LIVE, started_at=timezone.now())
        waiting = self.session()

        with self.assertRaises(ValidationError) as ctx:
            start_session(trainer=self.admin, session_id=waiting.pk)

        self.assertCode(ctx, SPEAKER_ALREADY_LIVE)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status, Session.Status.NOT_STARTED)

    def test_rejects_session_that_already_started(self):
        session = self.session(status=Session.Status.LIVE)
        with self.assertRaises(ValidationError) as ctx:
            start_session(trainer=self.admin, session_id=session.pk)
        self.assertCode(ctx, INVALID_TRANSITION)

    def test_rejects_speaker_and_other_admin(self):
        session = self.session()
        for user, code in ((self.speaker.user, NOT_ADMIN), (self.other_admin, SESSION_NOT_YOURS)):
            with self.subTest(user=user.email):
                with self.assertRaises(ValidationError) as ctx:
                    start_session(trainer=user, session_id=session.pk)
                self.assertCode(ctx, code)


class EndSessionTests(SessionTestCase):
    def test_ends_live_session_and_sets_ended_at(self):
        session = self.session(status=Session.Status.LIVE, started_at=timezone.now())
        ended = end_session(trainer=self.admin, session_id=session.pk)

        self.assertEqual(ended.status, Session.Status.FINISHED)
        self.assertIsNotNone(ended.ended_at)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.FINISHED)

    def test_rejects_session_that_is_not_live(self):
        session = self.session()
        with self.assertRaises(ValidationError) as ctx:
            end_session(trainer=self.admin, session_id=session.pk)
        self.assertCode(ctx, INVALID_TRANSITION)

    def test_rejects_speaker(self):
        session = self.session(status=Session.Status.LIVE, started_at=timezone.now())
        with self.assertRaises(ValidationError) as ctx:
            end_session(trainer=self.speaker.user, session_id=session.pk)
        self.assertCode(ctx, NOT_ADMIN)


class CancelSessionTests(SessionTestCase):
    def test_cancels_not_started_session_and_keeps_row(self):
        session = self.session()
        cancelled = cancel_session(trainer=self.admin, session_id=session.pk)

        self.assertEqual(cancelled.status, Session.Status.CANCELLED)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.CANCELLED)

    def test_rejects_started_session(self):
        session = self.session(status=Session.Status.LIVE)
        with self.assertRaises(ValidationError) as ctx:
            cancel_session(trainer=self.admin, session_id=session.pk)
        self.assertCode(ctx, INVALID_TRANSITION)

    def test_rejects_speaker_and_other_admin(self):
        session = self.session()
        for user, code in ((self.speaker.user, NOT_ADMIN), (self.other_admin, SESSION_NOT_YOURS)):
            with self.subTest(user=user.email):
                with self.assertRaises(ValidationError) as ctx:
                    cancel_session(trainer=user, session_id=session.pk)
                self.assertCode(ctx, code)
