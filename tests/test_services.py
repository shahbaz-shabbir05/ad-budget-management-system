from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import cast
from unittest.mock import patch

import pytest
from django.utils import timezone

from ads.models import Brand, Campaign, DaypartingSchedule, SpendRecord
from ads.services import (
    DaypartingWindow,
    check_spend_and_pause_service,
    create_spend_record_for_reset,
    enforce_dayparting,
    is_now_in_window,
    pause_if_budget_exceeded,
    reset_daily_spend,
    reset_monthly_spend,
    track_spend,
)
from ads.utils import TaskMetrics


@pytest.mark.django_db
def test_track_spend_and_pause_if_budget_exceeded():
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("0.00"),
        monthly_spend=Decimal("0.00"),
        is_active=True,
    )
    # Spend within budget
    track_spend(campaign, Decimal("50.00"))
    campaign.refresh_from_db()
    assert campaign.daily_spend == Decimal("50.00")
    assert campaign.monthly_spend == Decimal("50.00")
    assert campaign.is_active is True
    # Spend to exceed daily budget
    track_spend(campaign, Decimal("60.00"))
    campaign.refresh_from_db()
    assert campaign.daily_spend == Decimal("110.00")
    assert campaign.is_active is False


@pytest.mark.django_db
def test_pause_if_budget_exceeded():
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("10.00"),
        monthly_budget=Decimal("100.00"),
    )
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("15.00"),
        monthly_spend=Decimal("20.00"),
        is_active=True,
    )
    pause_if_budget_exceeded(campaign)
    campaign.refresh_from_db()
    assert campaign.is_active is False


@pytest.mark.django_db
def test_reset_daily_spend_and_reactivate():
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    active_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="ActiveCampaign",
        daily_spend=Decimal("50.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
    )
    paused_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="PausedCampaign",
        daily_spend=Decimal("80.00"),
        monthly_spend=Decimal("200.00"),
        is_active=False,
    )
    reset_daily_spend()
    active_campaign.refresh_from_db()
    paused_campaign.refresh_from_db()
    assert active_campaign.daily_spend == Decimal("0.00")
    assert paused_campaign.daily_spend == Decimal("0.00")
    assert paused_campaign.is_active is True


@pytest.mark.django_db
def test_reset_monthly_spend_and_reactivate():
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    active_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="ActiveCampaign",
        daily_spend=Decimal("50.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
    )
    paused_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="PausedCampaign",
        daily_spend=Decimal("80.00"),
        monthly_spend=Decimal("800.00"),
        is_active=False,
    )
    reset_monthly_spend()
    active_campaign.refresh_from_db()
    paused_campaign.refresh_from_db()
    assert active_campaign.monthly_spend == Decimal("0.00")
    assert paused_campaign.monthly_spend == Decimal("0.00")
    assert paused_campaign.is_active is True


@pytest.mark.django_db
def test_enforce_dayparting(monkeypatch):
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
    in_window_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="InWindow",
        daily_spend=Decimal("0.00"),
        monthly_spend=Decimal("0.00"),
        is_active=True,
        dayparting_schedule=schedule,
    )
    out_window_campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="OutWindow",
        daily_spend=Decimal("0.00"),
        monthly_spend=Decimal("0.00"),
        is_active=True,
        dayparting_schedule=schedule,
    )

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


@pytest.mark.django_db
def test_reset_daily_spend_idempotency():
    brand = Brand.objects.create(
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )  # type: ignore[attr-defined]
    campaign = Campaign.objects.create(
        brand=brand, name="Test", daily_spend=Decimal("50.00"), is_active=True
    )  # type: ignore[attr-defined]
    # First reset
    reset_daily_spend()
    campaign.refresh_from_db()
    assert campaign.daily_spend == Decimal("0.00")
    first_reset_date = campaign.last_daily_reset
    # Second reset (should not change anything)
    reset_daily_spend()
    campaign.refresh_from_db()
    assert campaign.daily_spend == Decimal("0.00")
    assert campaign.last_daily_reset == first_reset_date


