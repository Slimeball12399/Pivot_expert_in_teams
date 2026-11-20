import uuid
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.tests.utils import make_speaker, make_trainer
from core.models import FullVoiceResult, Session, Talk
from core.services.SessionsService import (
    INVALID_FILTER,
    INVALID_PAGE,
    INVALID_TRANSITION,
    NOT_ADMIN,
    SESSION_NOT_YOURS,
    SPEAKER_ALREADY_LIVE,
    SPEAKER_INACTIVE,
    SPEAKER_NOT_YOURS,
    abort_session,
    cancel_session,
    create_session,
    end_session,
    get_session,
    list_sessions,
    start_session,
    update_session,
)
from core.validators import INVALID_SCHEDULE

# The rules of SessionsService: creating, listing, reading and changing
# sessions, and the state machine events (start, end, cancel, abort). A trainer
# manages their own sessions; a speaker only sees theirs.
# The HTTP layer gets its own tests in api/tests and web/tests with the endpoints.


class SessionServiceTestCase(TestCase):
    """Shared data and helpers for the session tests below."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", cls.trainer).speaker_profile
        cls.other_trainer = make_trainer("bo@example.com")
        cls.other_speaker = make_speaker("lars@example.com", cls.other_trainer).speaker_profile

    def make_session(self, status=Session.Status.NOT_STARTED, *, speaker=None, **fields):
        """A session made straight in the database, bypassing the service."""
        speaker = speaker or self.speaker
        return Session.objects.create(
            trainer=speaker.admin, speaker=speaker, status=status, **fields)

    def assertRaisesCode(self, code, func, field=None, **kwargs):
        """func(**kwargs) raises a ValidationError with `code`. With `field`:
        a field error from full_clean(), with `code` as that field's error."""
        with self.assertRaises(ValidationError) as ctx:
            func(**kwargs)
        if field is None:
            self.assertEqual(ctx.exception.code, code)
        else:
            self.assertEqual([error.code for error in ctx.exception.error_dict[field]], [code])


class CreateSessionTests(SessionServiceTestCase):
    def test_creates_a_not_started_session(self):
        with self.subTest("with a display and a schedule"):
            when = timezone.now() + timedelta(days=1)
            session = create_session(
                trainer=self.trainer.user, speaker_id=self.speaker.user_id,
                display=Session.Display.BOTH, scheduled_at=when)
            self.assertEqual(session.status, Session.Status.NOT_STARTED)
            self.assertEqual(session.trainer, self.trainer)
            self.assertEqual(session.speaker, self.speaker)
            self.assertEqual(session.display, Session.Display.BOTH)
            self.assertEqual(session.scheduled_at, when)
            self.assertIsNone(session.started_at)
            self.assertIsNone(session.ended_at)

        with self.subTest("defaults: browser only, no schedule"):
            session = create_session(trainer=self.trainer.user, speaker_id=self.speaker.user_id)
            self.assertEqual(session.display, Session.Display.WEB)
            self.assertIsNone(session.scheduled_at)

        with self.subTest("a speaker can have several sessions that haven't started"):
            self.assertEqual(Session.objects.filter(speaker=self.speaker).count(), 2)

    def test_rejects(self):
        cases = [
            ("another trainer's speaker", None, SPEAKER_NOT_YOURS,
             {"speaker_id": self.other_speaker.user_id}),
            ("a speaker that doesn't exist", None, SPEAKER_NOT_YOURS, {"speaker_id": uuid.uuid4()}),
            ("a speaker can't create sessions", None, SPEAKER_NOT_YOURS,
             {"trainer": self.speaker.user}),
            ("an unknown display", "display", "invalid_choice", {"display": "TV"}),
            ("a schedule without a time zone", "scheduled_at", INVALID_SCHEDULE,
             {"scheduled_at": datetime(2099, 1, 1, 10, 0)}),
            ("a schedule in the past", "scheduled_at", INVALID_SCHEDULE,
             {"scheduled_at": timezone.now() - timedelta(minutes=1)}),
        ]
        for label, field, code, overrides in cases:
            with self.subTest(label):
                self.assertRaisesCode(code, create_session, field, **{
                    "trainer": self.trainer.user, "speaker_id": self.speaker.user_id, **overrides})

        # Last, because it changes the speaker.
        with self.subTest("a deactivated speaker"):
            self.speaker.user.is_active = False
            self.speaker.user.save(update_fields=["is_active"])
            self.assertRaisesCode(SPEAKER_INACTIVE, create_session,
                                  trainer=self.trainer.user, speaker_id=self.speaker.user_id)

        self.assertFalse(Session.objects.exists())


