from __future__ import annotations

from django.contrib import messages
from django.shortcuts import render

from audit.models import AuditLog
from audit.services import audit_log as enregistrer_audit

from .forms import RapportGenerationForm
from .permissions import rapports_required
from .services import (
    ReportFilters,
    exporter_rapport_excel,
    exporter_rapport_pdf,
    generer_rapport,
)


def _build_filters_from_form(form: RapportGenerationForm) -> ReportFilters:
    return ReportFilters(
        report_type=form.cleaned_data["type_rapport"],
        period_type=form.cleaned_data["periode"],
        configuration=form.cleaned_data["annee_fiscale"],
        mois=form.cleaned_data.get("mois"),
        categorie=form.cleaned_data.get("categorie"),
        direction=form.cleaned_data.get("direction"),
        etat_requisition=form.cleaned_data.get("etat_requisition") or "",
    )


def _audit_meta_from_filters(filters: ReportFilters) -> dict:
    return {
        "type_rapport": filters.report_type,
        "periode": filters.period_type,
        "annee_fiscale": getattr(filters.configuration, "code", None),
        "annee_fiscale_id": getattr(filters.configuration, "pk", None),
        "mois": filters.mois,
        "categorie": getattr(filters.categorie, "libelle", None),
        "categorie_id": getattr(filters.categorie, "pk", None),
        "direction": getattr(filters.direction, "nom", None),
        "direction_id": getattr(filters.direction, "pk", None),
        "etat_requisition": filters.etat_requisition or None,
    }


def _audit_meta_from_report(rapport) -> dict:
    return {
        "report_type": getattr(rapport, "report_type", None),
        "report_label": getattr(rapport, "report_label", None),
        "period_type": getattr(rapport, "period_type", None),
        "period_label": getattr(rapport, "period_label", None),
        "annee_fiscale_label": getattr(rapport, "annee_fiscale_label", None),
        "mois": getattr(rapport, "mois", None),
        "mois_label": getattr(rapport, "mois_label", None),
        "annee_reelle": getattr(rapport, "annee_reelle", None),
        "nb_lignes": len(getattr(rapport, "rows", []) or []),
        "colonnes": list(getattr(rapport, "columns", []) or []),
        "titre": getattr(rapport, "title", None),
        "sous_titre": getattr(rapport, "subtitle", None),
        "filtres_textes": list(getattr(rapport, "filters_text", []) or []),
        "mode_logique": getattr(getattr(rapport, "extra_context", {}), "get", lambda *_: None)("mode_logique"),
    }


def _render_generer(request, *, form: RapportGenerationForm, rapport=None):
    return render(
        request,
        "rapports/generer.html",
        {
            "form": form,
            "rapport": rapport,
        },
    )


@rapports_required
def generer(request):
    rapport = None

    if request.method == "POST":
        form = RapportGenerationForm(request.POST)

        if form.is_valid():
            filters = _build_filters_from_form(form)

            try:
                rapport = generer_rapport(filters)

                enregistrer_audit(
                    action=AuditLog.Action.GENERATION_RAPPORT,
                    user=request.user,
                    request=request,
                    app_label="rapports",
                    cible_type="Rapport",
                    cible_id=f"{rapport.report_type}-{rapport.annee_fiscale_label}-{rapport.period_type.lower()}-{rapport.mois or 'annuel'}",
                    cible_label=rapport.title,
                    message="Génération d'un rapport analytique.",
                    meta={
                        **_audit_meta_from_filters(filters),
                        **_audit_meta_from_report(rapport),
                        "format": "ecran",
                    },
                )

            except Exception as e:
                enregistrer_audit(
                    action=AuditLog.Action.GENERATION_RAPPORT,
                    user=request.user,
                    request=request,
                    app_label="rapports",
                    niveau=AuditLog.Niveau.ERROR,
                    succes=False,
                    cible_type="Rapport",
                    cible_label="Rapport analytique",
                    message="Échec de génération d'un rapport analytique.",
                    meta={
                        **_audit_meta_from_filters(filters),
                        "format": "ecran",
                        "erreur": str(e),
                    },
                )
                messages.error(request, str(e))
        else:
            enregistrer_audit(
                action=AuditLog.Action.GENERATION_RAPPORT,
                user=request.user,
                request=request,
                app_label="rapports",
                niveau=AuditLog.Niveau.WARNING,
                succes=False,
                cible_type="Rapport",
                cible_label="Rapport analytique",
                message="Échec de génération d'un rapport : formulaire invalide.",
                meta={
                    "format": "ecran",
                    "donnees_saisies": {
                        k: request.POST.get(k)
                        for k in request.POST.keys()
                        if k != "csrfmiddlewaretoken"
                    },
                    "erreurs": form.errors.get_json_data(),
                },
            )
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = RapportGenerationForm()

    return _render_generer(request, form=form, rapport=rapport)


