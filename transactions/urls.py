from django.urls import path
from .views import (
    dashboard,
    add_transaction,
    edit_transaction,
    delete_transaction,
    all_transactions,
    chart_data,
    expense_category_chart,
    add_transaction_voice,         # text-based JSON voice endpoint (preview/save)
    add_transaction_voice_direct,  # audio-based direct save (Groq transcription)
    create_budget,
    budgets_list,
    delete_budget,
    chat_api,
    chat_stream,
    admin_dashboard,
    admin_users,
    ban_user,
    predict_category_api,
    unban_user,
    delete_user,
    offline,
    voice_chunk_upload,
)
from .pdf import monthly_pdf

urlpatterns = [
    # ================= USER =================
    path("", dashboard, name="dashboard"),
    path("add/", add_transaction, name="add_transaction"),
    path("edit/<int:pk>/", edit_transaction, name="edit_transaction"),
    path("delete/<int:pk>/", delete_transaction, name="delete_transaction"),
    path("list/", all_transactions, name="all_transactions"),  # /transactions/list/

    # ================= BUDGETS =================
    path("budgets/", budgets_list, name="budgets_list"),
    path("budgets/add/", create_budget, name="create_budget"),
    path("budgets/delete/<int:budget_id>/", delete_budget, name="delete_budget"),

    # ================= PDF =================
    path("pdf/", monthly_pdf, name="monthly_pdf"),

    # ================= API =================
    path("api/chart-data/", chart_data, name="chart_data"),
    path("api/chat/", chat_api, name="chat_api"),
    path("chat/", chat_api, name="chat_api"),  # legacy alias
    path("chat/stream/", chat_stream, name="chat_stream"),

    # ================= ADMIN =================
    path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
    path("admin-users/", admin_users, name="admin_users"),
    path("admin-users/ban/<int:user_id>/", ban_user, name="ban_user"),
    path("admin-users/unban/<int:user_id>/", unban_user, name="unban_user"),
    path("admin-users/delete/<int:user_id>/", delete_user, name="delete_user"),

    # ================= PWA =================
    path("offline/", offline, name="offline"),

    # ================= CHARTS =================
    path("charts/expense-category/", expense_category_chart, name="expense_category_chart"),
    path("expense-category-chart/", expense_category_chart, name="expense_category_chart"),  # alias

    # ================= VOICE =================
    # Text-based endpoint (expects JSON { "text": "...", "preview": true|false })
    path("voice-text/", add_transaction_voice, name="add_transaction_voice_text"),

    # Audio-based direct save (records uploaded audio -> Groq transcription -> save)
    path("add-transaction-voice/", add_transaction_voice_direct, name="add_transaction_voice"),
    path("voice-chunk/", voice_chunk_upload, name="voice_chunk"),
    


    path("voice/chunk-upload/", voice_chunk_upload, name="voice_chunk_upload"),
    path("predict-category/", predict_category_api, name="predict_category_api")
    # other paths...



]
