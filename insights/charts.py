import matplotlib
matplotlib.use("Agg")  # IMPORTANT (no GUI)

import matplotlib.pyplot as plt
from django.http import HttpResponse
from .services import category_breakdown
from datetime import date



def expense_category_chart(request):
    today = date.today()

    # ✅ Get month & year from query params
    month = int(request.GET.get("month", today.month))
    year = int(request.GET.get("year", today.year))

    df = category_breakdown(request.user, month, year)

    if df.empty:
        return HttpResponse("No data for selected month")

    plt.figure(figsize=(7, 4))
    plt.bar(df["category"], df["total"], color="#6F4FF2")
    plt.title(f"Expense by Category – {month}/{year}")
    plt.xlabel("Category")
    plt.ylabel("Amount (₹)")
    plt.xticks(rotation=20)
    plt.tight_layout()

    response = HttpResponse(content_type="image/png")
    plt.savefig(response, format="png")
    plt.close()

    return response
