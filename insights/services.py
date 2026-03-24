# insights/services.py

from django.db.models import Sum
from transactions.models import Transaction, Budget
from datetime import date
import pandas as pd
from .models import DailyInsightSnapshot, MonthlyInsightSnapshot


# =========================================================
# MONTHLY SUMMARY (LIVE COMPUTATION)
# =========================================================

def monthly_summary(user, month=None, year=None):
    today = date.today()
    month = month or today.month
    year = year or today.year

    income = Transaction.objects.filter(
        user=user,
        transaction_type="INCOME",
        date__month=month,
        date__year=year
    ).aggregate(total=Sum("amount"))["total"] or 0

    expense = Transaction.objects.filter(
        user=user,
        transaction_type="EXPENSE",
        date__month=month,
        date__year=year
    ).aggregate(total=Sum("amount"))["total"] or 0

    savings = income - expense

    if savings < 0:
        insight = {
            "icon": "⚠",
            "text": f"Overspent ₹{abs(savings):.2f} this month"
        }
    else:
        insight = {
            "icon": "✔",
            "text": f"Saved ₹{savings:.2f} this month"
        }

    return {
        "income": income,
        "expense": expense,
        "savings": savings,
        "insights": [insight],
    }


# =========================================================
# CATEGORY BREAKDOWN
# =========================================================

def category_breakdown(user, month=None, year=None):
    today = date.today()
    month = month or today.month
    year = year or today.year

    qs = (
        Transaction.objects.filter(
            user=user,
            transaction_type="EXPENSE",
            date__month=month,
            date__year=year
        )
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    return pd.DataFrame(list(qs))


# =========================================================
# DAILY ALERTS (LIVE)
# =========================================================

def generate_daily_insights(user):
    from .budget_alerts import budget_alerts

    messages = budget_alerts(user)
    unique_messages = list(dict.fromkeys(messages))

    formatted = []

    for msg in unique_messages:
        msg_lower = msg.lower()

        if "exceed" in msg_lower:
            icon = "🚨"
        elif "risk" in msg_lower:
            icon = "⚠"
        else:
            icon = "✔"

        formatted.append({
            "icon": icon,
            "text": msg.strip()
        })

    return formatted


# =========================================================
# SNAPSHOT GENERATION
# =========================================================

def generate_daily_snapshot(user):
    today = date.today()

    income = Transaction.objects.filter(
        user=user,
        transaction_type="INCOME",
        date=today
    ).aggregate(total=Sum("amount"))["total"] or 0

    expense = Transaction.objects.filter(
        user=user,
        transaction_type="EXPENSE",
        date=today
    ).aggregate(total=Sum("amount"))["total"] or 0

    alerts = []

    budgets = Budget.objects.filter(user=user)
    for b in budgets:
        spent = Transaction.objects.filter(
            user=user,
            category=b.category,
            transaction_type="EXPENSE",
            date__month=today.month,
            date__year=today.year
        ).aggregate(total=Sum("amount"))["total"] or 0

        if spent > b.limit:
            alerts.append({
                "category": b.category,
                "limit": float(b.limit),
                "spent": float(spent)
            })

    DailyInsightSnapshot.objects.update_or_create(
        user=user,
        date=today,
        defaults={
            "income": income,
            "expense": expense,
            "savings": income - expense,
            "budget_alerts": alerts
        }
    )


def generate_monthly_snapshot(user):
    today = date.today()

    income = Transaction.objects.filter(
        user=user,
        transaction_type="INCOME",
        date__month=today.month,
        date__year=today.year
    ).aggregate(total=Sum("amount"))["total"] or 0

    expense = Transaction.objects.filter(
        user=user,
        transaction_type="EXPENSE",
        date__month=today.month,
        date__year=today.year
    ).aggregate(total=Sum("amount"))["total"] or 0

    breakdown = (
        Transaction.objects.filter(
            user=user,
            transaction_type="EXPENSE",
            date__month=today.month,
            date__year=today.year
        )
        .values("category")
        .annotate(total=Sum("amount"))
    )

    category_data = {
        item["category"]: float(item["total"])
        for item in breakdown
    }

    health_score = int(max(0, 100 - (expense / income * 100))) if income else 0

    MonthlyInsightSnapshot.objects.update_or_create(
        user=user,
        year=today.year,
        month=today.month,
        defaults={
            "total_income": income,
            "total_expense": expense,
            "savings": income - expense,
            "category_breakdown": category_data,
            "health_score": health_score
        }
    )


# =========================================================
# FRONTEND FORMATTER
# =========================================================

def format_insights_for_frontend(user):

    # Generate snapshots safely (idempotent)
    generate_daily_snapshot(user)
    generate_monthly_snapshot(user)

    summary = monthly_summary(user)
    daily = generate_daily_insights(user)

    combined = summary["insights"] + daily

    seen = set()
    unique = []

    for item in combined:
        text = item["text"].strip()
        if text not in seen:
            unique.append(item)
            seen.add(text)

    return {
        "summary": {
            "income": summary["income"],
            "expense": summary["expense"],
            "savings": summary["savings"],
        },
        "insights": unique,
    }