class ListSessionsTests(SessionServiceTestCase):
    def test_each_user_sees_only_their_own(self):
        own = self.make_session()
        self.make_session(speaker=self.other_speaker)

        with self.subTest("a plain list"):
            self.assertIsInstance(list_sessions(user=self.trainer.user), list)
        with self.subTest("the trainer: the sessions they lead"):
            self.assertEqual(list_sessions(user=self.trainer.user), [own])
        with self.subTest("the speaker: their own sessions"):
            self.assertEqual(list_sessions(user=self.speaker.user), [own])

    def test_filters(self):
        second = make_speaker("sofie@example.com", self.trainer).speaker_profile
        live = self.make_session(Session.Status.LIVE)
        self.make_session(Session.Status.FINISHED)
        theirs = self.make_session(speaker=second)

        with self.subTest("by status"):
            self.assertEqual(list_sessions(user=self.trainer.user, statuses=["LIVE"]), [live])
        with self.subTest("by speaker"):
            self.assertEqual(list_sessions(user=self.trainer.user, speaker_id=second.user_id), [theirs])
        with self.subTest("an unknown status"):
            self.assertRaisesCode(INVALID_FILTER, list_sessions,
                                  user=self.trainer.user, statuses=["SLEEPING"])

    def test_newest_first_and_paging(self):
        now = timezone.now()
        sessions = [self.make_session() for _ in range(3)]
        for minutes_old, session in enumerate(sessions):  # sessions[0] is the newest
            Session.objects.filter(pk=session.pk).update(
                created_at=now - timedelta(minutes=minutes_old))

        with self.subTest("newest first"):
            self.assertEqual(list_sessions(user=self.trainer.user), sessions)
        with self.subTest("limit and offset"):
            self.assertEqual(list_sessions(user=self.trainer.user, limit=2), sessions[:2])
            self.assertEqual(list_sessions(user=self.trainer.user, limit=2, offset=2), sessions[2:])

        cases = [("a limit below 1", {"limit": 0}), ("a negative offset", {"offset": -1})]
        for label, paging in cases:
            with self.subTest(label):
                self.assertRaisesCode(INVALID_PAGE, list_sessions, user=self.trainer.user, **paging)


class GetSessionTests(SessionServiceTestCase):
    def test_returns_own_session_in_any_status(self):
        for status in Session.Status.values:
            with self.subTest(status):
                session = self.make_session(status)
                self.assertEqual(get_session(user=self.trainer.user, session_id=session.pk), session)
                self.assertEqual(get_session(user=self.speaker.user, session_id=session.pk), session)

    def test_includes_the_talks_oldest_first_without_discarded_ones(self):
        session = self.make_session(Session.Status.FINISHED)
        now = timezone.now()
        second = Talk.objects.create(
            session=session, status=Talk.Status.COMPLETED, started_at=now - timedelta(minutes=5))
        first = Talk.objects.create(
            session=session, status=Talk.Status.COMPLETED, started_at=now - timedelta(minutes=20))
        Talk.objects.create(
            session=session, status=Talk.Status.DISCARDED, started_at=now - timedelta(minutes=10))
        Talk.objects.create(
            session=self.make_session(speaker=self.other_speaker),
            status=Talk.Status.COMPLETED, started_at=now)
        FullVoiceResult.objects.create(talk=first, voice_score=7.5)

        for label, user in [("the trainer", self.trainer.user), ("the speaker", self.speaker.user)]:
            with self.subTest(label):
                with self.assertNumQueries(2):
                    found = get_session(user=user, session_id=session.pk)
                # The talks and their scores came with the session: no extra queries.
                with self.assertNumQueries(0):
                    talks = list(found.talks.all())
                    self.assertEqual(talks, [first, second])
                    self.assertEqual(talks[0].full_voice_result.voice_score, 7.5)
                    self.assertIsNone(getattr(talks[1], "full_voice_result", None))

    def test_not_found(self):
        others = self.make_session(speaker=self.other_speaker)
        cases = [
            ("the trainer, another trainer's session", self.trainer.user, others.pk),
            ("the speaker, someone else's session", self.speaker.user, others.pk),
            ("a session that doesn't exist", self.trainer.user, uuid.uuid4()),
        ]
        for label, user, session_id in cases:
            with self.subTest(label):
                self.assertRaisesCode(SESSION_NOT_YOURS, get_session, user=user, session_id=session_id)


