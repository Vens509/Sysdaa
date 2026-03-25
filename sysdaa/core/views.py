from __future__ import annotations

import json

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List

from django.apps import apps
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django_otp.plugins.otp_email.models import EmailDevice
from core.permissions import otp_required_for_user
from utilisateurs.services import (
    synchroniser_email_otp_utilisateur,
    EMAIL_DEVICE_NAME,
)
from audit.models import AuditLog
from audit.services import audit_log as enregistrer_audit

from core.permissions import (
    ROLE_ADMIN,
    ROLE_ADMIN_SYSTEME,
    ROLE_DIRECTEUR_DAA,
    ROLE_DIRECTEUR_DIRECTION,
    ROLE_GESTIONNAIRE,
    ROLE_SECRETAIRE,
    ROLE_SUPER_ADMIN,
    ROLE_ASSISTANT_DIRECTEUR,
    role_name,
    role_required,
)
from .forms import CustomPasswordChangeForm
from .forms import ActiveStatusAuthenticationForm, CustomPasswordChangeForm

try:
    from configurations.services import assurer_annee_fiscale_active_auto
except Exception:
    assurer_annee_fiscale_active_auto = None

from two_factor.views import LoginView


@dataclass(frozen=True)
class StockKPI:
    stock_initial_total: int
    stock_minimal_total: int
    stock_actuel_total: int
    alertes_orange: int
    alertes_rouge: int


