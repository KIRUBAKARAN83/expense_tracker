# insights/health_score.py
from django.db.models import Sum
from datetime import date
from transactions.models import Transaction, Budget

def financial_health_score(user):
    today = date.today()

    # ================= CURRENT MONTH =================
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

    # ================= SAVINGS (40 pts) =================
    savings_rate = max((income - expense) / income, 0) if income > 0 else 0
    savings_score = min(round(savings_rate * 40), 40)

    # ================= EXPENSE CONTROL (30 pts) =================
    expense_ratio = expense / income if income > 0 else 1
    expense_score = max(round(30 - (expense_ratio * 30)), 0)

    # ================= BUDGET DISCIPLINE (20 pts) =================
    budgets = Budget.objects.filter(user=user)
    violations = 0

    for b in budgets:
        spent = Transaction.objects.filter(
            user=user,
            category=b.category,
            transaction_type="EXPENSE",
            date__month=today.month,
            date__year=today.year
        ).aggregate(total=Sum("amount"))["total"] or 0

        if spent > b.limit:
            violations += 1

    budget_score = max(20 - (violations * 5), 0)

    # ================= INCOME STABILITY (10 pts) =================
    income_score = 10 if income > 0 else 0

    # ================= TOTAL =================
    total_score = savings_score + expense_score + budget_score + income_score

    # ================= GRADE =================
    if total_score >= 80:
        grade = "Excellent"
        color = "success"
        short_msg = "🟢 Strong financial health this month."
    elif total_score >= 60:
        grade = "Good"
        color = "primary"
        short_msg = "🟠 Finances are stable, but watch spending."
    elif total_score >= 40:
        grade = "Average"
        color = "warning"
        short_msg = "🟡 Financial health is average, improve savings."
    else:
        grade = "Poor"
        color = "danger"
        short_msg = "🔴 High risk: expenses outweigh savings."

    # ================= TREND (PREVIOUS MONTH) =================
    prev_month = today.month - 1 or 12
    prev_year = today.year if today.month != 1 else today.year - 1

    prev_income = Transaction.objects.filter(
        user=user,
        transaction_type="INCOME",
        date__month=prev_month,
        date__year=prev_year
    ).aggregate(total=Sum("amount"))["total"] or 0

    prev_expense = Transaction.objects.filter(
        user=user,
        transaction_type="EXPENSE",
        date__month=prev_month,
        date__year=prev_year
    ).aggregate(total=Sum("amount"))["total"] or 0

    prev_savings_rate = max((prev_income - prev_expense) / prev_income, 0) if prev_income > 0 else 0
    prev_score = min(round(prev_savings_rate * 40), 40)

    if total_score > prev_score:
        trend = "up"
        trend_msg = "📈 Better than last month."
    elif total_score < prev_score:
        trend = "down"
        trend_msg = "📉 Worse than last month."
    else:
        trend = "stable"
        trend_msg = "➖ Same as last month."

    # ================= RETURN =================
    return {
        "health_score": total_score,
        "health_grade": grade,
        "health_color": color,
        "trend": trend,
        "breakdown": {
            "savings": savings_score,
            "expenses": expense_score,
            "budget": budget_score,
            "stability": income_score,
        },
        # 👇 Short, clear insights for UI or notifications
        "messages": [
            short_msg,
            trend_msg
        ]
    }
