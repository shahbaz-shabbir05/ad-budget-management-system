import logging

from django.core.management.base import BaseCommand

from ads.tasks import enforce_dayparting_task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Manually trigger dayparting enforcement (pauses/unpauses campaigns based on allowed hours). Use as a fallback if Celery Beat is down."

    def handle(self, *args, **options) -> None:
        enforce_dayparting_task.delay()
        logger.info("Queued dayparting enforcement task.")
        self.stdout.write(self.style.SUCCESS("Queued dayparting enforcement task."))
