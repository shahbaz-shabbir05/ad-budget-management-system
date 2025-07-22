from __future__ import annotations

from datetime import time
from decimal import Decimal
from typing import Final

from django.core.management.base import BaseCommand
from django.db import transaction

from ads.models import Brand, Campaign, DaypartingSchedule

BRAND_NAME: Final[str] = "Lorem Ipsum Inc."
CAMPAIGN_NAMES: Final[list[str]] = ["Lorem Ipsum Summer", "Dolor Sit Winter"]
DAILY_BUDGET: Final[Decimal] = Decimal("500.00")
MONTHLY_BUDGET: Final[Decimal] = Decimal("15000.00")
START_TIME: Final[time] = time(9, 0)
END_TIME: Final[time] = time(17, 0)
DAYS_OF_WEEK: Final[str] = "mon,tue,wed,thu,fri"


class Command(BaseCommand):
    help = "Seed essential baseline data for local development and staging. Idempotent."

    def handle(self, *args, **options) -> None:
        with transaction.atomic():
            # Brand
            brand, created_brand = Brand.objects.get_or_create(
                name=BRAND_NAME,
                defaults={
                    "daily_budget": DAILY_BUDGET,
                    "monthly_budget": MONTHLY_BUDGET,
                },
            )
            if created_brand:
                self.stdout.write(self.style.SUCCESS(f"Created brand: {brand.name}"))
            else:
                self.stdout.write(
                    self.style.WARNING(f"Brand already exists: {brand.name}")
                )

            # DaypartingSchedule
            schedule, created_schedule = DaypartingSchedule.objects.get_or_create(
                start_time=START_TIME,
                end_time=END_TIME,
                days_of_week=DAYS_OF_WEEK,
            )
            if created_schedule:
                self.stdout.write(
                    self.style.SUCCESS(f"Created dayparting schedule: {schedule}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Dayparting schedule already exists: {schedule}"
                    )
                )

            # Campaigns
            for i, campaign_name in enumerate(CAMPAIGN_NAMES):
                campaign, created_campaign = Campaign.objects.get_or_create(
                    brand=brand,
                    name=campaign_name,
                    defaults={
                        "daily_spend": Decimal("0.00") if i == 0 else Decimal("10.00"),
                        "monthly_spend": (
                            Decimal("0.00") if i == 0 else Decimal("100.00")
                        ),
                        "is_active": True,
                        "dayparting_schedule": schedule,
                    },
                )
                if created_campaign:
                    self.stdout.write(
                        self.style.SUCCESS(f"Created campaign: {campaign.name}")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Campaign already exists: {campaign.name}")
                    )

        self.stdout.write(self.style.SUCCESS("Seeding complete."))
