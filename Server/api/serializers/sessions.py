"""Sessions and their talks, with the voice results.

The serializers only check the shape of the input. The rules (one of your own
speakers, a schedule not in the past, changes only before the session starts)
run in core.services.SessionsService, which the views call.
"""

from rest_framework import serializers

from core.models import Session

from .users import ProfileSerializer

# Base serializer: the fields a trainer sets on a session, defined once here.


class SessionBaseSerializer(serializers.Serializer):
    """What the trainer chooses: where the live feedback is shown, and when the
    session is planned (null: started on the spot, without a schedule)."""

    display = serializers.ChoiceField(choices=Session.Display.choices, required=False)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)


# Input


class SessionCreateSerializer(SessionBaseSerializer):
    """Input for POST /api/sessions/: who the session is with, plus the base
    fields. display defaults to WEB. The speaker can't be changed later."""

    # The speaker's user id.
    speaker_id = serializers.UUIDField()


class SessionListQuerySerializer(serializers.Serializer):
    """Query parameters of GET /api/sessions/, all optional. status can be
    given more than once (?status=LIVE&status=FINISHED)."""

    status = serializers.ListField(
        child=serializers.ChoiceField(choices=Session.Status.choices), required=False)
    speaker_id = serializers.UUIDField(required=False)
    limit = serializers.IntegerField(required=False, default=20)
    offset = serializers.IntegerField(required=False, default=0)


class SessionUpdateSerializer(SessionBaseSerializer):
    """Input for PATCH /api/sessions/<id>/, only while the session hasn't
    started. Send only the fields to change; scheduled_at null removes the
    schedule. speaker_id isn't declared, so one sent anyway is ignored."""


# Output


class TalkSummarySerializer(serializers.Serializer):
    """A talk in short form, as in a session's talk list: the talk and its
    overall scores. The full talk, with the voice windows, comes from get_talk."""

    id = serializers.UUIDField()
    status = serializers.CharField()
    started_at = serializers.DateTimeField()
    # Recorded time without the pauses; null while the talk is going on.
    duration = serializers.DurationField(allow_null=True)
    # The overall voice score, 0 to 100; null until the talk is processed.
    voice_score = serializers.FloatField(source="full_voice_result.voice_score", allow_null=True)
    # stability_score: added once the stability result exists.


class PartialVoiceResultSerializer(serializers.Serializer):
    """One analysis window of a talk, with only what the live graph shows."""

    # Absolute UTC time the window starts, the same time base as the stability data.
    start_at = serializers.DateTimeField()
    # The window's score, -10 to +10.
    voice_score = serializers.FloatField(allow_null=True)
    # The two lines of the live voice graph, -10 to +10.
    pace_score = serializers.FloatField(allow_null=True)
    pitch_variation_score = serializers.FloatField(allow_null=True)


class FullVoiceResultSerializer(serializers.Serializer):
    """The voice result of a whole talk: its measures and its score. Values
    that couldn't be produced are null."""

    mean_f0 = serializers.FloatField(allow_null=True)  # Hz
    f0_range_q90_q10 = serializers.FloatField(allow_null=True)  # Hz
    mean_f1 = serializers.FloatField(allow_null=True)  # Hz
    mean_f2 = serializers.FloatField(allow_null=True)  # Hz
    mean_f3 = serializers.FloatField(allow_null=True)  # Hz
    h1_h2_corrected = serializers.FloatField(allow_null=True)  # dB
    h1_a3_corrected = serializers.FloatField(allow_null=True)  # dB
    mean_speaking_rate = serializers.FloatField(allow_null=True)  # syllables/s
    mean_pause_duration = serializers.FloatField(allow_null=True)  # s
    pause_frequency = serializers.FloatField(allow_null=True)  # pauses/min
    spl_dbfs = serializers.FloatField(allow_null=True)  # dBFS
    # The overall voice score, 0 to 100.
    voice_score = serializers.FloatField(allow_null=True)


class TalkDetailSerializer(TalkSummarySerializer):
    """A talk in full (get_talk): the short form plus its full voice result
    (null until the talk is processed) and its analysis windows, in time order."""

    full_voice_result = FullVoiceResultSerializer(allow_null=True)
    partial_voice_results = PartialVoiceResultSerializer(many=True)


class SessionSerializer(SessionBaseSerializer):
    """A session in GET /api/sessions/ (the list), without its talks."""

    id = serializers.UUIDField()
    status = serializers.CharField()
    speaker = ProfileSerializer()
    # Null when the trainer's account was deleted.
    trainer = ProfileSerializer(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    ended_at = serializers.DateTimeField(allow_null=True)


class SessionDetailSerializer(SessionSerializer):
    """GET /api/sessions/<id>/: the session with its talks in short form,
    oldest first, discarded ones left out (as get_session loads them)."""

    talks = TalkSummarySerializer(many=True)
