from __future__ import annotations

from typing import Any, Dict


def global_settings(request) -> Dict[str, Any]:
    """
    Contexte global pour tous les templates.

    Fournit :
    - APP_NAME
    - ROLE_NAME (calculé avec la logique centrale role_name(user))
    - PERM_NAMES (permissions custom du rôle)
    - IS_DIRECTION_APPROVER (Directeur de direction ou Assistant de directeur)
    """

    user = getattr(request, "user", None)

    role_name_value = ""
    perm_names = set()

    if user is not None and getattr(user, "is_authenticated", False):
        try:
            from core.permissions import role_name
            role_name_value = role_name(user)
        except Exception:
            role = getattr(user, "role", None)
            role_name_value = getattr(role, "nom_role", "") if role else ""

        try:
            from utilisateurs.models import RolePermission

            role = getattr(user, "role", None)

            if role:
                perm_names = set(
                    RolePermission.objects
                    .filter(role=role)
                    .select_related("permission")
                    .values_list("permission__nom_permission", flat=True)
                )
        except Exception:
            perm_names = set()

    return {
        "APP_NAME": "SYSDAA",
        "ROLE_NAME": role_name_value,
        "PERM_NAMES": perm_names,
        "IS_DIRECTION_APPROVER": role_name_value in {
            "Directeur de direction",
            "Assistant de directeur",
        },
    }