"""Background tasks (Django's Tasks framework, django.tasks), run by the
worker: python manage.py db_worker (django-tasks-db, the queue lives in the
database). Enqueue one with task.enqueue(...); its arguments must be JSON
(ids as strings).

Queues (settings.TASKS):
- analysis: the analysis of a finished talk (analyse_talk), enqueued by
  finish_talk after the commit.
"""
import logging

from django.tasks import task

from core.services.AnalysisService import analyse_talk as run_analysis
from core.services.ScoresService import score_result

logger = logging.getLogger(__name__)

# The bands every speaker is scored with (core/voice_ranges.json: "men" or
# "women"), until the speaker's sex is stored and used instead.
SPEAKER_SEX = "men"


@task(queue_name="analysis")
def analyse_talk(talk_id: str) -> None:
    """The analysis of a finished talk (AnalysisService.analyse_talk): the whole
    talk analysed, scored, saved, the talk COMPLETED; then logged. Every
    speaker is scored as a man (SPEAKER_SEX) until the speaker's sex is
    stored. A failure is logged and raised, so the task's result says FAILED
    (no retries yet)."""
    try:
        result = run_analysis(talk_id, sex=SPEAKER_SEX)
    except Exception:
        logger.exception("Analysis of talk %s failed", talk_id)
        raise
    if result is None:
        logger.info("Talk %s isn't processing any more (discarded?): nothing saved", talk_id)
        return
    measures = {field.name: getattr(result, field.name) for field in result._meta.concrete_fields
                if field.name not in ("id", "talk", "created_at", "voice_score")}
    scores = score_result(result, sex=SPEAKER_SEX)
    logger.info("Analysis of talk %s, voice score %s:\n%s", talk_id,
                "-" if scores["voice_score"] is None else round(scores["voice_score"]),
                "\n".join(f"  {name}: {value}" + (
                    f" (score {round(scores['measures'][name])})" if scores["measures"].get(name) is not None else "")
                    for name, value in measures.items()))
