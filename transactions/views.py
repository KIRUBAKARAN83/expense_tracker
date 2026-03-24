# transactions/views.py
import json
import os
import time
import tempfile
import logging
import requests
from datetime import date, timedelta

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now

from .models import Transaction, Budget
from .forms import TransactionForm, BudgetForm
from .utils import parse_finance_text, normalize_amount
from .pdf import monthly_pdf

from insights.services import (
    monthly_summary,
    category_breakdown,
    generate_daily_insights,
)
from insights.health_score import financial_health_score
from insights.budget_alerts import budget_alerts
from insights.month_compare import month_comparison
from insights.budget_progress import budget_progress
from insights.budget_suggest import suggest_budgets
from insights.chat_engine import finance_chat, finance_chat_stream
from accounts.models import UserActivity
from insights.models import Insight

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
#from openai import OpenAI
from groq import Groq  # for direct Groq API usage in transcription
# OpenAI client (optional usage in other parts)
client =Groq (api_key=os.getenv("GROQ_API_KEY"))

# Groq transcription config (used by audio-to-transaction endpoint)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"

# Directory for assembling voice chunks (can be overridden in Django settings)
VOICE_CHUNK_DIR = getattr(settings, "VOICE_CHUNK_DIR", os.path.join(tempfile.gettempdir(), "voice_chunks"))

app_name = "transactions"
import logging
logger = logging.getLogger(__name__)


# =========================================================
# USER DASHBOARD
# =========================================================
# insights/views.py



from insights.services import format_insights_for_frontend






@login_required
def dashboard(request):
    today = date.today()

    # ====================================================
    # 1️⃣ Insights + Snapshots (Handled in Services Layer)
    # ====================================================
    insights_payload = format_insights_for_frontend(request.user)

    # ====================================================
    # 2️⃣ Financial Metrics
    # ====================================================
    health = financial_health_score(request.user)
    comparison = month_comparison(request.user)
    budgets = budget_progress(request.user)

    # ====================================================
    # 3️⃣ Transactions + Search
    # ====================================================
    query = request.GET.get("q", "").strip()

    transactions_qs = Transaction.objects.filter(
        user=request.user,
        date__month=today.month,
        date__year=today.year,
    )

    if query:
        transactions_qs = transactions_qs.filter(
            Q(category__icontains=query)
            | Q(description__icontains=query)
            | Q(transaction_type__icontains=query)
        )

    transactions = Paginator(
        transactions_qs.order_by("-date"),
        10
    ).get_page(request.GET.get("page"))

    # ====================================================
    # 4️⃣ Render
    # ====================================================
    return render(
        request,
        "dashboard.html",
        {
            "summary": insights_payload["summary"],
            "insights": insights_payload["insights"],
            **health,
            "comparison": comparison,
            "budgets": budgets,
            "transactions": transactions,
            "query": query,
        },
    )
#===============================
# TRANSACTION CRUD
# =========================================================
from insights.transaction_parser import parse_transaction_text

@login_required
def add_transaction(request):

    if request.method == "POST":
        form = TransactionForm(request.POST)

        if form.is_valid():

            txn = form.save(commit=False)
            txn.user = request.user

            # AI auto-fill fallback
            ai = parse_transaction_text(txn.description)

            if not txn.amount:
                txn.amount = ai["amount"]

            if not txn.category:
                txn.category = ai["category"]

            if not txn.transaction_type:
                txn.transaction_type = ai["transaction_type"]

            if not txn.date:
                txn.date = ai["date"]

            txn.save()

            return redirect("dashboard")

    else:
        form = TransactionForm()

    return render(request, "transaction_form.html", {"form": form})
# transactions/views.py


@login_required
def edit_transaction(request, pk):
    txn = get_object_or_404(Transaction, pk=pk, user=request.user)
    form = TransactionForm(request.POST or None, instance=txn)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("dashboard")
    return render(request, "transaction_form.html", {"form": form})


@login_required
def delete_transaction(request, pk):
    txn = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == "POST":
        txn.delete()
        return redirect("dashboard")
    return render(request, "confirm_delete.html", {"transaction": txn})


# =========================================================
# CHART DATA (AJAX)
# =========================================================
@login_required
def chart_data(request):
    today = date.today()
    income = Transaction.objects.filter(
        user=request.user,
        transaction_type="INCOME",
        date__month=today.month,
        date__year=today.year,
    ).aggregate(total=Sum("amount"))["total"] or 0

    expense = Transaction.objects.filter(
        user=request.user,
        transaction_type="EXPENSE",
        date__month=today.month,
        date__year=today.year,
    ).aggregate(total=Sum("amount"))["total"] or 0

    return JsonResponse({
        "income": float(income),
        "expense": float(expense),
        "savings": float(income - expense),
    })