@pytest.mark.django_db
def test_reset_monthly_spend_idempotency():
    brand = Brand.objects.create(
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )  # type: ignore[attr-defined]
    campaign = Campaign.objects.create(
        brand=brand, name="Test", monthly_spend=Decimal("200.00"), is_active=True
    )  # type: ignore[attr-defined]
    # First reset
    reset_monthly_spend()
    campaign.refresh_from_db()
    assert campaign.monthly_spend == Decimal("0.00")
    first_reset_date = campaign.last_monthly_reset
    # Second reset (should not change anything)
    reset_monthly_spend()
    campaign.refresh_from_db()
    assert campaign.monthly_spend == Decimal("0.00")
    assert campaign.last_monthly_reset == first_reset_date


@pytest.mark.django_db
def test_track_spend_creates_spend_record():
    """Test that track_spend creates a SpendRecord for audit trail."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("10.00"),
        monthly_spend=Decimal("50.00"),
        is_active=True,
    )

    # Track spend
    track_spend(
        campaign=campaign,
        amount=Decimal("25.00"),
        spend_type="click",
        source="api",
        created_by="test_user",
        reference_id="ref_123",
        description="Test click event",
    )

    # Verify SpendRecord was created
    spend_record = SpendRecord.objects.filter(campaign=campaign).first()
    assert spend_record is not None
    assert spend_record.amount == Decimal("25.00")
    assert spend_record.type == "click"
    assert spend_record.source == "api"
    assert spend_record.created_by == "test_user"
    assert spend_record.reference_id == "ref_123"
    assert spend_record.description == "Test click event"
    assert spend_record.daily_spend_before == Decimal("10.00")
    assert spend_record.daily_spend_after == Decimal("35.00")
    assert spend_record.monthly_spend_before == Decimal("50.00")
    assert spend_record.monthly_spend_after == Decimal("75.00")


@pytest.mark.django_db
def test_track_spend_with_metrics():
    """Test track_spend with metrics tracking."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("0.00"),
        monthly_spend=Decimal("0.00"),
        is_active=True,
    )

    # Track spend that will exceed budget
    track_spend(campaign, Decimal("150.00"))

    campaign.refresh_from_db()
    assert campaign.is_active is False  # Should be paused due to budget


@pytest.mark.django_db
def test_pause_if_budget_exceeded_with_metrics():
    """Test pause_if_budget_exceeded with metrics tracking."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("150.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
    )

    metrics = TaskMetrics("test_task")
    was_paused = pause_if_budget_exceeded(campaign, metrics)

    campaign.refresh_from_db()
    assert was_paused is True
    assert campaign.is_active is False
    assert metrics.campaigns_paused == 1


@pytest.mark.django_db
def test_pause_if_budget_exceeded_within_budget():
    """Test pause_if_budget_exceeded when campaign is within budget."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("50.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
    )

    metrics = TaskMetrics("test_task")
    was_paused = pause_if_budget_exceeded(campaign, metrics)

    campaign.refresh_from_db()
    assert was_paused is False
    assert campaign.is_active is True
    assert metrics.campaigns_paused == 0


@pytest.mark.django_db
def test_check_spend_and_pause_service_with_frequency():
    """Test check_spend_and_pause_service respects frequency settings."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )

    # Campaign with custom frequency
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("150.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
        budget_check_frequency_minutes=30,
        last_budget_check=timezone.now() - timedelta(minutes=15),  # Too recent
    )

    metrics = TaskMetrics("test_task")
    check_spend_and_pause_service(metrics)

    campaign.refresh_from_db()
    # Should not be checked due to frequency
    assert campaign.is_active is True
    assert metrics.campaigns_processed == 1


@pytest.mark.django_db
def test_check_spend_and_pause_service_batch_processing():
    """Test check_spend_and_pause_service handles batch processing correctly."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )

    # Create multiple campaigns
    campaigns = []
    for i in range(3):
        campaign = Campaign.objects.create(  # type: ignore[attr-defined]
            brand=brand,
            name=f"TestCampaign{i}",
            daily_spend=Decimal("150.00"),
            monthly_spend=Decimal("200.00"),
            is_active=True,
        )
        campaigns.append(campaign)

    metrics = TaskMetrics("test_task")
    check_spend_and_pause_service(metrics)

    # All campaigns should be processed and paused
    assert metrics.campaigns_processed == 3
    for campaign in campaigns:
        campaign.refresh_from_db()
        assert campaign.is_active is False


