# insights/chat_engine.py

import os
from datetime import date
from django.db.models import Sum
from groq import Groq
from transactions.models import Transaction, Budget


# =========================================================
# GROQ CLIENT INITIALIZATION (SAFE)
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# =========================================================
# SHARED DATA BUILDER (NO DUPLICATION)
# =========================================================

def _build_financial_context(user):
    today = date.today()

    # Current month totals
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

    # Previous month totals
    last_month = today.month - 1 if today.month > 1 else 12
    last_year = today.year if today.month > 1 else today.year - 1

    prev_income = Transaction.objects.filter(
        user=user,
        transaction_type="INCOME",
        date__month=last_month,
        date__year=last_year
    ).aggregate(total=Sum("amount"))["total"] or 0

    prev_expense = Transaction.objects.filter(
        user=user,
        transaction_type="EXPENSE",
        date__month=last_month,
        date__year=last_year
    ).aggregate(total=Sum("amount"))["total"] or 0

    # Budgets
    budgets = list(
        Budget.objects.filter(user=user).values("category", "limit")
    )

    breakdown = list(
        Transaction.objects.filter(
            user=user,
            transaction_type="EXPENSE",
            date__month=today.month,
            date__year=today.year
        )
        .values("category")
        .annotate(total=Sum("amount"))
    )

    def pct_change(current, previous):
        if previous == 0:
            return "N/A"
        return f"{((current - previous) / previous) * 100:.1f}%"

    income_change = income - prev_income
    expense_change = expense - prev_expense

    income_trend = (
        f"{'↑' if income_change > 0 else '↓'} "
        f"{abs(income_change)} vs last month "
        f"({pct_change(income, prev_income)})"
    )

    expense_trend = (
        f"{'↑' if expense_change > 0 else '↓'} "
        f"{abs(expense_change)} vs last month "
        f"({pct_change(expense, prev_expense)})"
    )

    alerts = []

    if expense > income:
        alerts.append("⚠️ Expenses exceed income this month.")

    for b in budgets:
        spent = next(
            (x["total"] for x in breakdown if x["category"] == b["category"]),
            0
        )
        if spent > b["limit"]:
            alerts.append(
                f"⚠️ Overspending in {b['category']} "
                f"(limit ₹{b['limit']}, spent ₹{spent})."
            )

    return {
        "income": income,
        "expense": expense,
        "income_trend": income_trend,
        "expense_trend": expense_trend,
        "budgets": budgets,
        "breakdown": breakdown,
        "alerts": alerts,
    }


# =========================================================
# PROMPT BUILDER
# =========================================================

def _build_prompt(context, message):

    return f"""
You are a professional financial assistant.

Use ONLY the structured data below when referencing numbers.

Current Income: ₹{context['income']} ({context['income_trend']})
Current Expense: ₹{context['expense']} ({context['expense_trend']})
Budgets: {context['budgets']}
Category Breakdown: {context['breakdown']}
Risk Alerts: {context['alerts']}

User Question:
{message}

Rules:
- Be concise.
- Be actionable.
- Do NOT invent numbers.
- If risk exists, highlight it clearly.
"""


# =========================================================
# NORMAL CHAT
# =========================================================

def finance_chat(user, message):

    if not client:
        return "⚠️ AI service not configured."

    context = _build_financial_context(user)
    prompt = _build_prompt(context, message)

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=300,
        )

        reply = response.choices[0].message.content.strip()

        # 🔒 DO NOT STORE IN Insight TABLE
        return f"💡 Financial Insight:\n{reply}"

    except Exception as e:
        print("GROQ ERROR:", e)
        return "⚠️ AI service temporarily unavailable."


# =========================================================
# STREAMING CHAT
# =========================================================

def finance_chat_stream(user, message):

    if not client:
        yield "⚠️ AI service not configured."
        return

    context = _build_financial_context(user)
    prompt = _build_prompt(context, message)

    try:
        stream = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=300,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

        # 🔒 No DB writes here either

    except Exception as e:
        print("GROQ STREAM ERROR:", e)
        yield "\n⚠️ AI service temporarily unavailable."