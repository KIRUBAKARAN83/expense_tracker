from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now


# =========================================================
# CHAT INSIGHTS (Optional Storage)
# =========================================================

class Insight(models.Model):
    """
    Stores chat-based insights only.
    SYSTEM insights should NOT be stored here anymore.
    """

    INSIGHT_TYPES = [
        ("CHAT", "Chat Generated"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chat_insights"
    )

    insight_type = models.CharField(
        max_length=20,
        choices=INSIGHT_TYPES,
        default="CHAT"
    )

    text = models.TextField()

    date = models.DateField(default=now)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"CHAT | {self.user.username} | {self.date}"


# =========================================================
# DAILY SNAPSHOT (Historical Analytics)
# =========================================================

class DailyInsightSnapshot(models.Model):
    """
    Stores computed daily financial state.
    Used for analytics & historical tracking.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="daily_snapshots"
    )

    date = models.DateField(default=now)

    income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    savings = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    budget_alerts = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self):
        return f"DailySnapshot | {self.user.username} | {self.date}"


# =========================================================
# MONTHLY SNAPSHOT (Analytics Engine)
# =========================================================

class MonthlyInsightSnapshot(models.Model):
    """
    Stores aggregated monthly financial state.
    Enables growth tracking, health scoring, and trends.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="monthly_snapshots"
    )

    year = models.IntegerField()
    month = models.IntegerField()

    total_income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    savings = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    category_breakdown = models.JSONField(default=dict)

    health_score = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "year", "month")
        ordering = ["-year", "-month"]
        indexes = [
            models.Index(fields=["user", "year", "month"]),
        ]

    def __str__(self):
        return f"MonthlySnapshot | {self.user.username} | {self.month}/{self.year}"