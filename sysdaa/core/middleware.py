from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.utils.http import urlencode
from django.contrib import messages
from django.contrib.auth import logout
from core.permissions import otp_required_for_user


class RequireVerifiedUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def _build_redirect_url(self, viewname, request):
        url = reverse(viewname)
        next_url = request.get_full_path()

        if next_url and next_url != url:
            return f"{url}?{urlencode({'next': next_url})}"
        return url

    def __call__(self, request):
        path = request.path

        if path.startswith("/static/") or path.startswith("/media/"):
            return self.get_response(request)

        try:
            match = resolve(path)
            current_view = match.view_name or ""
        except Exception:
            current_view = ""

        allowed_views = {
            "custom_login",
            "logout",
            "two_factor:login",
            "two_factor:setup",
            "two_factor:qr",
            "two_factor:setup_complete",
            "two_factor:backup_tokens",
            "two_factor:profile",
            "two_factor:disable",
        }

        if current_view in allowed_views:
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return self.get_response(request)

        statut = getattr(user, "statut", "")
        if statut == "Inactif" or not getattr(user, "is_active", False):
            logout(request)
            messages.error(request, "Connexion impossible : ce compte est inactif.")
            return redirect(self._build_redirect_url("custom_login", request))

        # Utilisateur connecté, mais rôle sans OTP imposé -> on laisse passer
        if not otp_required_for_user(user):
            return self.get_response(request)
        

        # OTP imposé -> on exige seulement ici la vérification complète
        if hasattr(user, "is_verified") and user.is_verified():
            return self.get_response(request)

        return redirect(self._build_redirect_url("custom_login", request))