class UpdateSessionTests(SessionServiceTestCase):
    def test_changes_only_the_given_fields(self):
        when = timezone.now() + timedelta(days=2)
        session = self.make_session(display=Session.Display.WEB, scheduled_at=when)

        with self.subTest("the display, the schedule stays"):
            updated = update_session(trainer=self.trainer.user, session_id=session.pk,
                                     display=Session.Display.MOBILE)
            self.assertEqual(updated.display, Session.Display.MOBILE)
            session.refresh_from_db()
            self.assertEqual(session.display, Session.Display.MOBILE)
            self.assertEqual(session.scheduled_at, when)

        with self.subTest("None removes the schedule"):
            update_session(trainer=self.trainer.user, session_id=session.pk, scheduled_at=None)
            session.refresh_from_db()
            self.assertIsNone(session.scheduled_at)

        with self.subTest("nothing to change returns the session"):
            self.assertEqual(update_session(trainer=self.trainer.user, session_id=session.pk), session)

        with self.subTest("a schedule that has passed doesn't block changing the display"):
            passed = timezone.now() - timedelta(hours=1)
            Session.objects.filter(pk=session.pk).update(scheduled_at=passed)
            update_session(trainer=self.trainer.user, session_id=session.pk,
                           display=Session.Display.BOTH)
            session.refresh_from_db()
            self.assertEqual(session.display, Session.Display.BOTH)
            self.assertEqual(session.scheduled_at, passed)

    def test_rejects(self):
        session = self.make_session(display=Session.Display.WEB)
        live = self.make_session(Session.Status.LIVE)
        others = self.make_session(speaker=self.other_speaker)
        cases = [
            ("a speaker", None, NOT_ADMIN, {"trainer": self.speaker.user}),
            ("another trainer's session", None, SESSION_NOT_YOURS, {"session_id": others.pk}),
            ("a session that has started", None, INVALID_TRANSITION, {"session_id": live.pk}),
            ("an unknown display", "display", "invalid_choice", {"display": "TV"}),
            ("a schedule in the past", "scheduled_at", INVALID_SCHEDULE,
             {"scheduled_at": timezone.now() - timedelta(hours=1)}),
        ]
        for label, field, code, overrides in cases:
            with self.subTest(label):
                self.assertRaisesCode(code, update_session, field, **{
                    "trainer": self.trainer.user, "session_id": session.pk,
                    "display": Session.Display.BOTH, **overrides})

        session.refresh_from_db()
        self.assertEqual(session.display, Session.Display.WEB)
        self.assertIsNone(session.scheduled_at)


class StartSessionTests(SessionServiceTestCase):
    def test_starts_and_sets_started_at(self):
        session = self.make_session()
        started = start_session(trainer=self.trainer.user, session_id=session.pk)

        self.assertEqual(started.status, Session.Status.LIVE)
        self.assertIsNotNone(started.started_at)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.LIVE)

    def test_rejects(self):
        waiting = self.make_session()
        finished = self.make_session(Session.Status.FINISHED)
        cases = [
            ("a speaker", NOT_ADMIN, self.speaker.user, waiting.pk),
            ("another trainer", SESSION_NOT_YOURS, self.other_trainer.user, waiting.pk),
            ("a session that has already ended", INVALID_TRANSITION, self.trainer.user, finished.pk),
        ]
        for label, code, user, session_id in cases:
            with self.subTest(label):
                self.assertRaisesCode(code, start_session, trainer=user, session_id=session_id)

        waiting.refresh_from_db()
        self.assertEqual(waiting.status, Session.Status.NOT_STARTED)

    def test_one_live_session_per_speaker(self):
        self.make_session(Session.Status.LIVE, started_at=timezone.now())
        waiting = self.make_session()

        self.assertRaisesCode(SPEAKER_ALREADY_LIVE, start_session,
                              trainer=self.trainer.user, session_id=waiting.pk)
        waiting.refresh_from_db()
        self.assertEqual(waiting.status, Session.Status.NOT_STARTED)