@rapports_required
def export_excel(request):
    form = RapportGenerationForm(request.GET)

    if not form.is_valid():
        enregistrer_audit(
            action=AuditLog.Action.GENERATION_RAPPORT,
            user=request.user,
            request=request,
            app_label="rapports",
            niveau=AuditLog.Niveau.WARNING,
            succes=False,
            cible_type="Rapport",
            cible_label="Export Excel rapport analytique",
            message="Échec d'export Excel d'un rapport analytique : paramètres invalides.",
            meta={
                "format": "excel",
                "parametres_saisis": {k: request.GET.get(k) for k in request.GET.keys()},
                "erreurs": form.errors.get_json_data(),
            },
        )
        messages.error(request, "Veuillez choisir des paramètres valides.")
        return _render_generer(request, form=form, rapport=None)

    filters = _build_filters_from_form(form)

    try:
        rapport = generer_rapport(filters)

        enregistrer_audit(
            action=AuditLog.Action.GENERATION_RAPPORT,
            user=request.user,
            request=request,
            app_label="rapports",
            cible_type="Rapport",
            cible_id=f"{rapport.report_type}-excel-{rapport.annee_fiscale_label}-{rapport.period_type.lower()}-{rapport.mois or 'annuel'}",
            cible_label=rapport.title,
            message="Export Excel d'un rapport analytique.",
            meta={
                **_audit_meta_from_filters(filters),
                **_audit_meta_from_report(rapport),
                "format": "excel",
            },
        )

        return exporter_rapport_excel(data=rapport)

    except Exception as e:
        enregistrer_audit(
            action=AuditLog.Action.GENERATION_RAPPORT,
            user=request.user,
            request=request,
            app_label="rapports",
            niveau=AuditLog.Niveau.ERROR,
            succes=False,
            cible_type="Rapport",
            cible_label="Export Excel rapport analytique",
            message="Échec d'export Excel d'un rapport analytique.",
            meta={
                **_audit_meta_from_filters(filters),
                "format": "excel",
                "erreur": str(e),
            },
        )
        messages.error(request, str(e))
        return _render_generer(request, form=form, rapport=None)


@rapports_required
def export_pdf(request):
    form = RapportGenerationForm(request.GET)

    if not form.is_valid():
        enregistrer_audit(
            action=AuditLog.Action.GENERATION_RAPPORT,
            user=request.user,
            request=request,
            app_label="rapports",
            niveau=AuditLog.Niveau.WARNING,
            succes=False,
            cible_type="Rapport",
            cible_label="Export PDF rapport analytique",
            message="Échec d'export PDF d'un rapport analytique : paramètres invalides.",
            meta={
                "format": "pdf",
                "parametres_saisis": {k: request.GET.get(k) for k in request.GET.keys()},
                "erreurs": form.errors.get_json_data(),
            },
        )
        messages.error(request, "Veuillez choisir des paramètres valides.")
        return _render_generer(request, form=form, rapport=None)

    filters = _build_filters_from_form(form)

    try:
        rapport = generer_rapport(filters)

        enregistrer_audit(
            action=AuditLog.Action.GENERATION_RAPPORT,
            user=request.user,
            request=request,
            app_label="rapports",
            cible_type="Rapport",
            cible_id=f"{rapport.report_type}-pdf-{rapport.annee_fiscale_label}-{rapport.period_type.lower()}-{rapport.mois or 'annuel'}",
            cible_label=rapport.title,
            message="Export PDF d'un rapport analytique.",
            meta={
                **_audit_meta_from_filters(filters),
                **_audit_meta_from_report(rapport),
                "format": "pdf",
            },
        )

        return exporter_rapport_pdf(data=rapport)

    except Exception as e:
        enregistrer_audit(
            action=AuditLog.Action.GENERATION_RAPPORT,
            user=request.user,
            request=request,
            app_label="rapports",
            niveau=AuditLog.Niveau.ERROR,
            succes=False,
            cible_type="Rapport",
            cible_label="Export PDF rapport analytique",
            message="Échec d'export PDF d'un rapport analytique.",
            meta={
                **_audit_meta_from_filters(filters),
                "format": "pdf",
                "erreur": str(e),
            },
        )
        messages.error(request, str(e))
        return _render_generer(request, form=form, rapport=None)