# =========================================================
# ALL TRANSACTIONS PAGE
# =========================================================
@login_required
def all_transactions(request):
    query = request.GET.get("q", "").strip()
    start_date = request.GET.get("start")
    end_date = request.GET.get("end")

    qs = Transaction.objects.filter(user=request.user)

    if query:
        qs = qs.filter(
            Q(category__icontains=query)
            | Q(description__icontains=query)
            | Q(transaction_type__icontains=query)
        )
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)

    qs = qs.order_by("-date")
    transactions = Paginator(qs, 15).get_page(request.GET.get("page"))

    return render(
        request,
        "all_transaction.html",
        {
            "transactions": transactions,
            "query": query,
            "start_date": start_date,
            "end_date": end_date,
        },
    )


# =========================================================
# BUDGETS
# =========================================================
@login_required
def create_budget(request):
    if request.method == "POST":
        form = BudgetForm(request.POST)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            return redirect("dashboard")
    else:
        form = BudgetForm()
    return render(
        request,
        "budget_form.html",
        {"form": form, "suggestions": suggest_budgets(request.user)},
    )


@login_required
def budgets_list(request):
    budgets = Budget.objects.filter(user=request.user)
    return render(request, "budgets_list.html", {"budgets": budgets})


@login_required
def delete_budget(request, budget_id):
    budget = get_object_or_404(Budget, id=budget_id, user=request.user)
    budget.delete()
    return redirect("budgets_list")


# =========================================================
# AI CHATBOT API
# =========================================================
import json
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from insights.chat_engine import finance_chat, finance_chat_stream

@login_required
@require_POST
def chat_api(request):
    try:
        data = json.loads(request.body)
        msg = data.get("message", "").strip()
        if not msg:
            return JsonResponse({"reply": "Ask something 🙂"})
        reply = finance_chat(request.user, msg)
        return JsonResponse({"reply": reply})
    except Exception as e:
        print("CHAT ERROR:", e)
        return JsonResponse({"reply": "⚠️ AI error. Try again."}, status=500)


@login_required
@require_POST
def chat_stream(request):
    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
        if not message:
            return StreamingHttpResponse("⚠️ Empty message", content_type="text/plain")

        def event_stream():
            try:
                for token in finance_chat_stream(request.user, message):
                    yield token
            except Exception as e:
                print("STREAM ERROR:", e)
                yield "\n⚠️ AI error"

        return StreamingHttpResponse(event_stream(), content_type="text/plain")

    except Exception as e:
        print("CHAT STREAM ERROR:", e)
        return StreamingHttpResponse("⚠️ Invalid request", content_type="text/plain", status=400)



# =========================================================
# ADMIN
# =========================================================
@staff_member_required
def admin_dashboard(request):
    online_cutoff = now() - timedelta(minutes=5)
    online_users = UserActivity.objects.filter(last_seen__gte=online_cutoff).count()
    return render(request, "admin_dashboard.html", {
        "total_users": User.objects.count(),
        "online_users": online_users,
        "total_income": Transaction.objects.filter(transaction_type="INCOME").aggregate(total=Sum("amount"))["total"] or 0,
        "total_expense": Transaction.objects.filter(transaction_type="EXPENSE").aggregate(total=Sum("amount"))["total"] or 0,
        "total_transactions": Transaction.objects.count(),
    })


@staff_member_required
def admin_users(request):
    users = User.objects.all().order_by("-date_joined")
    return render(request, "admin_users.html", {"users": users})


@staff_member_required
def ban_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user.is_superuser:
        user.is_active = False
        user.save()
    return redirect("admin_users")


@staff_member_required
def unban_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = True
    user.save()
    return redirect("admin_users")


@staff_member_required
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST" and not user.is_superuser:
        user.delete()
    return redirect("admin_users")


# =========================================================
# PWA OFFLINE PAGE
# =========================================================
def offline(request):
    return render(request, "offline.html")


# =========================================================
# Expense category chart (image)
# =========================================================
def expense_category_chart(request):
    today = date.today()

    month = int(request.GET.get("month", today.month))
    year = int(request.GET.get("year", today.year))
    download = request.GET.get("download") == "1"

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
    if download:
        response["Content-Disposition"] = 'attachment; filename="expense_chart.png"'

    plt.savefig(response, format="png")
    plt.close()

    return response


