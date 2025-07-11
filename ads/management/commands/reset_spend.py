import logging
from typing import Final, Literal

from django.core.management.base import BaseCommand, CommandParser

from ads.tasks import reset_daily_spend_task, reset_monthly_spend_task

logger = logging.getLogger(__name__)

RESET_TYPE_DAILY: Final[str] = "daily"
RESET_TYPE_MONTHLY: Final[str] = "monthly"
RESET_TYPE_CHOICES: tuple[str, ...] = (RESET_TYPE_DAILY, RESET_TYPE_MONTHLY)


class Command(BaseCommand):
    help = "Manually trigger daily or monthly spend resets. Use as a fallback if Celery Beat is down."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--type",
            type=str,
            choices=RESET_TYPE_CHOICES,
            required=True,
            help="Type of reset: 'daily' or 'monthly'",
        )

    def handle(self, *args, **options) -> None:
        reset_type: Literal["daily", "monthly"] = options["type"]
        if reset_type == RESET_TYPE_DAILY:
            reset_daily_spend_task.delay()
            logger.info("Queued daily spend reset task.")
            self.stdout.write(self.style.SUCCESS("Queued daily spend reset task."))
        elif reset_type == RESET_TYPE_MONTHLY:
            reset_monthly_spend_task.delay()
            logger.info("Queued monthly spend reset task.")
            self.stdout.write(self.style.SUCCESS("Queued monthly spend reset task."))
        else:
            self.stderr.write(self.style.ERROR(f"Unknown reset type: {reset_type}"))
