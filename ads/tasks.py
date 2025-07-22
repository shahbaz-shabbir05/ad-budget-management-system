from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Final

from ads.models import DAYS_OF_WEEK, DayOfWeek
from ads.services import (
    check_spend_and_pause_service,
    enforce_dayparting,
    reset_daily_spend,
    reset_monthly_spend,
)
from ads.utils import TaskMetrics, celery_task_with_logging_and_retry

logger = logging.getLogger(__name__)

CHECKED_STATUS: Final[str] = "checked"
REACTIVATED_STATUS: Final[str] = "reactivated"
PAUSED_REASON_DAYPART: Final[str] = "dayparting"

RETRY_KWARGS = {"max_retries": 5, "countdown": 10}


@celery_task_with_logging_and_retry(
    "check_spend_and_pause_task", retry_kwargs=RETRY_KWARGS
)
def check_spend_and_pause_task() -> None:
    check_spend_and_pause_service(TaskMetrics("check_spend_and_pause_task"))


@celery_task_with_logging_and_retry("reset_daily_spend_task", retry_kwargs=RETRY_KWARGS)
def reset_daily_spend_task() -> None:
    reset_daily_spend(TaskMetrics("reset_daily_spend_task"))


@celery_task_with_logging_and_retry(
    "reset_monthly_spend_task", retry_kwargs=RETRY_KWARGS
)
def reset_monthly_spend_task() -> None:
    reset_monthly_spend(TaskMetrics("reset_monthly_spend_task"))


@celery_task_with_logging_and_retry(
    "enforce_dayparting_task", retry_kwargs=RETRY_KWARGS
)
def enforce_dayparting_task() -> None:
    enforce_dayparting(TaskMetrics("enforce_dayparting_task"))


def is_now_in_window(start: time, end: time, days: list[DayOfWeek]) -> bool:
    now = datetime.now()
    now_time = now.time()
    now_day: DayOfWeek = DAYS_OF_WEEK[now.weekday()]
    if now_day not in days:
        return False
    if start <= end:
        return start <= now_time <= end
    else:
        return now_time >= start or now_time <= end
