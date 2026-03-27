from pathlib import Path
import os
import socket

from dotenv import load_dotenv
from django.contrib.messages import constants as messages

BASE_DIR = Path(__file__).resolve().parent.parent
print("==========SYsdaa setting charge==================")

# Charger le fichier .env
load_dotenv(BASE_DIR / ".env")


def env_str(name, default=""):
    return os.environ.get(name, default).strip()


def env_int(name, default=0):
    value = os.environ.get(name, str(default))
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# -------------------------------------------------------------------
# Réseau / timeout
# -------------------------------------------------------------------
SOCKET_DEFAULT_TIMEOUT = env_int("DJANGO_SOCKET_TIMEOUT", 10)
if SOCKET_DEFAULT_TIMEOUT > 0:
    socket.setdefaulttimeout(SOCKET_DEFAULT_TIMEOUT)

# -------------------------------------------------------------------
# Base
# -------------------------------------------------------------------
SECRET_KEY = env_str("DJANGO_SECRET_KEY", "CHANGE_ME_IN_PROD")
DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = [
    h.strip()
    for h in env_str("DJANGO_ALLOWED_HOSTS", "").split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    u.strip()
    for u in env_str("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if u.strip()
]

if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["10.3.26.105", "localhost"]

# -------------------------------------------------------------------
# Applications
# -------------------------------------------------------------------
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

# -------------------------------------------------------------------
# Middleware
# -------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "core.middleware.RequireVerifiedUserMiddleware",
    "configurations.middleware.AutoAnneeFiscaleMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "sysdaa.urls"

# -------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------
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

# -------------------------------------------------------------------
# Base de données
# -------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("POSTGRES_DB", "sysdaa"),
        "USER": env_str("POSTGRES_USER", "postgres"),
        "PASSWORD": env_str("POSTGRES_PASSWORD", ""),
        "HOST": env_str("POSTGRES_HOST", "127.0.0.1"),
        "PORT": env_str("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
    }
}

# -------------------------------------------------------------------
# Validation mots de passe
# -------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -------------------------------------------------------------------
# Internationalisation
# -------------------------------------------------------------------
LANGUAGE_CODE = "fr"
TIME_ZONE = "America/Port-au-Prince"
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------------------
# Fichiers statiques et médias
# -------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -------------------------------------------------------------------
# Modèle utilisateur
# -------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "utilisateurs.Utilisateur"

# -------------------------------------------------------------------
# Sites framework
# -------------------------------------------------------------------
SITE_ID = env_int("DJANGO_SITE_ID", 1)

# -------------------------------------------------------------------
# Authentification
# -------------------------------------------------------------------
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "/login/"

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = env_int("DJANGO_SESSION_COOKIE_AGE", 60 * 60 * 5)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"

# -------------------------------------------------------------------
# SMTP / Email
# -------------------------------------------------------------------
EMAIL_BACKEND = env_str(
    "DJANGO_EMAIL_BACKEND",
    "core.email_backend.EmailBackend",
)
EMAIL_HOST = env_str("DJANGO_EMAIL_HOST", "smtp.budget.gouv.ht")
EMAIL_PORT = env_int("DJANGO_EMAIL_PORT", 25)
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("DJANGO_EMAIL_USE_SSL", False)
EMAIL_HOST_USER = env_str("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env_str("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = env_int("DJANGO_EMAIL_TIMEOUT", SOCKET_DEFAULT_TIMEOUT)

DEFAULT_FROM_EMAIL = env_str(
    "DJANGO_DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER or "no-reply@sysdaa.local",
)
SERVER_EMAIL = env_str("DJANGO_SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# -------------------------------------------------------------------
# OTP Email
# -------------------------------------------------------------------
OTP_EMAIL_SENDER = DEFAULT_FROM_EMAIL
OTP_EMAIL_SUBJECT = env_str(
    "OTP_EMAIL_SUBJECT",
    "Code de vérification SYSDAA",
)
OTP_EMAIL_TOKEN_VALIDITY = env_int("OTP_EMAIL_TOKEN_VALIDITY", 300)
OTP_EMAIL_COOLDOWN_DURATION = env_int("OTP_EMAIL_COOLDOWN_DURATION", 60)
OTP_EMAIL_THROTTLE_FACTOR = env_int("OTP_EMAIL_THROTTLE_FACTOR", 1)

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
TWO_FACTOR_LOGIN_TIMEOUT = env_int("TWO_FACTOR_LOGIN_TIMEOUT", 600)
TWO_FACTOR_REMEMBER_COOKIE_AGE = env_int(
    "TWO_FACTOR_REMEMBER_COOKIE_AGE",
    60 * 60 * 24 * 30,
)
TWO_FACTOR_REMEMBER_COOKIE_SECURE = not DEBUG
TWO_FACTOR_REMEMBER_COOKIE_HTTPONLY = True
TWO_FACTOR_REMEMBER_COOKIE_SAMESITE = "Lax"

TWO_FACTOR_SMS_GATEWAY = None
TWO_FACTOR_CALL_GATEWAY = None

# -------------------------------------------------------------------
# Sécurité production
# -------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)

USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", False)
if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

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
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "sysdaa.log",
            "formatter": "standard",
            "level": "INFO",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "two_factor": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django_otp": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# -------------------------------------------------------------------
# Messages
# -------------------------------------------------------------------
MESSAGE_TAGS = {
    messages.ERROR: "danger",
}