# =========================================================
# VOICE: TEXT-BASED (existing) - accepts JSON text and optionally preview
# =========================================================
# =========================================================
# VOICE: TEXT-BASED (existing) - accepts JSON text and optionally preview
# =========================================================
# voice/views.py
import os, time, json, tempfile
from datetime import date
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from transactions.models import Transaction
from .utils import parse_finance_text, normalize_amount

import logging
logger = logging.getLogger(__name__)

# =========================================================
# VOICE: TEXT-BASED (JSON input)
# =========================================================
@csrf_exempt
@login_required
def add_transaction_voice(request):

    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Invalid request method"},
            status=405,
        )

    # =====================================================
    # 1️⃣ PARSE JSON BODY
    # =====================================================

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse(
            {"status": "error", "message": "Invalid JSON"},
            status=400,
        )

    text = (data.get("text") or "").strip()
    preview = bool(data.get("preview", False))

    if not text:
        return JsonResponse(
            {"status": "error", "message": "No text provided"},
            status=400,
        )

    # =====================================================
    # 2️⃣ EXTRACT AMOUNT
    # =====================================================

    parsed = parse_finance_text(text) or {}
    amount_val = data.get("amount") or parsed.get("amount")

    if amount_val is None:
        return JsonResponse(
            {"status": "error", "message": "Amount not detected"},
            status=400,
        )

    try:
        amount = normalize_amount(amount_val)
    except Exception:
        return JsonResponse(
            {"status": "error", "message": "Invalid amount format"},
            status=400,
        )

    if amount <= 0:
        return JsonResponse(
            {"status": "error", "message": "Amount must be positive"},
            status=400,
        )

    # =====================================================
    # 3️⃣ AI CATEGORY PREDICTION (SINGLE SOURCE OF TRUTH)
    # =====================================================

    ai_result = predict_category(text)

    category = data.get("category") or ai_result["category"]
    transaction_type = data.get("transaction_type") or ai_result["transaction_type"]

    # =====================================================
    # 4️⃣ DATE HANDLING
    # =====================================================

    txn_date = data.get("date") or parsed.get("date")

    if txn_date:
        try:
            txn_date = date.fromisoformat(str(txn_date))
        except Exception:
            txn_date = date.today()
    else:
        txn_date = date.today()

    # =====================================================
    # 5️⃣ PREVIEW MODE
    # =====================================================

    if preview:
        return JsonResponse({
            "status": "preview",
            "amount": amount_val,
            "category": category,
            "transaction_type": transaction_type,
            "date": txn_date.isoformat(),
            "description": text,
        })

    # =====================================================
    # 6️⃣ SAVE TRANSACTION
    # =====================================================

    txn = Transaction.objects.create(
        user=request.user,
        amount=amount,
        category=category,
        transaction_type=transaction_type,
        date=txn_date,
        description=text,
    )

    return JsonResponse({
        "status": "success",
        "transaction": {
            "id": txn.id,
            "amount": float(txn.amount),
            "category": txn.category,
            "type": txn.transaction_type,
            "date": txn.date.isoformat(),
        }
    })
# =========================================================
# VOICE: AUDIO-BASED DIRECT SAVE
# =========================================================





VOICE_CHUNK_DIR = os.path.join(os.getcwd(), "voice_chunks")


# =========================================================
# GROQ TRANSCRIPTION HELPER
# =========================================================
def _transcribe_with_groq(file_obj, lang="ta"):
    """
    Send audio file to Groq transcription API.
    """
    url = os.getenv("GROQ_TRANSCRIBE_URL")
    model = os.getenv("GROQ_MODEL", "whisper-large-v3")
    api_key = os.getenv("GROQ_API_KEY")

    if not url or not api_key:
        raise RuntimeError("Groq API not configured")

    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (getattr(file_obj, "name", "audio.webm"), file_obj)}
    data = {"model": model, "language": lang}

    resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
    resp.raise_for_status()
    return resp.json()


# =========================================================
# VOICE: DIRECT UPLOAD
# =========================================================
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from datetime import date
import json, requests
from transactions.models import Transaction

from insights.ai_engine import predict_category  # <-- your ML/AI classifier

