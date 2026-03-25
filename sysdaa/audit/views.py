from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from core.permissions import (
    ROLE_ADMIN,
    ROLE_ADMIN_SYSTEME,
    ROLE_SUPER_ADMIN,
    role_required,
)

from .models import AuditLog


@login_required(login_url="two_factor:login")
@role_required(
    ROLE_ADMIN,
    ROLE_ADMIN_SYSTEME,
    ROLE_SUPER_ADMIN,
    message="Accès refusé : réservé aux administrateurs.",
)
def liste(request):
    q = (request.GET.get("q") or "").strip()
    app_value = (request.GET.get("app") or "").strip()
    action_value = (request.GET.get("action") or "").strip()
    niveau_value = (request.GET.get("niveau") or "").strip()
    succes_value = (request.GET.get("succes") or "").strip()

    qs = AuditLog.objects.select_related("acteur").all().order_by("-date_action", "-id")

    if q:
        qs = qs.filter(
            Q(message__icontains=q)
            | Q(app__icontains=q)
            | Q(action__icontains=q)
            | Q(cible_type__icontains=q)
            | Q(cible_id__icontains=q)
            | Q(cible_label__icontains=q)
            | Q(identifiant_saisi__icontains=q)
            | Q(niveau__icontains=q)
            | Q(acteur__nom__icontains=q)
            | Q(acteur__prenom__icontains=q)
            | Q(acteur__email__icontains=q)
            | Q(ip__icontains=q)
        )

    if app_value:
        qs = qs.filter(app=app_value)

    if action_value:
        qs = qs.filter(action=action_value)

    if niveau_value:
        qs = qs.filter(niveau=niveau_value)

    if succes_value == "1":
        qs = qs.filter(succes=True)
    elif succes_value == "0":
        qs = qs.filter(succes=False)

    apps_disponibles = (
        AuditLog.objects.exclude(app__isnull=True)
        .exclude(app__exact="")
        .values_list("app", flat=True)
        .distinct()
        .order_by("app")
    )

    actions_disponibles = (
        AuditLog.objects.exclude(action__isnull=True)
        .exclude(action__exact="")
        .values_list("action", flat=True)
        .distinct()
        .order_by("action")
    )

    niveaux_disponibles = (
        AuditLog.objects.exclude(niveau__isnull=True)
        .exclude(niveau__exact="")
        .values_list("niveau", flat=True)
        .distinct()
        .order_by("niveau")
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "audits": page_obj.object_list,
        "q": q,
        "app_value": app_value,
        "action_value": action_value,
        "niveau_value": niveau_value,
        "succes_value": succes_value,
        "apps_disponibles": list(apps_disponibles),
        "actions_disponibles": list(actions_disponibles),
        "niveaux_disponibles": list(niveaux_disponibles),
    }
    return render(request, "audit/liste.html", context)


@login_required(login_url="two_factor:login")
@role_required(
    ROLE_ADMIN,
    ROLE_ADMIN_SYSTEME,
    ROLE_SUPER_ADMIN,
    message="Accès refusé : réservé aux administrateurs.",
)
def detail(request, pk: int):
    audit = get_object_or_404(
        AuditLog.objects.select_related("acteur"),
        pk=pk,
    )

    details_json = audit.details if audit.details is not None else {}

    identifiant_affiche = audit.identifiant_saisi
    if not identifiant_affiche and audit.acteur and audit.acteur.email:
        identifiant_affiche = audit.acteur.email

    return render(
        request,
        "audit/detail.html",
        {
            "a": audit,
            "details_json": details_json,
            "identifiant_affiche": identifiant_affiche,
        },
    )