from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.permissions import (
    ROLE_ADMIN,
    ROLE_ADMIN_SYSTEME,
    ROLE_SUPER_ADMIN,
    role_required,
)

from .services import (
    assurer_annee_fiscale_active_auto,
    get_annee_fiscale_active_auto,
    lister_configurations,
)


@login_required
@role_required(
    ROLE_ADMIN,
    ROLE_ADMIN_SYSTEME,
    ROLE_SUPER_ADMIN,
    message="Accès refusé : réservé aux administrateurs.",
)
def tableau(request):
    cfg_active = assurer_annee_fiscale_active_auto(configurateur=request.user)
    annee_fiscale = get_annee_fiscale_active_auto()

    return render(
        request,
        "configurations/tableau.html",
        {
            "cfg_active": cfg_active,
            "annee_fiscale": annee_fiscale,
            "configurations": lister_configurations(),
        },
    )