@pytest.mark.django_db
def test_create_spend_record_for_reset():
    """Test create_spend_record_for_reset helper function."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("50.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
    )

    # Test daily reset record
    create_spend_record_for_reset(
        campaign=campaign,
        reset_type="daily",
        amount=Decimal("50.00"),
        description="Daily reset test",
    )

    spend_record = SpendRecord.objects.filter(
        campaign=campaign, type="budget_reset"
    ).first()

    assert spend_record is not None
    assert spend_record.amount == Decimal("50.00")
    assert spend_record.source == "system"
    assert spend_record.created_by == "system"
    assert "daily_reset" in spend_record.reference_id
    assert "Daily budget reset: Daily reset test" in spend_record.description
    assert spend_record.daily_spend_before == Decimal("50.00")
    assert spend_record.daily_spend_after == Decimal("0.00")  # Daily reset
    assert spend_record.monthly_spend_before == Decimal("200.00")
    assert spend_record.monthly_spend_after == Decimal("200.00")  # No monthly reset


@pytest.mark.django_db
def test_reset_daily_spend_with_metrics():
    """Test reset_daily_spend with metrics tracking."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )

    # Campaign that will be reactivated
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("80.00"),
        monthly_spend=Decimal("200.00"),
        is_active=False,  # Currently paused
    )

    metrics = TaskMetrics("test_task")
    reset_daily_spend(metrics)

    campaign.refresh_from_db()
    assert campaign.daily_spend == Decimal("0.00")
    assert campaign.is_active is True  # Should be reactivated
    assert metrics.campaigns_reset == 1
    assert metrics.campaigns_reactivated == 1


@pytest.mark.django_db
def test_reset_monthly_spend_with_metrics():
    """Test reset_monthly_spend with metrics tracking."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )

    # Campaign that will be reactivated
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("50.00"),
        monthly_spend=Decimal("800.00"),
        is_active=False,  # Currently paused
    )

    metrics = TaskMetrics("test_task")
    reset_monthly_spend(metrics)

    campaign.refresh_from_db()
    assert campaign.monthly_spend == Decimal("0.00")
    assert campaign.is_active is True  # Should be reactivated
    assert metrics.campaigns_reset == 1
    assert metrics.campaigns_reactivated == 1


@pytest.mark.django_db
def test_enforce_dayparting_with_metrics():
    """Test enforce_dayparting with metrics tracking."""
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

    # Campaign that should be paused (out of window)
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("0.00"),
        monthly_spend=Decimal("0.00"),
        is_active=True,
        dayparting_schedule=schedule,
    )

    # Mock datetime to Monday 8:00 (out-of-window)
    with patch("ads.services.timezone.now") as mock_now:
        mock_now.return_value = datetime(2024, 6, 3, 8, 0)  # Monday, 08:00

        metrics = TaskMetrics("test_task")
        enforce_dayparting(metrics)

        campaign.refresh_from_db()
        assert campaign.is_active is False
        assert metrics.campaigns_paused == 1


def test_is_now_in_window_normal_hours():
    """Test is_now_in_window with normal business hours."""
    with patch("ads.services.timezone.now") as mock_now:
        # Monday 10:00 AM
        mock_now.return_value = datetime(2024, 6, 3, 10, 0)

        window = cast(
            DaypartingWindow,
            {
                "start_time": time(9, 0),
                "end_time": time(17, 0),
                "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            },
        )

        assert is_now_in_window(window) is True


def test_is_now_in_window_outside_hours():
    """Test is_now_in_window outside business hours."""
    with patch("ads.services.timezone.now") as mock_now:
        # Monday 8:00 AM (before start)
        mock_now.return_value = datetime(2024, 6, 3, 8, 0)

        window = cast(
            DaypartingWindow,
            {
                "start_time": time(9, 0),
                "end_time": time(17, 0),
                "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            },
        )

        assert is_now_in_window(window) is False


def test_is_now_in_window_wrong_day():
    """Test is_now_in_window on wrong day of week."""
    with patch("ads.services.timezone.now") as mock_now:
        # Sunday 10:00 AM (not in allowed days)
        mock_now.return_value = datetime(2024, 6, 2, 10, 0)

        window = cast(
            DaypartingWindow,
            {
                "start_time": time(9, 0),
                "end_time": time(17, 0),
                "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            },
        )

        assert is_now_in_window(window) is False


def test_is_now_in_window_overnight():
    """Test is_now_in_window with overnight schedule."""
    with patch("ads.services.timezone.now") as mock_now:
        # Monday 2:00 AM (in overnight window)
        mock_now.return_value = datetime(2024, 6, 3, 2, 0)

        window = cast(
            DaypartingWindow,
            {
                "start_time": time(22, 0),  # 10 PM
                "end_time": time(6, 0),  # 6 AM
                "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            },
        )

        assert is_now_in_window(window) is True


@pytest.mark.django_db
def test_reset_daily_spend_no_reactivation_when_over_budget():
    """Test that campaigns over budget are not reactivated during daily reset."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )

    # Campaign over monthly budget (even after daily reset)
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("80.00"),
        monthly_spend=Decimal("1200.00"),  # Over monthly budget
        is_active=False,
    )

    metrics = TaskMetrics("test_task")
    reset_daily_spend(metrics)

    campaign.refresh_from_db()
    assert campaign.daily_spend == Decimal("0.00")
    assert campaign.is_active is False  # Should remain paused due to monthly budget
    assert metrics.campaigns_reset == 1
    assert metrics.campaigns_reactivated == 0


