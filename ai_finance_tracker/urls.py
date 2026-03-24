from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Accounts (login, logout, signup, etc.)
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("accounts.urls")),

    # Transactions app routes (single include)
    path("", include("transactions.urls")),              # dashboard at root
    path("transactions/", include("transactions.urls")), # app routes under /transactions/

    # If you want a top-level shortcut for voice add, define it in transactions/urls.py
    # and keep project urls.py free of direct view imports to avoid circular imports.
]
