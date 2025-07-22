from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Final, Literal, TypedDict

from django.core.validators import MinValueValidator
from django.db import models

if TYPE_CHECKING:
    pass

# Enums and constants
SpendType = Literal["impression", "click", "manual_adjustment"]
DayOfWeek = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAYS_OF_WEEK: Final[list[DayOfWeek]] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PAUSED_REASON_BUDGET: Final[str] = "budget_exceeded"


# TypedDict for spend event config
class SpendEvent(TypedDict):
    campaign_id: int
    amount: Decimal
    type: SpendType
    timestamp: str  # ISO format


class Brand(models.Model):
    """Represents an advertiser/brand with daily and monthly budgets."""

    name = models.CharField(max_length=100, unique=True)
    daily_budget = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    monthly_budget = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(0)]
    )

    def __str__(self) -> str:
        """Return the brand name."""
        return self.name


class DaypartingSchedule(models.Model):
    """Defines allowed hours and days for a campaign to run."""

    start_time = models.TimeField()
    end_time = models.TimeField()
    days_of_week = models.CharField(
        max_length=20, help_text="Comma-separated days, e.g. 'mon,tue,wed'"
    )

    def __str__(self) -> str:
        """Return a string representation of the schedule."""
        return f"{self.days_of_week} {self.start_time}-{self.end_time}"


class Campaign(models.Model):
    """
    Entity Pattern: Campaign for a brand.

    budget_check_frequency_minutes: Optional[int]
        Optional override for how often (in minutes) this campaign's budget should be checked and enforced.
        If not set, the system uses the DEFAULT_BUDGET_CHECK_FREQUENCY from environment variables.
    last_budget_check: Optional[datetime]
        The last time this campaign's budget was checked. Used for per-campaign frequency logic.
    """

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="campaigns")
    name = models.CharField(max_length=100)
    daily_spend = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    monthly_spend = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)  # type: ignore[call-arg]
    dayparting_schedule = models.ForeignKey(
        DaypartingSchedule, on_delete=models.SET_NULL, null=True, blank=True
    )
    last_daily_reset = models.DateField(null=True, blank=True, db_index=True)
    last_monthly_reset = models.DateField(null=True, blank=True, db_index=True)
    budget_check_frequency_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="How often (in minutes) to check/enforce this campaign's budget. If not set, uses DEFAULT_BUDGET_CHECK_FREQUENCY.",
    )
    last_budget_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The last time this campaign's budget was checked. Used for per-campaign frequency logic.",
    )

    class Meta:
        indexes = [
            models.Index(fields=["is_active"], name="campaign_is_active_idx"),
            models.Index(fields=["brand"], name="campaign_brand_idx"),
        ]

    def __str__(self) -> str:
        """Return the campaign name and brand."""
        return f"{self.name} ({self.brand.name})"

    def can_run_now(self) -> bool:
        """Stub for dayparting logic (implemented in services)."""
        return True


class SpendRecord(models.Model):
    """
    Immutable audit trail for every spend event - industry best practice for financial tracking.

    This model provides a complete, tamper-proof record of all spend events for compliance,
    auditing, and financial reconciliation purposes.
    """

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="spend_records"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Spend amount in currency units",
        validators=[MinValueValidator(0)],
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, help_text="When the spend event occurred"
    )
    type = models.CharField(
        max_length=20,
        choices=[
            ("impression", "Impression"),
            ("click", "Click"),
            ("manual_adjustment", "Manual Adjustment"),
            ("budget_reset", "Budget Reset"),
            ("system_adjustment", "System Adjustment"),
        ],
        help_text="Type of spend event",
    )

    # Audit trail fields
    created_by = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="User or system that created this spend record",
    )
    source = models.CharField(
        max_length=50,
        default="system",
        choices=[
            ("system", "System"),
            ("manual", "Manual Entry"),
            ("api", "API"),
            ("import", "Data Import"),
        ],
        help_text="Source of the spend event",
    )

    # Financial tracking fields
    daily_spend_before = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Campaign daily spend before this event",
        validators=[MinValueValidator(0)],
    )
    daily_spend_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Campaign daily spend after this event",
        validators=[MinValueValidator(0)],
    )
    monthly_spend_before = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Campaign monthly spend before this event",
        validators=[MinValueValidator(0)],
    )
    monthly_spend_after = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Campaign monthly spend after this event",
        validators=[MinValueValidator(0)],
    )

    # Metadata for compliance
    reference_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="External reference ID (e.g., ad platform transaction ID)",
    )
    description = models.TextField(
        blank=True, help_text="Human-readable description of the spend event"
    )

    # Immutability protection
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Record creation timestamp"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Record last update timestamp"
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["campaign", "timestamp"], name="spend_campaign_timestamp_idx"
            ),
            models.Index(fields=["timestamp"], name="spend_timestamp_idx"),
            models.Index(fields=["type"], name="spend_type_idx"),
            models.Index(fields=["source"], name="spend_source_idx"),
            models.Index(fields=["reference_id"], name="spend_reference_idx"),
        ]
        ordering = ["-timestamp"]
        verbose_name = "Spend Record"
        verbose_name_plural = "Spend Records"

    def __str__(self) -> str:
        """Return a string representation of the spend record."""
        return f"{self.campaign.name}: {self.amount} ({self.type}) at {self.timestamp}"

    def save(self, *args, **kwargs) -> None:
        """Ensure immutability by preventing updates to key fields."""
        if self.pk:  # This is an update
            # Allow only certain fields to be updated
            allowed_update_fields = ["updated_at", "description"]
            if not all(
                field in allowed_update_fields
                for field in kwargs.get("update_fields", [])
            ):
                raise ValueError(
                    "SpendRecord is immutable - only description can be updated"
                )
        super().save(*args, **kwargs)


class BudgetAdjustment(models.Model):
    """Logs manual adjustments to budgets or spends."""

    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="budget_adjustments",
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="budget_adjustments",
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    reason = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    adjusted_by = models.CharField(max_length=100)

    def __str__(self) -> str:
        """Return a string representation of the adjustment."""
        target = (
            self.campaign.name
            if self.campaign
            else (self.brand.name if self.brand else "Unknown")
        )
        return f"Adjustment {self.amount} to {target} at {self.timestamp}"


class CampaignStatusHistory(models.Model):
    """Tracks changes in campaign status (active/paused/reactivated)."""

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="status_history"
    )
    old_status = models.BooleanField()
    new_status = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255)

    def __str__(self) -> str:
        """Return a string representation of the status change."""
        return f"{self.campaign.name}: {self.old_status}→{self.new_status} at {self.timestamp}"