def _safe_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _next_month_first_day(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _calculer_kpis_stock() -> StockKPI:
    """
    KPI global stock (articles).
    Robuste : si l'app/model n'existe pas, retourne 0.
    """
    try:
        Article = apps.get_model("articles", "Article")
    except LookupError:
        return StockKPI(0, 0, 0, 0, 0)

    qs = Article.objects.all()
    agg = qs.aggregate(
        s_init=Sum("stock_initial"),
        s_min=Sum("stock_minimal"),
        s_act=Sum("stock_actuel"),
    )

    stock_initial_total = _safe_int(agg.get("s_init"))
    stock_minimal_total = _safe_int(agg.get("s_min"))
    stock_actuel_total = _safe_int(agg.get("s_act"))

    alertes_orange = qs.filter(
        stock_actuel__gt=0,
        stock_actuel__lte=F("stock_minimal"),
    ).count()

    alertes_rouge = qs.filter(stock_actuel=0).count()

    return StockKPI(
        stock_initial_total=stock_initial_total,
        stock_minimal_total=stock_minimal_total,
        stock_actuel_total=stock_actuel_total,
        alertes_orange=alertes_orange,
        alertes_rouge=alertes_rouge,
    )


def _requisitions_qs_pour_dashboard(user):
    """
    Applique la règle métier demandée :
    - Gestionnaire : ne voit jamais les réquisitions "En attente".
    - Directeur DAA : ne voit que les réquisitions transférées à lui.
    """
    try:
        Requisition = apps.get_model("requisitions", "Requisition")
    except LookupError:
        return None, None

    rn = role_name(user)

    etat_en_attente = getattr(Requisition, "ETAT_EN_ATTENTE", "En attente")
    etat_validee = getattr(Requisition, "ETAT_VALIDEE", "Validé")
    etat_en_attente_modif = getattr(Requisition, "ETAT_EN_ATTENTE_MODIF", "En attente de modification")
    etat_traitee = getattr(Requisition, "ETAT_TRAITEE", "Traité")
    etat_rejetee = getattr(Requisition, "ETAT_REJETEE", "Rejeté")

    qs = Requisition.objects.all()

    if rn == ROLE_GESTIONNAIRE:
        qs = qs.filter(
            etat_requisition__in=[
                etat_validee,
                etat_en_attente_modif,
                etat_traitee,
                etat_rejetee,
            ]
        )
    elif rn == ROLE_DIRECTEUR_DAA:
        qs = qs.filter(transferee_vers_directeur_daa=True, directeur_daa=user)
    else:
        qs = qs.exclude(etat_requisition=etat_en_attente) if rn == ROLE_GESTIONNAIRE else qs

    return Requisition, qs


def _annee_fiscale_active():
    """
    Retourne (annee_debut, annee_fin, label) de l'année fiscale active.
    Fallback robuste si le service/config n'est pas disponible.
    """
    if assurer_annee_fiscale_active_auto is not None:
        try:
            cfg = assurer_annee_fiscale_active_auto()
            if cfg and getattr(cfg, "annee_debut", None) and getattr(cfg, "annee_fin", None):
                debut = int(cfg.annee_debut)
                fin = int(cfg.annee_fin)
                return debut, fin, f"{debut}-{fin}"
        except Exception:
            pass

    today = timezone.localdate()
    if today.month >= 10:
        debut = today.year
        fin = today.year + 1
    else:
        debut = today.year - 1
        fin = today.year
    return debut, fin, f"{debut}-{fin}"


@login_required(login_url="two_factor:login")
def home(request):
    """
    Point d'entrée après login (LOGIN_REDIRECT_URL = core:home).
    Redirige vers le dashboard selon rôle.
    """
    if not hasattr(request.user, "role") or not request.user.role:
        return HttpResponseForbidden("Aucun rôle associé à cet utilisateur.")

    rn = role_name(request.user)

    if rn in {ROLE_DIRECTEUR_DAA, ROLE_GESTIONNAIRE}:
        try:
            enregistrer_audit(
                action=AuditLog.Action.CONSULTATION,
                user=request.user,
                request=request,
                app_label="core",
                message="Accès au point d'entrée avec redirection vers le dashboard principal.",
                meta={"role": rn, "destination": "core:dashboard"},
                identifiant_saisi=getattr(request.user, "email", "") or "",
            )
        except Exception:
            pass
        return redirect("core:dashboard")

    if rn == ROLE_SECRETAIRE:
        try:
            enregistrer_audit(
                action=AuditLog.Action.CONSULTATION,
                user=request.user,
                request=request,
                app_label="core",
                message="Accès au point d'entrée avec redirection vers le dashboard secrétaire.",
                meta={"role": rn, "destination": "core:dashboard_secretaire"},
                identifiant_saisi=getattr(request.user, "email", "") or "",
            )
        except Exception:
            pass
        return redirect("core:dashboard_secretaire")

    if rn in {ROLE_DIRECTEUR_DIRECTION, ROLE_ASSISTANT_DIRECTEUR}:
        try:
            enregistrer_audit(
                action=AuditLog.Action.CONSULTATION,
                user=request.user,
                request=request,
                app_label="core",
                message="Accès au point d'entrée avec redirection vers la file des réquisitions à confirmer.",
                meta={"role": rn, "destination": "core:a_confirmer"},
                identifiant_saisi=getattr(request.user, "email", "") or "",
            )
        except Exception:
            pass
        return redirect("core:a_confirmer")

    if rn in {ROLE_ADMIN, ROLE_ADMIN_SYSTEME, ROLE_SUPER_ADMIN}:
        try:
            enregistrer_audit(
                action=AuditLog.Action.CONSULTATION,
                user=request.user,
                request=request,
                app_label="core",
                message="Accès au point d'entrée avec redirection vers le dashboard administrateur.",
                meta={"role": rn, "destination": "core:dashboard_admin"},
                identifiant_saisi=getattr(request.user, "email", "") or "",
            )
        except Exception:
            pass
        return redirect("core:dashboard_admin")

    return HttpResponseForbidden("Accès refusé : rôle non reconnu.")


@role_required(
    ROLE_DIRECTEUR_DAA,
    ROLE_GESTIONNAIRE,
    message="Accès refusé : dashboard réservé au Directeur DAA et au Gestionnaire des ressources matérielles.",
)
@login_required(login_url="two_factor:login")
def dashboard(request):
    """
    Dashboard décisionnel stock (DAA + Gestionnaire).
    Réquisitions filtrées selon rôle.
    """

    try:
        Article = apps.get_model("articles", "Article")
    except LookupError:
        Article = None

    try:
        MouvementStock = apps.get_model("mouvements_stock", "MouvementStock")
    except LookupError:
        MouvementStock = None

    try:
        LigneRequisition = apps.get_model("requisitions", "LigneRequisition")
    except LookupError:
        LigneRequisition = None

    Requisition, req_qs = _requisitions_qs_pour_dashboard(request.user)

    today = timezone.localdate()
    start_30 = today - timedelta(days=29)
    start_6m = (today.replace(day=1) - timedelta(days=31 * 5)).replace(day=1)

    kpis_stock = _calculer_kpis_stock()
    total_articles = Article.objects.count() if Article else 0

    requisitions_total = 0
    requisitions_by_state: Dict[str, int] = {}

    if Requisition is not None and req_qs is not None:
        requisitions_total = req_qs.count()
        for row in req_qs.values("etat_requisition").annotate(n=Count("id")).order_by("etat_requisition"):
            requisitions_by_state[str(row["etat_requisition"])] = _safe_int(row["n"])

    mv_30_entrees = 0
    mv_30_sorties = 0
    if MouvementStock is not None:
        mv_30 = MouvementStock.objects.filter(date_mouvement__date__gte=start_30)
        mv_30_entrees = _safe_int(
            mv_30.filter(type_mouvement="ENTREE").aggregate(n=Count("id")).get("n")
        )
        mv_30_sorties = _safe_int(
            mv_30.filter(type_mouvement="SORTIE").aggregate(n=Count("id")).get("n")
        )

    daily_labels: List[str] = [(start_30 + timedelta(days=i)).isoformat() for i in range(30)]
    daily_entrees_map = {label: 0 for label in daily_labels}
    daily_sorties_map = {label: 0 for label in daily_labels}

    if MouvementStock is not None:
        qs_daily = (
            MouvementStock.objects.filter(date_mouvement__date__gte=start_30)
            .annotate(day=TruncDate("date_mouvement"))
            .values("day", "type_mouvement")
            .annotate(n=Count("id"))
            .order_by("day")
        )

        for row in qs_daily:
            day = row.get("day")
            if not day:
                continue

            label = day.isoformat()
            if label not in daily_entrees_map:
                continue

            n = _safe_int(row.get("n"))
            if row.get("type_mouvement") == "ENTREE":
                daily_entrees_map[label] = n
            elif row.get("type_mouvement") == "SORTIE":
                daily_sorties_map[label] = n

    daily_series = [
        {"label": label, "entrees": daily_entrees_map[label], "sorties": daily_sorties_map[label]}
        for label in daily_labels
    ]

    month_cursor = start_6m
    month_labels: List[str] = []
    month_entrees_map: Dict[str, int] = {}
    month_sorties_map: Dict[str, int] = {}

    while month_cursor <= today.replace(day=1):
        label = month_cursor.strftime("%Y-%m")
        month_labels.append(label)
        month_entrees_map[label] = 0
        month_sorties_map[label] = 0
        month_cursor = _next_month_first_day(month_cursor)

    if MouvementStock is not None and month_labels:
        qs_monthly = (
            MouvementStock.objects.filter(date_mouvement__date__gte=start_6m)
            .annotate(m=TruncMonth("date_mouvement"))
            .values("m", "type_mouvement")
            .annotate(n=Count("id"))
            .order_by("m")
        )

        for row in qs_monthly:
            mois = row.get("m")
            if not mois:
                continue

            label = mois.strftime("%Y-%m")
            if label not in month_entrees_map:
                continue

            n = _safe_int(row.get("n"))
            if row.get("type_mouvement") == "ENTREE":
                month_entrees_map[label] = n
            elif row.get("type_mouvement") == "SORTIE":
                month_sorties_map[label] = n

    monthly_series = [
        {"label": label, "entrees": month_entrees_map[label], "sorties": month_sorties_map[label]}
        for label in month_labels
    ]

    top_articles: List[Dict[str, Any]] = []
    if LigneRequisition is not None and Requisition is not None and req_qs is not None:
        req_ids_subquery = req_qs.values("id")
        qs_top = (
            LigneRequisition.objects.filter(
                requisition_id__in=req_ids_subquery,
                requisition__date_preparation__date__gte=start_30,
            )
            .values("article__nom", "article__unite")
            .annotate(qte=Sum("quantite_demandee"))
            .order_by("-qte", "article__nom")[:5]
        )

        top_articles = [
            {"nom": row["article__nom"], "unite": row["article__unite"], "qte": _safe_int(row["qte"])}
            for row in qs_top
        ]

    stock_donut = {"ok": 0, "orange": 0, "rouge": 0}
    if Article is not None:
        qs_articles = Article.objects.all()
        stock_donut["rouge"] = qs_articles.filter(stock_actuel=0).count()
        stock_donut["orange"] = qs_articles.filter(
            stock_actuel__gt=0,
            stock_actuel__lte=F("stock_minimal"),
        ).count()
        stock_donut["ok"] = qs_articles.filter(stock_actuel__gt=F("stock_minimal")).count()

    req_pie = {"labels": [], "data": []}
    for etat, total in requisitions_by_state.items():
        req_pie["labels"].append(etat)
        req_pie["data"].append(_safe_int(total))

    context: Dict[str, Any] = {
        "kpis": kpis_stock,
        "today": today,
        "role_name": role_name(request.user),
        "total_articles": total_articles,
        "requisitions_total": requisitions_total,
        "requisitions_by_state": requisitions_by_state,
        "mv_30_entrees": mv_30_entrees,
        "mv_30_sorties": mv_30_sorties,
        "daily_series": daily_series,
        "monthly_series": monthly_series,
        "stock_donut": stock_donut,
        "req_pie": req_pie,
        "top_articles": top_articles,
    }

    try:
        enregistrer_audit(
            action=AuditLog.Action.CONSULTATION,
            user=request.user,
            request=request,
            app_label="core",
            message="Consultation du dashboard principal.",
            meta={
                "role": role_name(request.user),
                "total_articles": total_articles,
                "requisitions_total": requisitions_total,
                "mv_30_entrees": mv_30_entrees,
                "mv_30_sorties": mv_30_sorties,
                "alertes_orange": kpis_stock.alertes_orange,
                "alertes_rouge": kpis_stock.alertes_rouge,
            },
            identifiant_saisi=getattr(request.user, "email", "") or "",
        )
    except Exception:
        pass

    return render(request, "core/dashboard.html", context)


@role_required(ROLE_SECRETAIRE, message="Accès refusé : réservé au rôle Secrétaire.")
@login_required(login_url="two_factor:login")
def dashboard_secretaire(request):
    """
    Dashboard Secrétaire : activité de ses réquisitions sur l'année fiscale active.
    """
    try:
        Requisition = apps.get_model("requisitions", "Requisition")
    except LookupError:
        debut, fin, label = _annee_fiscale_active()
        return render(
            request,
            "core/dashboard_secretaire.html",
            {
                "annee_fiscale_debut": debut,
                "annee_fiscale_fin": fin,
                "annee_fiscale_label": label,
                "kpi_total": 0,
                "kpi_traite": 0,
                "kpi_attente": 0,
                "kpi_rejete": 0,
                "monthly_labels": [],
                "monthly_values": [],
            },
        )

    annee_fiscale_debut, annee_fiscale_fin, annee_fiscale_label = _annee_fiscale_active()
    start = date(annee_fiscale_debut, 10, 1)
    end = date(annee_fiscale_fin, 9, 30)

    qs = Requisition.objects.filter(
        soumetteur=request.user,
        date_preparation__date__gte=start,
        date_preparation__date__lte=end,
    )

    etat_traitee = getattr(Requisition, "ETAT_TRAITEE", "TRAITEE")
    etat_rejetee = getattr(Requisition, "ETAT_REJETEE", "REJETEE")

    total = qs.count()
    traite = qs.filter(etat_requisition=etat_traitee).count()
    rejete = qs.filter(etat_requisition=etat_rejetee).count()
    attente = qs.exclude(etat_requisition__in=[etat_traitee, etat_rejetee]).count()

    fiscal_months = [
        date(annee_fiscale_debut, 10, 1),
        date(annee_fiscale_debut, 11, 1),
        date(annee_fiscale_debut, 12, 1),
        date(annee_fiscale_fin, 1, 1),
        date(annee_fiscale_fin, 2, 1),
        date(annee_fiscale_fin, 3, 1),
        date(annee_fiscale_fin, 4, 1),
        date(annee_fiscale_fin, 5, 1),
        date(annee_fiscale_fin, 6, 1),
        date(annee_fiscale_fin, 7, 1),
        date(annee_fiscale_fin, 8, 1),
        date(annee_fiscale_fin, 9, 1),
    ]

    monthly_labels = [m.strftime("%Y-%m") for m in fiscal_months]
    monthly_map = {label: 0 for label in monthly_labels}

    monthly = (
        qs.annotate(m=TruncMonth("date_preparation"))
        .values("m")
        .annotate(n=Count("id"))
        .order_by("m")
    )

    for row in monthly:
        m = row.get("m")
        if not m:
            continue
        key = m.strftime("%Y-%m")
        if key in monthly_map:
            monthly_map[key] = _safe_int(row.get("n"))

    values = [monthly_map[label] for label in monthly_labels]

    try:
        enregistrer_audit(
            action=AuditLog.Action.CONSULTATION,
            user=request.user,
            request=request,
            app_label="core",
            message="Consultation du dashboard secrétaire.",
            meta={
                "annee_fiscale": annee_fiscale_label,
                "kpi_total": total,
                "kpi_traite": traite,
                "kpi_attente": attente,
                "kpi_rejete": rejete,
            },
            identifiant_saisi=getattr(request.user, "email", "") or "",
        )
    except Exception:
        pass

    return render(
        request,
        "core/dashboard_secretaire.html",
        {
            "annee_fiscale_debut": annee_fiscale_debut,
            "annee_fiscale_fin": annee_fiscale_fin,
            "annee_fiscale_label": annee_fiscale_label,
            "kpi_total": total,
            "kpi_traite": traite,
            "kpi_attente": attente,
            "kpi_rejete": rejete,
            "monthly_labels": monthly_labels,
            "monthly_values": values,
        },
    )


@role_required(
    ROLE_DIRECTEUR_DIRECTION,
    ROLE_ASSISTANT_DIRECTEUR,
    message="Accès refusé : réservé au Directeur de direction et à son assistant.",
)
@login_required(login_url="two_factor:login")
def a_confirmer(request):
    """
    Réquisitions à confirmer pour la direction du directeur connecté.
    """
    try:
        Requisition = apps.get_model("requisitions", "Requisition")
    except LookupError:
        return render(request, "core/dashboard_direction.html", {"requisitions": []})

    etat_en_attente = getattr(Requisition, "ETAT_EN_ATTENTE", "En attente")
    direction = getattr(request.user, "direction_affectee", None)

    if not direction:
        return render(request, "core/dashboard_direction.html", {"requisitions": []})

    qs = (
        Requisition.objects.select_related("soumetteur", "directeur_direction")
        .filter(
            etat_requisition=etat_en_attente,
            soumetteur__direction_affectee=direction,
        )
        .order_by("-date_preparation", "-id")[:25]
    )

    try:
        enregistrer_audit(
            action=AuditLog.Action.CONSULTATION,
            user=request.user,
            request=request,
            app_label="core",
            message="Consultation des réquisitions à confirmer par le directeur de direction.",
            meta={
                "direction": str(direction),
                "nombre_requisitions": qs.count(),
            },
            identifiant_saisi=getattr(request.user, "email", "") or "",
        )
    except Exception:
        pass

    return render(request, "core/dashboard_direction.html", {"requisitions": qs})


@role_required(
    ROLE_ADMIN,
    ROLE_ADMIN_SYSTEME,
    ROLE_SUPER_ADMIN,
    message="Accès refusé : réservé aux administrateurs.",
)
@login_required(login_url="two_factor:login")
def dashboard_admin(request):
    """
    Dashboard Admin/Super admin :
    limité aux informations utilisateurs et audit.
    """
    Utilisateur = apps.get_model("utilisateurs", "Utilisateur")
    Role = apps.get_model("utilisateurs", "Role")

    try:
        AuditLogModel = apps.get_model("audit", "AuditLog")
    except LookupError:
        AuditLogModel = None

    today = timezone.localdate()
    start_30 = today - timedelta(days=29)

    kpi_total_users = Utilisateur.objects.count()
    kpi_actifs = Utilisateur.objects.filter(is_active=True).count()
    kpi_inactifs = Utilisateur.objects.filter(is_active=False).count()
    kpi_jamais_connecte = Utilisateur.objects.filter(last_login__isnull=True).count()
    kpi_roles = Role.objects.count()

    admin_daily_labels = [(start_30 + timedelta(days=i)).isoformat() for i in range(30)]
    admin_daily_values = [0] * 30

    qs_users = (
        Utilisateur.objects.filter(date_creation__date__gte=start_30)
        .annotate(day=TruncDate("date_creation"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    )

    idx = {d: i for i, d in enumerate(admin_daily_labels)}
    for row in qs_users:
        day = row.get("day")
        if not day:
            continue
        k = day.isoformat()
        i = idx.get(k)
        if i is not None:
            admin_daily_values[i] = _safe_int(row.get("n"))

    admin_daily_labels_json = json.dumps(admin_daily_labels)
    admin_daily_values_json = json.dumps(admin_daily_values)

    users_by_role = []
    qs_roles = (
        Utilisateur.objects.values("role__nom_role")
        .annotate(n=Count("id"))
        .order_by("-n", "role__nom_role")
    )
    for row in qs_roles:
        users_by_role.append(
            {
                "role": row["role__nom_role"] or "Non défini",
                "total": _safe_int(row["n"]),
            }
        )

    audit_logs = []
    audit_actions_pie = {"labels": [], "values": []}
    audit_levels_donut = {"labels": [], "values": []}
    kpi_audit_30_total = 0
    kpi_audit_30_erreurs = 0

    if AuditLogModel is not None:
        audit_logs = (
            AuditLogModel.objects.select_related("acteur")
            .only(
                "id",
                "date_action",
                "niveau",
                "app",
                "action",
                "acteur__email",
                "message",
                "succes",
                "ip",
            )
            .order_by("-date_action")[:50]
        )

        qs_30 = AuditLogModel.objects.filter(date_action__date__gte=start_30)
        kpi_audit_30_total = qs_30.count()
        kpi_audit_30_erreurs = qs_30.filter(
            models.Q(succes=False) | models.Q(niveau="ERROR")
        ).count()

        top_actions = list(
            qs_30.values("action")
            .annotate(n=Count("id"))
            .order_by("-n", "action")[:6]
        )
        used = 0
        for row in top_actions:
            audit_actions_pie["labels"].append(str(row["action"]))
            audit_actions_pie["values"].append(_safe_int(row["n"]))
            used += _safe_int(row["n"])

        autres = kpi_audit_30_total - used
        if autres > 0:
            audit_actions_pie["labels"].append("Autres")
            audit_actions_pie["values"].append(autres)

        for row in qs_30.values("niveau").annotate(n=Count("id")).order_by("niveau"):
            audit_levels_donut["labels"].append(str(row["niveau"]))
            audit_levels_donut["values"].append(_safe_int(row["n"]))

    context: Dict[str, Any] = {
        "today": today,
        "kpi_total_users": kpi_total_users,
        "kpi_actifs": kpi_actifs,
        "kpi_inactifs": kpi_inactifs,
        "kpi_jamais_connecte": kpi_jamais_connecte,
        "kpi_roles": kpi_roles,
        "admin_daily_labels_json": admin_daily_labels_json,
        "admin_daily_values_json": admin_daily_values_json,
        "users_by_role": users_by_role,
        "kpi_audit_30_total": kpi_audit_30_total,
        "kpi_audit_30_erreurs": kpi_audit_30_erreurs,
        "audit_actions_pie": audit_actions_pie,
        "audit_levels_donut": audit_levels_donut,
        "audit_logs": audit_logs,
    }

    try:
        enregistrer_audit(
            action=AuditLog.Action.CONSULTATION,
            user=request.user,
            request=request,
            app_label="core",
            message="Consultation du dashboard administrateur.",
            meta={
                "kpi_total_users": kpi_total_users,
                "kpi_actifs": kpi_actifs,
                "kpi_inactifs": kpi_inactifs,
                "kpi_jamais_connecte": kpi_jamais_connecte,
                "kpi_roles": kpi_roles,
                "kpi_audit_30_total": kpi_audit_30_total,
                "kpi_audit_30_erreurs": kpi_audit_30_erreurs,
            },
            identifiant_saisi=getattr(request.user, "email", "") or "",
        )
    except Exception:
        pass

    return render(request, "core/dashboard_admin.html", context)


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "core/password_change.html"
    form_class = CustomPasswordChangeForm
    success_url = reverse_lazy("core:password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        try:
            enregistrer_audit(
                action=AuditLog.Action.MODIFICATION,
                user=self.request.user,
                request=self.request,
                app_label="core",
                message="Changement du mot de passe par l'utilisateur connecté.",
                meta={
                    "user_id": getattr(self.request.user, "pk", None),
                    "email": getattr(self.request.user, "email", "") or "",
                },
                identifiant_saisi=getattr(self.request.user, "email", "") or "",
            )
        except Exception:
            pass
        return response


class CustomLoginView(LoginView):
    template_name = "two_factor/core/login.html"
    authentication_form = ActiveStatusAuthenticationForm

    condition_dict = {
        LoginView.TOKEN_STEP: lambda wizard: wizard.has_token_step(),
        LoginView.BACKUP_STEP: lambda wizard: wizard.has_backup_step(),
    }

    def _get_email_device(self, user):
        if not user or not getattr(user, "pk", None):
            return None

        synchroniser_email_otp_utilisateur(user)

        return (
            EmailDevice.objects
            .filter(user=user, name=EMAIL_DEVICE_NAME, confirmed=True)
            .order_by("id")
            .first()
        )

    def has_token_step(self):
        user = self.get_user()
        if not user:
            return False

        if not otp_required_for_user(user):
            return False

        if getattr(self, "remember_agent", False):
            return False

        device = self._get_email_device(user)
        return device is not None

    def has_backup_step(self):
        return False

    def get_device(self, step=None):
        user = self.get_user()
        if not user:
            return None

        if otp_required_for_user(user):
            return self._get_email_device(user)

        return super().get_device(step=step)

    def render(self, form=None, **kwargs):
        current_step = getattr(self.steps, "current", None)

        response = super().render(form, **kwargs)

        if current_step == self.TOKEN_STEP:
            sent_key = "otp_email_sent_for_login"
            if not self.request.session.get(sent_key, False):
                self.request.session[sent_key] = True
                messages.success(
                    self.request,
                    "Un code OTP a été envoyé à votre adresse email.",
                )

        return response

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form, **kwargs)
        context["redirect_field_name"] = self.redirect_field_name
        context["redirect_field_value"] = self.get_redirect_url()
        return context

    def post(self, *args, **kwargs):
        if "resend_token" in self.request.POST:
            user = self.get_user()
            current_step = getattr(self.steps, "current", None)

            if current_step == self.TOKEN_STEP and user and otp_required_for_user(user):
                device = self._get_email_device(user)
                if device:
                    try:
                        device.generate_challenge()
                        self.request.session["otp_email_sent_for_login"] = True
                        messages.success(
                            self.request,
                            "Un nouveau code OTP a été envoyé à votre adresse email.",
                        )
                    except Exception:
                        messages.error(
                            self.request,
                            "Impossible de renvoyer le code OTP par email.",
                        )
                else:
                    messages.error(
                        self.request,
                        "Aucun dispositif OTP email n'a été trouvé pour ce compte.",
                    )
                return self.render(self.get_form())

            messages.warning(
                self.request,
                "Vous devez d'abord valider votre email et votre mot de passe.",
            )
            return self.render(self.get_form())

        self.request.session.pop("otp_email_sent_for_login", None)
        return super().post(*args, **kwargs)


class PasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "core/password_change_done.html"


password_change = PasswordChangeView.as_view()
password_change_done = PasswordChangeDoneView.as_view()