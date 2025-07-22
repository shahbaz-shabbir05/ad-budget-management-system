from django.contrib import admin

from .models import (
    Brand,
    BudgetAdjustment,
    Campaign,
    CampaignStatusHistory,
    DaypartingSchedule,
    SpendRecord,
)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "daily_budget", "monthly_budget")
    search_fields = ("name",)


@admin.register(DaypartingSchedule)
class DaypartingScheduleAdmin(admin.ModelAdmin):
    list_display = ("days_of_week", "start_time", "end_time")
    search_fields = ("days_of_week",)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "brand",
        "daily_spend",
        "monthly_spend",
        "is_active",
        "dayparting_schedule",
    )
    search_fields = ("name", "brand__name")
    list_filter = ("is_active", "brand", "dayparting_schedule")


@admin.register(SpendRecord)
class SpendRecordAdmin(admin.ModelAdmin):
    list_display = [
        "campaign",
        "amount",
        "type",
        "source",
        "timestamp",
        "daily_spend_before",
        "daily_spend_after",
        "monthly_spend_before",
        "monthly_spend_after",
    ]
    list_filter = ["type", "source", "timestamp", "campaign__brand", "campaign"]
    search_fields = [
        "campaign__name",
        "campaign__brand__name",
        "reference_id",
        "description",
        "created_by",
    ]
    readonly_fields = [
        "campaign",
        "amount",
        "type",
        "source",
        "timestamp",
        "created_by",
        "daily_spend_before",
        "daily_spend_after",
        "monthly_spend_before",
        "monthly_spend_after",
        "reference_id",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("campaign", "amount", "type", "source", "timestamp")},
        ),
        ("Audit Trail", {"fields": ("created_by", "reference_id", "description")}),
        (
            "Financial Tracking",
            {
                "fields": (
                    "daily_spend_before",
                    "daily_spend_after",
                    "monthly_spend_before",
                    "monthly_spend_after",
                )
            },
        ),
        (
            "System Information",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("campaign", "campaign__brand")
        )


@admin.register(BudgetAdjustment)
class BudgetAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("amount", "brand", "campaign", "reason", "timestamp", "adjusted_by")
    search_fields = ("brand__name", "campaign__name", "reason", "adjusted_by")
    list_filter = ("timestamp",)


@admin.register(CampaignStatusHistory)
class CampaignStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("campaign", "old_status", "new_status", "timestamp", "reason")
    search_fields = ("campaign__name", "reason")
    list_filter = ("old_status", "new_status", "timestamp")
