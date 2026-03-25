from __future__ import annotations

from functools import wraps
from typing import Callable, Iterable, Set, TypeVar

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse

T = TypeVar("T", bound=Callable[..., HttpResponse])

# =========================
# NOMS DE RÔLES (exact / tolérants)
# =========================
ROLE_SECRETAIRE = "Secrétaire"
ROLE_DIRECTEUR_DIRECTION = "Directeur de direction"
ROLE_ASSISTANT_DIRECTEUR = "Assistant de directeur"
ROLE_GESTIONNAIRE = "Gestionnaire des ressources matérielles"
ROLE_DIRECTEUR_DAA = "Directeur DAA"

ROLE_ADMIN = "Admin"
ROLE_ADMIN_SYSTEME = "Administrateur système"
ROLE_SUPER_ADMIN = "Super admin"

# Alias toléré pour cohérence avec certains jeux de données / create_superuser
ROLE_SUPER_ADMIN_ALT = "Super Admin"

ROLES_UTILISATEURS: Set[str] = {
    ROLE_ADMIN,
    ROLE_ADMIN_SYSTEME,
    ROLE_SUPER_ADMIN,
    ROLE_SUPER_ADMIN_ALT,
}

ROLES_DIRECTION: Set[str] = {
    ROLE_DIRECTEUR_DIRECTION,
    ROLE_ASSISTANT_DIRECTEUR,
}

# Rôles pour lesquels on force la double authentification OTP
ROLES_OTP_OBLIGATOIRE: Set[str] = {
    ROLE_GESTIONNAIRE,
    ROLE_SECRETAIRE,
    ROLE_ADMIN_SYSTEME,
    ROLE_SUPER_ADMIN,
    ROLE_SUPER_ADMIN_ALT,
}


def is_authenticated(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False))


def role_name(user) -> str:
    """
    Retourne le nom de rôle:
    - superuser Django -> Super admin
    - staff Django -> Administrateur système
    - sinon via user.role.nom_role
    """
    if not user:
        return ""

    if getattr(user, "is_superuser", False):
        return ROLE_SUPER_ADMIN

    if getattr(user, "is_staff", False):
        return ROLE_ADMIN_SYSTEME

    role = getattr(user, "role", None)
    value = getattr(role, "nom_role", "") if role else ""
    return (value or "").strip()


def is_direction_role_name(value: str) -> bool:
    return (value or "").strip() in ROLES_DIRECTION


def is_direction_user(user) -> bool:
    return is_direction_role_name(role_name(user))


def has_role(user, allowed_roles: Iterable[str]) -> bool:
    if not is_authenticated(user):
        return False
    allowed = {(r or "").strip() for r in allowed_roles if (r or "").strip()}
    if not allowed:
        return False
    return role_name(user) in allowed


def otp_required_for_user(user) -> bool:
    """
    Retourne True si ce profil doit obligatoirement passer par l'OTP.
    """
    if not is_authenticated(user):
        return False
    return role_name(user) in ROLES_OTP_OBLIGATOIRE


def role_required(*allowed_roles: str, message: str = "Accès refusé : rôle non autorisé."):
    """
    Décorateur standard:
    - si user non connecté -> PermissionDenied (403)
    - si rôle non autorisé -> PermissionDenied (403)
    """
    allowed: Set[str] = {(r or "").strip() for r in allowed_roles if (r or "").strip()}

    if not allowed:
        def deco(view_func: T) -> T:
            @wraps(view_func)
            def _wrapped(request: HttpRequest, *args, **kwargs):
                raise PermissionDenied(message)
            return _wrapped  # type: ignore[return-value]
        return deco

    def deco(view_func: T) -> T:
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs):
            user = getattr(request, "user", None)
            if not is_authenticated(user):
                raise PermissionDenied(message)
            if role_name(user) not in allowed:
                raise PermissionDenied(message)
            return view_func(request, *args, **kwargs)

        return _wrapped  # type: ignore[return-value]

    return deco


def role_required_denied(*allowed_roles: str, message: str = "Accès refusé : rôle non autorisé."):
    return role_required(*allowed_roles, message=message)


# =========================
# Décorateurs "métier" réutilisables
# =========================

def articles_required(view_func: T) -> T:
    return role_required(
        ROLE_DIRECTEUR_DAA,
        ROLE_GESTIONNAIRE,
        message="Accès refusé : réservé au Directeur DAA et au Gestionnaire des ressources matérielles.",
    )(view_func)


def mouvements_required(view_func: T) -> T:
    return role_required(
        ROLE_DIRECTEUR_DAA,
        ROLE_GESTIONNAIRE,
        message="Accès refusé : réservé au Directeur DAA et au Gestionnaire des ressources matérielles.",
    )(view_func)


def rapports_required(view_func: T) -> T:
    return role_required(
        ROLE_DIRECTEUR_DAA,
        ROLE_GESTIONNAIRE,
        message="Accès refusé : réservé au Directeur DAA et au Gestionnaire des ressources matérielles.",
    )(view_func)


def fournisseurs_required(view_func: T) -> T:
    return role_required(
        ROLE_DIRECTEUR_DAA,
        ROLE_GESTIONNAIRE,
        message="Accès refusé : réservé au Directeur DAA et au Gestionnaire des ressources matérielles.",
    )(view_func)


def utilisateurs_required(view_func: T) -> T:
    return role_required(
        ROLE_ADMIN,
        ROLE_ADMIN_SYSTEME,
        ROLE_SUPER_ADMIN,
        ROLE_SUPER_ADMIN_ALT,
        message="Accès refusé : réservé aux administrateurs.",
    )(view_func)