@csrf_exempt
@login_required
def add_transaction_voice_direct(request):

    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Invalid method"},
            status=405,
        )

    try:
        text = ""
        payload = {}
        content_type = request.content_type or ""

        # =====================================================
        # 1️⃣ INPUT HANDLING (JSON / AUDIO / FORM)
        # =====================================================

        if "application/json" in content_type:
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except Exception:
                return JsonResponse(
                    {"status": "error", "message": "Invalid JSON"},
                    status=400,
                )

            text = (payload.get("text") or "").strip()

        else:
            audio = request.FILES.get("audio")

            if audio:
                try:
                    groq_resp = _transcribe_with_groq(audio)
                    text = groq_resp.get("text") or groq_resp.get("transcript") or ""
                except Exception as e:
                    return JsonResponse(
                        {"status": "error", "message": "Transcription failed", "detail": str(e)},
                        status=502,
                    )
            else:
                text = (request.POST.get("text") or "").strip()

            payload = {
                "amount": request.POST.get("amount"),
                "category": request.POST.get("category"),
                "transaction_type": request.POST.get("transaction_type"),
                "date": request.POST.get("date"),
                "preview": request.POST.get("preview"),
            }

        if not text:
            return JsonResponse(
                {"status": "error", "message": "No audio or text provided"},
                status=400,
            )

        # =====================================================
        # 2️⃣ SAFE PREVIEW BOOLEAN
        # =====================================================

        preview_raw = payload.get("preview")
        preview = str(preview_raw).lower() in ["true", "1", "yes"]

        # =====================================================
        # 3️⃣ AMOUNT EXTRACTION
        # =====================================================

        parsed = parse_finance_text(text) or {}
        amount_val = payload.get("amount") or parsed.get("amount")

        if amount_val is None:
            return JsonResponse(
                {"status": "error", "message": "Amount not detected"},
                status=400,
            )

        try:
            amount = normalize_amount(amount_val)
        except Exception:
            return JsonResponse(
                {"status": "error", "message": "Invalid amount format"},
                status=400,
            )

        if amount <= 0:
            return JsonResponse(
                {"status": "error", "message": "Amount must be positive"},
                status=400,
            )

        # =====================================================
        # 4️⃣ AI CATEGORY (SINGLE SOURCE OF TRUTH)
        # =====================================================

        from insights.transaction_parser import parse_transaction_text

        ai_result = parse_transaction_text(text)

        amount = ai_result["amount"]
        category = ai_result["category"]
        transaction_type = ai_result["transaction_type"]
        txn_date = ai_result["date"]
        # =====================================================
        # 5️⃣ DATE HANDLING
        # =====================================================

        txn_date_raw = payload.get("date") or parsed.get("date")

        if txn_date_raw:
            try:
                txn_date = date.fromisoformat(str(txn_date_raw))
            except Exception:
                txn_date = date.today()
        else:
            txn_date = date.today()

        # =====================================================
        # 6️⃣ PREVIEW MODE
        # =====================================================

        if preview:
            return JsonResponse({
                "status": "preview",
                "amount": amount_val,
                "category": category,
                "transaction_type": transaction_type,
                "date": txn_date.isoformat(),
                "description": text,
            })

        # =====================================================
        # 7️⃣ SAVE MODE
        # =====================================================

        txn = Transaction.objects.create(
            user=request.user,
            amount=amount,
            category=category,
            transaction_type=transaction_type,
            date=txn_date,
            description=text,
        )

        return JsonResponse({
            "status": "success",
            "transaction": {
                "id": txn.id,
                "amount": float(txn.amount),
                "category": txn.category,
                "type": txn.transaction_type,
                "date": txn.date.isoformat(),
            },
            "predictions": {
                "category": category,
                "transaction_type": transaction_type,
            }
        })

    except Exception as e:
        logger.exception("VOICE DIRECT ERROR: %s", str(e))
        return JsonResponse(
            {"status": "error", "message": "Server error"},
            status=500,
        )#========================
