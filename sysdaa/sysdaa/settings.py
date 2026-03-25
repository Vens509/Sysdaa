from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Charger le fichier .env
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "CHANGE_ME_IN_PROD")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    u.strip()
    for u in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if u.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_email",

    "two_factor",
    "two_factor.plugins.email",

    "utilisateurs",
    "core",
    "mouvements_stock",
    "articles",
    "requisitions",
    "notifications",
    "rapports",
    "audit",
    "configurations",
    "fournisseurs",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'core.middleware.RequireVerifiedUserMiddleware',
    'configurations.middleware.AutoAnneeFiscaleMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = "sysdaa.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "sysdaa" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.global_settings",
                "notifications.context_processors.notif_unread_count",
            ],
        },
    },
]

WSGI_APPLICATION = "sysdaa.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "sysdaa"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.environ.get("POSTGRES_CONN_MAX_AGE", "60")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = "America/Port-au-Prince"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "utilisateurs.Utilisateur"

SITE_ID = int(os.environ.get("DJANGO_SITE_ID", "1"))

# Auth
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "/login/"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 60 * 60 * 8  # Deconnexion apres 8 heures

# -------------------------------------------------------------------
# SMTP / Email
# -------------------------------------------------------------------
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)

EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("DJANGO_EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.environ.get("DJANGO_EMAIL_USE_SSL", "0") == "1"

EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")

DEFAULT_FROM_EMAIL = os.environ.get(
    "DJANGO_DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "no-reply@sysdaa.local",
)
SERVER_EMAIL = os.environ.get("DJANGO_SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# -------------------------------------------------------------------
# OTP Email
# -------------------------------------------------------------------
OTP_EMAIL_SENDER = DEFAULT_FROM_EMAIL
OTP_EMAIL_SUBJECT = os.environ.get(
    "OTP_EMAIL_SUBJECT",
    "Code de vérification SYSDAA",
)
OTP_EMAIL_TOKEN_VALIDITY = int(os.environ.get("OTP_EMAIL_TOKEN_VALIDITY", "300"))
OTP_EMAIL_COOLDOWN_DURATION = int(os.environ.get("OTP_EMAIL_COOLDOWN_DURATION", "60"))
OTP_EMAIL_THROTTLE_FACTOR = int(os.environ.get("OTP_EMAIL_THROTTLE_FACTOR", "1"))

OTP_EMAIL_BODY_TEMPLATE = (
    "Bonjour,\n\n"
    "Votre code de vérification SYSDAA est : {{ token }}\n\n"
    "Ce code expire dans quelques minutes.\n"
    "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n"
)

# -------------------------------------------------------------------
# Two-factor
# -------------------------------------------------------------------
TWO_FACTOR_PATCH_ADMIN = False
TWO_FACTOR_LOGIN_TIMEOUT = int(os.environ.get("TWO_FACTOR_LOGIN_TIMEOUT", "600"))
TWO_FACTOR_REMEMBER_COOKIE_AGE = int(
    os.environ.get("TWO_FACTOR_REMEMBER_COOKIE_AGE", str(60 * 60 * 24 * 30))
)
TWO_FACTOR_REMEMBER_COOKIE_SECURE = not DEBUG
TWO_FACTOR_REMEMBER_COOKIE_HTTPONLY = True
TWO_FACTOR_REMEMBER_COOKIE_SAMESITE = "Lax"

# Email seulement
TWO_FACTOR_SMS_GATEWAY = None
TWO_FACTOR_CALL_GATEWAY = None

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "DEBUG" if DEBUG else "INFO",
        }
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "two_factor": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django_otp": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
from django.contrib.messages import constants as messages

MESSAGE_TAGS = {
    messages.ERROR: "danger",
}
