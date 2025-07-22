import os
from pathlib import Path
from typing import Final

import environ

# Initialize environment
env = environ.Env(DJANGO_DEBUG=(bool, False))

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Security
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ads",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ad_budget_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "ad_budget_system.wsgi.application"

# Database
DATABASES = {"default": env.db("DATABASE_URL")}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE: Final = "en-us"
TIME_ZONE: Final = "UTC"
USE_I18N: Final = True
USE_TZ: Final = True

# Static files
STATIC_URL: Final = "static/"

DEFAULT_AUTO_FIELD: Final = "django.db.models.BigAutoField"

# Celery
CELERY_BROKER_URL = env.str("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

from celery.schedules import crontab, schedule

# Budget Management Configuration
DEFAULT_SPEND_CHECK_INTERVAL_MINUTES: int = int(
    os.environ.get("DEFAULT_SPEND_CHECK_INTERVAL_MINUTES", "15")
)
DEFAULT_BUDGET_CHECK_FREQUENCY: Final[int] = int(
    os.environ.get("DEFAULT_BUDGET_CHECK_FREQUENCY", "15")
)

# Celery Beat Schedule: Periodic Task Definitions
DAILY_RESET_CRON = env.str("DAILY_RESET_CRON", default="0 2 * * *")  # type: ignore
MONTHLY_RESET_CRON = env.str("MONTHLY_RESET_CRON", default="30 1 1 * *")  # type: ignore


def parse_cron_expr(expr: str):
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"Invalid cron expression: {expr}")
    return dict(
        minute=fields[0],
        hour=fields[1],
        day_of_month=fields[2],
        month_of_year=fields[3],
        day_of_week=fields[4],
    )


CELERY_BEAT_SCHEDULE: Final = {
    "reset_daily_spend_task": {
        "task": "ads.tasks.reset_daily_spend_task",
        "schedule": crontab(**parse_cron_expr(str(DAILY_RESET_CRON))),
    },
    "reset_monthly_spend_task": {
        "task": "ads.tasks.reset_monthly_spend_task",
        "schedule": crontab(**parse_cron_expr(str(MONTHLY_RESET_CRON))),
    },
    "check_spend_and_pause_task": {
        "task": "ads.tasks.check_spend_and_pause_task",
        "schedule": schedule(run_every=DEFAULT_SPEND_CHECK_INTERVAL_MINUTES * 60),
    },
}

# Logging configuration for observability
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "ads": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# Optional: Production security settings (uncomment for production)
# SECURE_HSTS_SECONDS = 3600
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
