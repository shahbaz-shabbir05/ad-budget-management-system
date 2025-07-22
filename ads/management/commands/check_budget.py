import logging

from django.core.management.base import BaseCommand

from ads.tasks import check_spend_and_pause_task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Manually trigger the budget enforcement logic (pauses campaigns over budget). "
        "Use as a fallback if Celery Beat is down."
    )

    def handle(self, *args, **options) -> None:
        check_spend_and_pause_task.delay()
        logger.info("Queued budget enforcement task.")
        self.stdout.write(self.style.SUCCESS("Queued budget enforcement task."))
