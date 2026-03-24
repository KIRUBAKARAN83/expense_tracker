# insights/daily_insights.py
from datetime import date
from insights.budget_alerts import budget_alerts
from insights.health_score import financial_health_score
from django.contrib.auth.models import User
from insights.models import Insight

def generate_daily_insights():
    today = date.today()

    for user in User.objects.filter(is_active=True):
        alerts = budget_alerts(user)  # list of alert strings
        health = financial_health_score(user)  # dict with "score" and "messages"

        messages = []

        # Assign priority levels to alerts
        for alert in alerts:
            if "⚠️ Expenses exceed income" in alert or "Overspending" in alert:
                priority = "High"
            elif "close to limit" in alert or "increased spending" in alert:
                priority = "Medium"
            else:
                priority = "Low"
            messages.append(f"[{priority}] {alert}")

        # Add health score messages
        for msg in health.get("messages", []):
            score = health.get("score", 0)
            if score < 40:
                priority = "High"
            elif score < 70:
                priority = "Medium"
            else:
                priority = "Low"
            messages.append(f"[{priority}] {msg}")

        # Add a short summary snapshot
        score = health.get("score", 0)
        if score < 40:
            summary = "🔴 Overall financial health: High Risk"
        elif score < 70:
            summary = "🟠 Overall financial health: Medium Risk"
        else:
            summary = "🟢 Overall financial health: Low Risk"
        messages.insert(0, summary)

        # Save insights
        for msg in messages:
            Insight.objects.get_or_create(
                user=user,
                date=today,
                text=msg
            )
