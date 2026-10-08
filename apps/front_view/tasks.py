from celery import shared_task

from apps.front_view import choices, influencer_sync


@shared_task(bind=True, max_retries=choices.INFLUENCER_SYNC_MAX_RETRIES)
def sync_influencer_leaderboard(self, slot):
    attempt = self.request.retries + 1
    try:
        return influencer_sync.run_sync(slot, attempt)
    except Exception as exc:
        influencer_sync.record_failure(slot, attempt, exc)
        raise self.retry(
            exc=exc,
            countdown=choices.INFLUENCER_SYNC_SCHEDULE[slot]["retry_seconds"],
        )