# VOICE: CHUNKED UPLOADS
# =========================================================
@csrf_exempt
@login_required
def voice_chunk_upload(request):

    session_id = request.POST.get("session_id") or request.GET.get("session_id")

    if not session_id:
        return JsonResponse(
            {"status": "error", "message": "Missing session_id"},
            status=400,
        )

    # 🔐 Prevent path traversal
    session_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))

    os.makedirs(VOICE_CHUNK_DIR, exist_ok=True)
    session_dir = os.path.join(VOICE_CHUNK_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    # =====================================================
    # 1️⃣ SAVE CHUNK
    # =====================================================

    if "chunk" in request.FILES:

        chunk = request.FILES["chunk"]
        idx = request.POST.get("index")

        if idx is None:
            return JsonResponse(
                {"status": "error", "message": "Missing chunk index"},
                status=400,
            )

        try:
            filename = f"chunk-{int(idx)}.webm"
        except Exception:
            return JsonResponse(
                {"status": "error", "message": "Invalid chunk index"},
                status=400,
            )

        chunk_path = os.path.join(session_dir, filename)

        with open(chunk_path, "wb") as f:
            for c in chunk.chunks():
                f.write(c)

        return JsonResponse({"status": "ok", "message": "chunk received"})

    # =====================================================
    # 2️⃣ FINAL ASSEMBLY
    # =====================================================

    final_raw = request.POST.get("final") or request.GET.get("final")
    final_flag = str(final_raw).lower() in ["1", "true", "yes"]

    if final_flag:

        assembled_path = os.path.join(session_dir, "assembled.webm")

        try:
            parts = [
                p for p in os.listdir(session_dir)
                if p.startswith("chunk-") and p.endswith(".webm")
            ]

            if not parts:
                return JsonResponse(
                    {"status": "error", "message": "No chunks found"},
                    status=400,
                )

            # 🔢 Numeric sort (critical)
            parts.sort(key=lambda x: int(x.split("-")[1].split(".")[0]))

            # Assemble file
            with open(assembled_path, "wb") as out:
                for p in parts:
                    with open(os.path.join(session_dir, p), "rb") as inp:
                        out.write(inp.read())

            # =====================================================
            # 3️⃣ TRANSCRIBE
            # =====================================================

            try:
                with open(assembled_path, "rb") as f:
                    groq_resp = _transcribe_with_groq(f)
            except Exception as e:
                return JsonResponse(
                    {"status": "error", "message": "Transcription failed", "detail": str(e)},
                    status=502,
                )

            text = groq_resp.get("text") or groq_resp.get("transcript") or ""

            if not text:
                return JsonResponse(
                    {"status": "error", "message": "Empty transcript"},
                    status=502,
                )

            # =====================================================
            # 4️⃣ PARSE AMOUNT
            # =====================================================

            parsed = parse_finance_text(text) or {}
            amount_val = parsed.get("amount")

            if amount_val is None:
                return JsonResponse(
                    {"status": "error", "message": "Amount not detected"},
                    status=400,
                )

            try:
                amount = normalize_amount(amount_val)
            except Exception:
                return JsonResponse(
                    {"status": "error", "message": "Invalid amount format"},
                    status=400,
                )

            if amount <= 0:
                return JsonResponse(
                    {"status": "error", "message": "Amount must be positive"},
                    status=400,
                )

            # =====================================================
            # 5️⃣ AI CATEGORY (SINGLE SOURCE)
            # =====================================================

            ai_result = parse_transaction_text(text)

            amount = ai_result["amount"]
            predicted_category = ai_result["category"]
            predicted_type = ai_result["transaction_type"]
            txn_date = ai_result["date"]

            # =====================================================
            # 6️⃣ DATE HANDLING
            # =====================================================

            txn_date_raw = parsed.get("date")

            if txn_date_raw:
                try:
                    txn_date = date.fromisoformat(str(txn_date_raw))
                except Exception:
                    txn_date = date.today()
            else:
                txn_date = date.today()

            # =====================================================
            # 7️⃣ CREATE TRANSACTION
            # =====================================================

            txn = Transaction.objects.create(
                user=request.user,
                amount=amount,
                category=predicted_category,
                transaction_type=predicted_type,
                date=txn_date,
                description=text,
            )

            return JsonResponse({
                "status": "success",
                "transaction": {
                    "id": txn.id,
                    "amount": float(txn.amount),
                    "category": txn.category,
                    "type": txn.transaction_type,
                    "date": txn.date.isoformat(),
                },
                "predictions": {
                    "category": predicted_category,
                    "transaction_type": predicted_type,
                }
            })

        except Exception as e:
            logger.exception("VOICE CHUNK ERROR: %s", str(e))
            return JsonResponse(
                {"status": "error", "message": "Server error"},
                status=500,
            )

        finally:
            # =====================================================
            # 8️⃣ SAFE CLEANUP (ALWAYS EXECUTE)
            # =====================================================

            try:
                if os.path.exists(session_dir):
                    for f in os.listdir(session_dir):
                        try:
                            os.remove(os.path.join(session_dir, f))
                        except Exception:
                            pass
                    try:
                        os.rmdir(session_dir)
                    except Exception:
                        pass
            except Exception:
                pass

    return JsonResponse({"status": "ok"})

from insights.transaction_parser import parse_transaction_text
from django.views.decorators.http import require_POST # pyright: ignore[reportMissingModuleSource]

@require_POST
def predict_category_api(request):

    try:
        data = json.loads(request.body)
        text = data.get("text", "").strip()

        if not text:
            return JsonResponse({"error": "No text provided"}, status=400)

        result = parse_transaction_text(text)

        return JsonResponse({
            "amount": result["amount"],
            "category": result["category"],
            "transaction_type": result["transaction_type"],
            "date": result["date"].isoformat()
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)