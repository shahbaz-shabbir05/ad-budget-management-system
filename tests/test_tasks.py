from datetime import datetime, time
from decimal import Decimal

import pytest

from ads.models import Brand, Campaign, DaypartingSchedule
from ads.services import (
    check_spend_and_pause_service,
    enforce_dayparting,
    reset_daily_spend,
    reset_monthly_spend,
)


@pytest.mark.django_db
def test_check_spend_and_pause_pauses_over_budget_campaign():
    # Setup: Brand with budgets
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )

    # Campaign 1: Over daily budget
    over_budget = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="OverBudget",
        daily_spend=Decimal("150.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
    )

    # Campaign 2: Within budget
    within_budget = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="WithinBudget",
        daily_spend=Decimal("50.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
    )

    # Call the task
    check_spend_and_pause_service()

    # Refresh from DB
    over_budget.refresh_from_db()
    within_budget.refresh_from_db()

    # Assert: Over-budget campaign is paused
    assert over_budget.is_active is False

    # Assert: Within-budget campaign remains active
    assert within_budget.is_active is True


@pytest.mark.django_db
def test_reset_daily_spend_resets_and_reactivates():
    # Setup: Brand with budgets
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )

    # Campaign 1: Active, non-zero daily_spend
    active_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="ActiveCampaign",
        daily_spend=Decimal("50.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
    )

    # Campaign 2: Paused, non-zero daily_spend, under budget after reset
    paused_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="PausedCampaign",
        daily_spend=Decimal("80.00"),
        monthly_spend=Decimal("200.00"),
        is_active=False,
    )

    # Call the task
    reset_daily_spend()

    # Refresh from DB
    active_campaign.refresh_from_db()
    paused_campaign.refresh_from_db()

    # Assert: daily_spend is zero for all
    assert active_campaign.daily_spend == Decimal("0.00")
    assert paused_campaign.daily_spend == Decimal("0.00")

    # Assert: eligible paused campaign is reactivated
    assert paused_campaign.is_active is True


@pytest.mark.django_db
def test_reset_monthly_spend_resets_and_reactivates():
    # Setup: Brand with budgets
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )

    # Campaign 1: Active, non-zero monthly_spend
    active_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="ActiveCampaign",
        daily_spend=Decimal("50.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
    )

    # Campaign 2: Paused, non-zero monthly_spend, under budget after reset
    paused_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="PausedCampaign",
        daily_spend=Decimal("80.00"),
        monthly_spend=Decimal("800.00"),
        is_active=False,
    )

    # Call the task
    reset_monthly_spend()

    # Refresh from DB
    active_campaign.refresh_from_db()
    paused_campaign.refresh_from_db()

    # Assert: monthly_spend is zero for all
    assert active_campaign.monthly_spend == Decimal("0.00")
    assert paused_campaign.monthly_spend == Decimal("0.00")

    # Assert: eligible paused campaign is reactivated
    assert paused_campaign.is_active is True


@pytest.mark.django_db
def test_enforce_dayparting():
    # Setup: Brand and DaypartingSchedule for 9am-5pm, Monday only
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    schedule = DaypartingSchedule.objects.create(  # type: ignore[attr-defined]
        start_time=time(9, 0),
        end_time=time(17, 0),
        days_of_week="mon",
    )

    # Campaign 1: Should be active (in-window)
    in_window_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="InWindow",
        daily_spend=Decimal("0.00"),
        monthly_spend=Decimal("0.00"),
        is_active=True,
        dayparting_schedule=schedule,
    )

    # Campaign 2: Should be paused (out-of-window)
    out_window_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="OutWindow",
        daily_spend=Decimal("0.00"),
        monthly_spend=Decimal("0.00"),
        is_active=True,
        dayparting_schedule=schedule,
    )

    from unittest.mock import patch

    # Mock timezone.now to Monday 10:00 (in-window)
    with patch("ads.services.timezone.now") as mock_now:
        mock_now.return_value = datetime(2024, 6, 3, 10, 0)  # Monday, 10:00
        enforce_dayparting()
        in_window_campaign.refresh_from_db()
        out_window_campaign.refresh_from_db()
        assert in_window_campaign.is_active is True

    # Mock timezone.now to Monday 8:00 (out-of-window)
    with patch("ads.services.timezone.now") as mock_now:
        mock_now.return_value = datetime(2024, 6, 3, 8, 0)  # Monday, 08:00
        enforce_dayparting()
        in_window_campaign.refresh_from_db()
        out_window_campaign.refresh_from_db()
        assert in_window_campaign.is_active is False
        assert out_window_campaign.is_active is False
