from core.permissions import (
    ROLE_GESTIONNAIRE,
    role_name,
    mouvements_required,
)

def is_gestionnaire(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False) and role_name(user) == ROLE_GESTIONNAIRE)

# Alias attendu possible dans du code existant :
gestionnaire_required = mouvements_required