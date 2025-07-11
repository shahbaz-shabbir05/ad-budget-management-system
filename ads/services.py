from __future__ import annotations

import logging
from datetime import time, timedelta
from decimal import Decimal
from typing import Final, Optional, TypedDict, cast

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ads.models import DAYS_OF_WEEK, Campaign, DayOfWeek, SpendRecord
from ads.utils import TaskMetrics, log_campaign_event, log_service_error

# Logger for service-level error reporting
logger: Final = logging.getLogger(__name__)


# Value Object Pattern for dayparting window
class DaypartingWindow(TypedDict):
    start_time: time
    end_time: time
    days_of_week: list[DayOfWeek]


PAUSED_REASON_BUDGET: Final[str] = "budget_exceeded"
PAUSED_REASON_DAYPART: Final[str] = "dayparting"
REACTIVATED_STATUS: Final[str] = "reactivated"

DATE_FMT: Final = "%Y-%m-%d"


def track_spend(
    campaign: Campaign,
    amount: Decimal,
    spend_type: str = "impression",
    source: str = "system",
    created_by: str | None = None,
    reference_id: str | None = None,
    description: str = "",
) -> None:
    try:
        with transaction.atomic():
            # Capture spend values before the update
            daily_spend_before = campaign.daily_spend
            monthly_spend_before = campaign.monthly_spend

            # Update campaign spend
            campaign.daily_spend = Decimal(str(campaign.daily_spend)) + amount  # type: ignore[operator]
            campaign.monthly_spend = Decimal(str(campaign.monthly_spend)) + amount  # type: ignore[operator]
            campaign.save(update_fields=["daily_spend", "monthly_spend"])

            # Create immutable audit trail
            SpendRecord.objects.create(
                campaign=campaign,
                amount=amount,
                type=spend_type,
                source=source,
                created_by=created_by,
                reference_id=reference_id,
                description=description,
                daily_spend_before=daily_spend_before,
                daily_spend_after=campaign.daily_spend,
                monthly_spend_before=monthly_spend_before,
                monthly_spend_after=campaign.monthly_spend,
            )

            # Check if budget exceeded and pause if needed
            pause_if_budget_exceeded(campaign)
    except Exception as e:
        log_service_error(logger, "track_spend", e, getattr(campaign, "id", None))
        raise


def pause_if_budget_exceeded(
    campaign: Campaign, metrics: TaskMetrics | None = None
) -> bool:
    try:
        # Pre-fetch brand data should already be available from select_related
        # This avoids additional database queries
        with transaction.atomic():
            if Decimal(str(campaign.daily_spend)) > Decimal(
                str(campaign.brand.daily_budget)
            ) or Decimal(  # type: ignore[operator, attr-defined]
                str(campaign.monthly_spend)
            ) > Decimal(
                str(campaign.brand.monthly_budget)
            ):  # type: ignore[operator, attr-defined]
                campaign.is_active = False
                # Use update_fields to minimize database writes
                campaign.save(update_fields=["is_active"])
                if metrics:
                    metrics.campaigns_paused += 1
                # Log pause event for observability
                log_campaign_event(
                    logger,
                    "paused_budget",
                    campaign,
                    daily_spend=str(campaign.daily_spend),
                    monthly_spend=str(campaign.monthly_spend),
                    daily_budget=str(campaign.brand.daily_budget),
                    monthly_budget=str(campaign.brand.monthly_budget),
                )
                return True
            return False
    except Exception as e:
        if metrics:
            metrics.errors += 1
        log_service_error(
            logger, "pause_if_budget_exceeded", e, getattr(campaign, "id", None)
        )
        raise


def check_spend_and_pause_service(metrics: Optional[TaskMetrics] = None) -> None:
    now = timezone.now()
    try:
        active_campaigns = Campaign.objects.filter(is_active=True).select_related(
            "brand"
        )
        batch_size = 100
        for i in range(0, active_campaigns.count(), batch_size):
            batch = active_campaigns[i : i + batch_size]
            for campaign in batch:
                if metrics:
                    metrics.campaigns_processed += 1
                freq: int = (
                    campaign.budget_check_frequency_minutes
                    or settings.DEFAULT_BUDGET_CHECK_FREQUENCY
                )
                last_check = getattr(campaign, "last_budget_check", None)
                if not last_check:
                    last_check = now - timedelta(minutes=freq)
                if now >= last_check + timedelta(minutes=freq):
                    log_campaign_event(logger, "checking", campaign, frequency=freq)
                    was_paused = pause_if_budget_exceeded(campaign, metrics)
                    campaign.last_budget_check = now
                    campaign.save(update_fields=["last_budget_check"])
    except Exception as e:
        if metrics:
            metrics.errors += 1
        log_service_error(logger, "check_spend_and_pause_service", e)
        raise


def create_spend_record_for_reset(
    campaign: Campaign, reset_type: str, amount: Decimal, description: str = ""
) -> None:
    try:
        SpendRecord.objects.create(
            campaign=campaign,
            amount=amount,
            type="budget_reset",
            source="system",
            created_by="system",
            reference_id=f"{reset_type}_reset_{timezone.now().date()}",
            description=f"{reset_type.capitalize()} budget reset: {description}",
            daily_spend_before=campaign.daily_spend,
            daily_spend_after=(
                campaign.daily_spend if reset_type == "monthly" else Decimal("0.00")
            ),
            monthly_spend_before=campaign.monthly_spend,
            monthly_spend_after=(
                campaign.monthly_spend if reset_type == "daily" else Decimal("0.00")
            ),
        )
    except Exception as e:
        # Log error but don't fail the reset operation
        log_service_error(
            logger, "create_spend_record_for_reset", e, getattr(campaign, "id", None)
        )


