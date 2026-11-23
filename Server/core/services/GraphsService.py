"""The graphs of a talk, as the config the timeline charts and score rings
take (web/components/timeline_chart.html, score_ring.html), so every page
and endpoint that shows them builds them the same way.

The caller has already checked the user may see the talk (get_talk).
"""

from core.models import Talk

# The band on the 0 to 100 graph scale: a window score of 50 or more is good
# or medium (ScoresService: 50 at the medium edge), under 50 bad. Until each
# speaker has their own range from earlier talks.
USUAL_RANGE = {"low": 50, "high": 100}


def get_talk_graphs(talk: Talk | None) -> dict:
    """The graphs of `talk`, a talk from get_talk() (its partial voice results
    prefetched in time order), for a page's context or as JSON:

    - `talk`: {"id", "number" (its place in the session, 1 to n, without
      discarded talks), "started_at", "length" (seconds, pauses included)},
      or None for no talk (then the graphs are empty)
    - `voice_config`: on the same 0 to 100 scale as stability, each partial
      result's voice_score (0 to 100, ScoresService) at the
      start of its window, in seconds from the start of the talk (real time,
      so pauses count; the line starts at 0). The band is the usual range
      (USUAL_RANGE); the points outside it are marker dots, which the chart
      colours yellow below it (below usual) and blue above it
    - `stability_config`: empty for now, on the same time axis (the session
      page's talk slider takes its length from it)
    - `speech_score`: the talk's overall voice score, 0 to 100, rounded
    - `stability_score`: None until there is stability data

    The time axis is the talk's real length (recorded time plus its pauses),
    shown one minute at a time (window 60 s, ticks every 10 s): the chart
    moves on to the next minute when the playhead crosses into it.
    """
    meta, points, length, speech_score = None, [], 60, None
    if talk is not None:
        points = [
            [round((window.start_at - talk.started_at).total_seconds(), 1),
             round(window.voice_score, 1)]
            for window in talk.partial_voice_results.all() if window.voice_score is not None
        ]
        paused = sum(((pause.resumed_at - pause.paused_at).total_seconds()
                      for pause in talk.pauses.all() if pause.resumed_at), 0)
        length = round(talk.duration.total_seconds() + paused) if talk.duration else 60
        result = getattr(talk, "full_voice_result", None)
        speech_score = result.voice_score if result is not None else None
        meta = {
            "id": talk.id,
            "number": (talk.session.talks.exclude(status=Talk.Status.DISCARDED)
                       .filter(started_at__lte=talk.started_at).count()),
            "started_at": talk.started_at,
            "length": length,
        }
    x = {"min": 0, "max": length, "interval": 10, "window": 60}

    return {
        "talk": meta,
        "voice_config": {
            "measure": "speech",
            "x": x,
            "y": {"min": 0, "max": 100, "interval": 20},
            "target": USUAL_RANGE,
            "points": points,
            "markers": [point for point in points
                        if not USUAL_RANGE["low"] <= point[1] <= USUAL_RANGE["high"]],
            "time": 0,
        },
        "stability_config": {"measure": "stability", "x": x, "points": [], "time": 0},
        "speech_score": round(speech_score) if speech_score is not None else None,
        "stability_score": None,
    }