@pytest.mark.django_db
def test_reset_monthly_spend_no_reactivation_when_over_budget():
    """Test that campaigns over budget are not reactivated during monthly reset."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )

    # Campaign over daily budget (even after monthly reset)
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("150.00"),  # Over daily budget
        monthly_spend=Decimal("800.00"),
        is_active=False,
    )

    metrics = TaskMetrics("test_task")
    reset_monthly_spend(metrics)

    campaign.refresh_from_db()
    assert campaign.monthly_spend == Decimal("0.00")
    assert campaign.is_active is False  # Should remain paused due to daily budget
    assert metrics.campaigns_reset == 1
    assert metrics.campaigns_reactivated == 0


@pytest.mark.django_db
def test_track_spend_error_handling():
    """Test track_spend error handling and logging."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("0.00"),
        monthly_spend=Decimal("0.00"),
        is_active=True,
    )

    # Mock an error during save
    with patch.object(campaign, "save", side_effect=Exception("Database error")):
        with pytest.raises(Exception, match="Database error"):
            track_spend(campaign, Decimal("10.00"))

    # Verify campaign state is unchanged
    campaign.refresh_from_db()
    assert campaign.daily_spend == Decimal("0.00")
    assert campaign.monthly_spend == Decimal("0.00")
    assert campaign.is_active is True


@pytest.mark.django_db
def test_pause_if_budget_exceeded_error_handling():
    """Test pause_if_budget_exceeded error handling."""
    brand = Brand.objects.create(  # type: ignore[attr-defined]
        name="TestBrand",
        daily_budget=Decimal("100.00"),
        monthly_budget=Decimal("1000.00"),
    )
    campaign = Campaign.objects.create(  # type: ignore[attr-defined]
        brand=brand,
        name="TestCampaign",
        daily_spend=Decimal("150.00"),
        monthly_spend=Decimal("200.00"),
        is_active=True,
    )

    # Mock an error during save
    with patch.object(campaign, "save", side_effect=Exception("Database error")):
        with pytest.raises(Exception, match="Database error"):
            pause_if_budget_exceeded(campaign)

    # Verify campaign state is unchanged
    campaign.refresh_from_db()
    assert campaign.is_active is True
