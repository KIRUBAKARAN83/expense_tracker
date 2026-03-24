import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# ----------------------------------------------
# BASE
# ----------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ----------------------------------------------
# SECURITY
# ----------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-local-dev-key")
DEBUG = os.getenv("DEBUG", "False") == "True"
ALLOWED_HOSTS = [os.getenv("RENDER_EXTERNAL_HOSTNAME", "*")]

# ----------------------------------------------
# APPLICATIONS
# ----------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "transactions",
    "insights",
]

# ----------------------------------------------
# MIDDLEWARE
# ----------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # required for Render static files
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "accounts.middleware.ActiveUserMiddleware",
]

# ----------------------------------------------
# URLS / TEMPLATES
# ----------------------------------------------
ROOT_URLCONF = "ai_finance_tracker.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ai_finance_tracker.wsgi.application"

# ----------------------------------------------
# DATABASE
# ----------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
    )
}

# ----------------------------------------------
# INTERNATIONALIZATION
# ----------------------------------------------
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ----------------------------------------------
# STATIC FILES
# ----------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ----------------------------------------------
# AUTH
# ----------------------------------------------
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ----------------------------------------------
# DEFAULT PK
# ----------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
