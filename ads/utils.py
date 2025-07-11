import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from functools import wraps
from typing import Any, Callable, TypeVar, cast

T = TypeVar("T", bound=Callable[..., Any])

logger = logging.getLogger(__name__)

DEFAULT_RETRY_KWARGS = {"max_retries": 5, "countdown": 10}

@dataclass
class TaskMetrics:
    """Tracks and logs metrics for Celery tasks."""
    task_name: str
    start_time: datetime = field(default_factory=datetime.now)
    campaigns_processed: int = 0
    campaigns_paused: int = 0
    campaigns_reactivated: int = 0
    campaigns_reset: int = 0
    errors: int = 0

    def log_summary(self) -> None:
        duration = datetime.now() - self.start_time
        logger.info(
            "Task %s completed: processed=%d, paused=%d, reactivated=%d, reset=%d, errors=%d, duration=%s",
            self.task_name,
            self.campaigns_processed,
            self.campaigns_paused,
            self.campaigns_reactivated,
            self.campaigns_reset,
            self.errors,
            duration,
        )

def log_campaign_event(
    logger_instance: logging.Logger, event_type: str, campaign, **kwargs
) -> None:
    """Logs a campaign event with context."""
    campaign_id = getattr(campaign, "id", None)
    brand_name = (
        getattr(campaign.brand, "name", None) if hasattr(campaign, "brand") else None
    )
    base_msg = f"Campaign event {event_type}: id={campaign_id}, brand={brand_name}"
    if kwargs:
        context_parts = [f"{k}={v}" for k, v in kwargs.items()]
        base_msg += f", {', '.join(context_parts)}"
    logger_instance.info(base_msg)

def log_service_error(
    logger_instance: logging.Logger,
    service_name: str,
    error: Exception,
    campaign_id: Any = None,
) -> None:
    """Logs errors from service functions."""
    if campaign_id:
        logger_instance.error(
            "%s failed for campaign %s: %s",
            service_name,
            campaign_id,
            error,
            exc_info=True,
        )
    else:
        logger_instance.error("%s failed: %s", service_name, error, exc_info=True)

def celery_task_with_logging_and_retry(
    task_name: str, retry_kwargs: dict[str, int] | None = None
):
    """Decorator for Celery tasks to add logging and retry."""
    def decorator(func: T) -> T:
        from celery import shared_task
        actual_retry_kwargs = (
            retry_kwargs if retry_kwargs is not None else DEFAULT_RETRY_KWARGS
        )
        @shared_task(
            autoretry_for=(Exception,),
            retry_kwargs=actual_retry_kwargs,
            retry_backoff=True,
            retry_jitter=True,
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"Starting {task_name}")
            try:
                result = func(*args, **kwargs)
                logger.info(f"Finished {task_name} successfully")
                return result
            except Exception as e:
                logger.error(f"{task_name} failed: {e}", exc_info=True)
                raise
        return cast(T, wrapper)
    return decorator