class EndSessionTests(SessionServiceTestCase):
    def test_ends_and_sets_ended_at(self):
        session = self.make_session(Session.Status.LIVE, started_at=timezone.now())
        ended = end_session(trainer=self.trainer.user, session_id=session.pk)

        self.assertEqual(ended.status, Session.Status.FINISHED)
        self.assertIsNotNone(ended.ended_at)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.FINISHED)

    def test_finishes_the_open_talk_at_the_same_moment(self):
        for status in (Talk.Status.RECORDING, Talk.Status.PAUSED):
            with self.subTest(status):
                session = self.make_session(Session.Status.LIVE, started_at=timezone.now())
                now = timezone.now()
                done = Talk.objects.create(
                    session=session, status=Talk.Status.COMPLETED,
                    started_at=now - timedelta(minutes=20), duration=timedelta(minutes=3))
                talk = Talk.objects.create(
                    session=session, status=status, started_at=now - timedelta(minutes=10))
                if status == Talk.Status.PAUSED:
                    talk.pauses.create(paused_at=now - timedelta(minutes=2))

                ended = end_session(trainer=self.trainer.user, session_id=session.pk)

                talk.refresh_from_db()
                self.assertEqual(talk.status, Talk.Status.PROCESSING)
                if status == Talk.Status.PAUSED:
                    # Recorded until the pause, 8 minutes; the pause ends with the session.
                    self.assertEqual(talk.duration, timedelta(minutes=8))
                    self.assertEqual(talk.pauses.get().resumed_at, ended.ended_at)
                else:
                    self.assertEqual(talk.duration, ended.ended_at - talk.started_at)
                # The returned session shows the change, without a new query.
                with self.assertNumQueries(0):
                    self.assertEqual(
                        [t.status for t in ended.talks.all()],
                        [Talk.Status.COMPLETED, Talk.Status.PROCESSING])
                done.refresh_from_db()
                self.assertEqual(done.duration, timedelta(minutes=3))

    def test_rejects(self):
        live = self.make_session(Session.Status.LIVE, started_at=timezone.now())
        waiting = self.make_session()
        cases = [
            ("a speaker", NOT_ADMIN, self.speaker.user, live.pk),
            ("another trainer", SESSION_NOT_YOURS, self.other_trainer.user, live.pk),
            ("a session that hasn't started", INVALID_TRANSITION, self.trainer.user, waiting.pk),
        ]
        for label, code, user, session_id in cases:
            with self.subTest(label):
                self.assertRaisesCode(code, end_session, trainer=user, session_id=session_id)

        live.refresh_from_db()
        self.assertEqual(live.status, Session.Status.LIVE)


class CancelSessionTests(SessionServiceTestCase):
    def test_cancels_and_keeps_the_row(self):
        session = self.make_session()
        cancelled = cancel_session(trainer=self.trainer.user, session_id=session.pk)

        self.assertEqual(cancelled.status, Session.Status.CANCELLED)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.CANCELLED)

    def test_rejects(self):
        waiting = self.make_session()
        live = self.make_session(Session.Status.LIVE, started_at=timezone.now())
        cases = [
            ("a speaker", NOT_ADMIN, self.speaker.user, waiting.pk),
            ("another trainer", SESSION_NOT_YOURS, self.other_trainer.user, waiting.pk),
            ("a session that has started", INVALID_TRANSITION, self.trainer.user, live.pk),
        ]
        for label, code, user, session_id in cases:
            with self.subTest(label):
                self.assertRaisesCode(code, cancel_session, trainer=user, session_id=session_id)

        waiting.refresh_from_db()
        self.assertEqual(waiting.status, Session.Status.NOT_STARTED)


class AbortSessionTests(SessionServiceTestCase):
    def test_aborts_and_fails_the_open_talk(self):
        session = self.make_session(Session.Status.LIVE, started_at=timezone.now())
        now = timezone.now()
        talk = Talk.objects.create(
            session=session, status=Talk.Status.PAUSED, started_at=now - timedelta(minutes=10))
        talk.pauses.create(paused_at=now - timedelta(minutes=2))

        aborted = abort_session(trainer=self.trainer.user, session_id=session.pk)

        self.assertEqual(aborted.status, Session.Status.ABORTED)
        self.assertIsNotNone(aborted.ended_at)
        talk.refresh_from_db()
        self.assertEqual(talk.status, Talk.Status.FAILED)
        # The duration is set, for a retry if the audio was saved.
        self.assertEqual(talk.duration, timedelta(minutes=8))
        self.assertEqual(talk.pauses.get().resumed_at, aborted.ended_at)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.ABORTED)

    def test_rejects(self):
        live = self.make_session(Session.Status.LIVE, started_at=timezone.now())
        finished = self.make_session(Session.Status.FINISHED)
        cases = [
            ("a speaker", NOT_ADMIN, self.speaker.user, live.pk),
            ("another trainer", SESSION_NOT_YOURS, self.other_trainer.user, live.pk),
            ("a session that isn't live", INVALID_TRANSITION, self.trainer.user, finished.pk),
        ]
        for label, code, user, session_id in cases:
            with self.subTest(label):
                self.assertRaisesCode(code, abort_session, trainer=user, session_id=session_id)

        live.refresh_from_db()
        self.assertEqual(live.status, Session.Status.LIVE)