def reset_daily_spend(metrics: Optional[TaskMetrics] = None) -> None:
    today = timezone.now().date()
    try:
        for campaign in Campaign.objects.exclude(last_daily_reset=today).select_related(
            "brand"
        ):
            with transaction.atomic():
                # Capture spend before reset for audit trail
                daily_spend_before = campaign.daily_spend

                campaign.daily_spend = Decimal("0.00")
                campaign.last_daily_reset = today
                reactivated = False
                if (
                    not campaign.is_active
                    and campaign.daily_spend <= campaign.brand.daily_budget  # type: ignore[attr-defined]
                    and campaign.monthly_spend <= campaign.brand.monthly_budget  # type: ignore[attr-defined]
                ):
                    campaign.is_active = True
                    reactivated = True
                    if metrics:
                        metrics.campaigns_reactivated += 1
                campaign.save(
                    update_fields=["daily_spend", "is_active", "last_daily_reset"]
                )
                if metrics:
                    metrics.campaigns_reset += 1

                # Create audit trail for the reset
                if daily_spend_before > 0:
                    create_spend_record_for_reset(
                        campaign,
                        "daily",
                        daily_spend_before,
                        f"Reset daily spend from {daily_spend_before} to 0.00",
                    )

                if reactivated:
                    # Log reactivation event
                    log_campaign_event(
                        logger,
                        "reactivated",
                        campaign,
                        reset_type="daily",
                        timestamp=str(today),
                    )
    except Exception as e:
        if metrics:
            metrics.errors += 1
        log_service_error(logger, "reset_daily_spend", e)
        raise


def reset_monthly_spend(metrics: Optional[TaskMetrics] = None) -> None:
    today = timezone.now().date()
    first_of_month = today.replace(day=1)
    try:
        for campaign in Campaign.objects.exclude(
            last_monthly_reset=first_of_month
        ).select_related("brand"):
            with transaction.atomic():
                # Capture spend before reset for audit trail
                monthly_spend_before = campaign.monthly_spend

                campaign.monthly_spend = Decimal("0.00")
                campaign.last_monthly_reset = first_of_month
                reactivated = False
                if (
                    not campaign.is_active
                    and campaign.daily_spend <= campaign.brand.daily_budget  # type: ignore[attr-defined]
                    and campaign.monthly_spend <= campaign.brand.monthly_budget  # type: ignore[attr-defined]
                ):
                    campaign.is_active = True
                    reactivated = True
                    if metrics:
                        metrics.campaigns_reactivated += 1
                campaign.save(
                    update_fields=["monthly_spend", "is_active", "last_monthly_reset"]
                )
                if metrics:
                    metrics.campaigns_reset += 1

                # Create audit trail for the reset
                if monthly_spend_before > 0:
                    create_spend_record_for_reset(
                        campaign,
                        "monthly",
                        monthly_spend_before,
                        f"Reset monthly spend from {monthly_spend_before} to 0.00",
                    )

                if reactivated:
                    # Log reactivation event
                    log_campaign_event(
                        logger,
                        "reactivated",
                        campaign,
                        reset_type="monthly",
                        timestamp=str(today),
                    )
    except Exception as e:
        if metrics:
            metrics.errors += 1
        log_service_error(logger, "reset_monthly_spend", e)
        raise


def is_now_in_window(window: DaypartingWindow) -> bool:
    """
    Value Object Pattern: Check if now is in the allowed window.
    """
    now = timezone.now()
    now_time = now.time()
    now_day: DayOfWeek = DAYS_OF_WEEK[now.weekday()]
    if now_day not in window["days_of_week"]:
        return False
    start = window["start_time"]
    end = window["end_time"]
    if start <= end:
        return start <= now_time <= end
    else:
        return now_time >= start or now_time <= end


def enforce_dayparting(metrics: TaskMetrics | None = None) -> None:
    """
    Domain Service Pattern: Enforce dayparting for all campaigns. Logs errors and dayparting events for observability.
    """
    try:
        campaigns = Campaign.objects.exclude(dayparting_schedule=None)  # type: ignore[attr-defined]
        for campaign in campaigns:
            if metrics:
                metrics.campaigns_processed += 1
            sched = campaign.dayparting_schedule
            if not sched:
                continue
            days_of_week = cast(
                list[DayOfWeek],
                [d for d in sched.days_of_week.split(",") if d.strip() in DAYS_OF_WEEK],
            )
            window: DaypartingWindow = {
                "start_time": sched.start_time,
                "end_time": sched.end_time,
                "days_of_week": days_of_week,
            }
            now = timezone.now()
            schedule_str = f"{days_of_week} {sched.start_time}-{sched.end_time}"
            if is_now_in_window(window):
                if not campaign.is_active and campaign.daily_spend <= campaign.brand.daily_budget and campaign.monthly_spend <= campaign.brand.monthly_budget:  # type: ignore[attr-defined]
                    campaign.is_active = True
                    campaign.save(update_fields=["is_active"])
                    if metrics:
                        metrics.campaigns_reactivated += 1
                    # Log reactivation due to dayparting
                    log_campaign_event(
                        logger,
                        "reactivated_dayparting",
                        campaign,
                        schedule=schedule_str,
                        now=str(now),
                    )
            else:
                if campaign.is_active:
                    campaign.is_active = False
                    campaign.save(update_fields=["is_active"])
                    if metrics:
                        metrics.campaigns_paused += 1
                    # Log pause due to dayparting
                    log_campaign_event(
                        logger,
                        "paused_dayparting",
                        campaign,
                        schedule=schedule_str,
                        now=str(now),
                    )
    except Exception as e:
        if metrics:
            metrics.errors += 1
        log_service_error(logger, "enforce_dayparting", e)
        raise
