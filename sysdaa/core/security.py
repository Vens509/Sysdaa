from __future__ import annotations

from functools import wraps
from typing import Callable

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django_otp.decorators import otp_required

from utilisateurs.models import RolePermission


def _login_url() -> str:
    return reverse("custom_login")


def require_perms(*perm_names: str):
    """
    Protège une vue par :
    - authentification (via two_factor)
    - OTP vérifié
    - permission(s) custom liées au rôle (RolePermission)
    """
    def deco(view_func: Callable):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect(f"{_login_url()}?next={request.get_full_path()}")

            # OTP obligatoire: si pas configuré => l’utilisateur sera poussé vers le setup 2FA
            # (comportement voulu : pages sensibles)
            otp_check = otp_required(view_func)  # applique la règle OTP
            # On ne l’exécute pas ici directement, on vérifie d’abord les perms pour message clair.

            role = getattr(user, "role", None)
            if not role:
                messages.error(request, "Accès refusé : rôle utilisateur non défini.")
                return redirect("core:home")

            user_perms = set(
                RolePermission.objects.filter(role=role)
                .select_related("permission")
                .values_list("permission__nom_permission", flat=True)
            )

            if perm_names and not any(p in user_perms for p in perm_names):
                messages.error(request, "Accès refusé : permission insuffisante.")
                return redirect("core:home")

            # OTP requis (après permission OK)
            return otp_check(request, *args, **kwargs)

        return _wrapped
    return deco