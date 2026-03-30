from __future__ import annotations

import os
from io import BytesIO

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from audit.models import AuditLog
from audit.services import audit_log as enregistrer_audit

from core.permissions import (
    role_required,
    role_name,
    ROLE_SECRETAIRE,
    ROLE_DIRECTEUR_DIRECTION,
    ROLE_GESTIONNAIRE,
    ROLE_DIRECTEUR_DAA,
)

from .forms import (
    RequisitionCreateForm,
    RequisitionUpdateForm,
    LigneRequisitionCreateFormSet,
    LigneRequisitionUpdateFormSet,
)

from .models import Requisition
from .services import (
    accuser_reception,
    creer_requisition,
    valider_par_directeur_direction,
    demander_modification,
    secretaire_apres_modification,
    transferer_vers_directeur_daa,
    valider_par_directeur_daa,
    rejeter_par_directeur_daa,
    traiter_requisition,
)

User = get_user_model()


def _abs(request, url_name: str, **kwargs) -> str:
    return request.build_absolute_uri(reverse(url_name, kwargs=kwargs))


def _forbidden():
    return HttpResponseForbidden("Accès refusé : rôle non autorisé.")


def _norm_text(value) -> str:
    return str(value or "").strip().lower()


def _get_user_direction_value(user):
    return getattr(user, "direction_affectee", None)


def _same_direction(user, req: Requisition) -> bool:
    user_direction = _get_user_direction_value(user)
    soumetteur = getattr(req, "soumetteur", None)
    req_direction = getattr(soumetteur, "direction_affectee", None) if soumetteur else None

    if user_direction is None or req_direction is None:
        return False

    user_direction_id = getattr(user_direction, "id", None)
    req_direction_id = getattr(req_direction, "id", None)

    if user_direction_id is not None and req_direction_id is not None:
        return user_direction_id == req_direction_id

    return _norm_text(user_direction) == _norm_text(req_direction)


def _qs_a_confirmer_pour_directeur(user):
    qs = (
        Requisition.objects.select_related(
            "soumetteur",
            "soumetteur__direction_affectee",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        )
        .prefetch_related("lignes__article")
        .filter(etat_requisition=Requisition.ETAT_EN_ATTENTE)
        .order_by("-date_preparation", "-id")
    )

    user_direction = _get_user_direction_value(user)
    if user_direction is None:
        return Requisition.objects.none()

    user_direction_id = getattr(user_direction, "id", None)
    if user_direction_id is not None:
        return qs.filter(soumetteur__direction_affectee_id=user_direction_id)

    return qs.filter(soumetteur__direction_affectee=user_direction)


def _can_view_requisition(user, req: Requisition) -> bool:
    if not user or not user.is_authenticated:
        return False

    rn = role_name(user)

    if rn == ROLE_SECRETAIRE:
        return req.soumetteur_id == user.id

    if rn == ROLE_DIRECTEUR_DIRECTION:
        return _same_direction(user, req)

    if rn == ROLE_GESTIONNAIRE:
        return req.etat_requisition in (
            Requisition.ETAT_VALIDEE,
            Requisition.ETAT_EN_ATTENTE_MODIF,
            Requisition.ETAT_TRAITEE,
            Requisition.ETAT_REJETEE,
        )

    if rn == ROLE_DIRECTEUR_DAA:
        return req.transferee_vers_directeur_daa and req.directeur_daa_id == user.id

    return False


def _can_modify_requisition(user, req: Requisition) -> bool:
    if not user or not user.is_authenticated:
        return False

    rn = role_name(user)

    if rn == ROLE_SECRETAIRE:
        return req.soumetteur_id == user.id and req.est_modifiable_par_secretaire()

    if rn == ROLE_DIRECTEUR_DIRECTION:
        return _same_direction(user, req) and req.etat_requisition == Requisition.ETAT_EN_ATTENTE

    return False


@role_required(ROLE_SECRETAIRE)
def creer(request):
    if request.method == "POST":
        form = RequisitionCreateForm(request.POST)
        formset = LigneRequisitionCreateFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    req = form.save(commit=False)
                    req.soumetteur = request.user
                    req.full_clean()
                    req.save()

                    formset.instance = req
                    formset.save()

                    lien_detail = request.build_absolute_uri(
                        reverse("requisitions:detail", kwargs={"pk": req.pk})
                    )

                    req = creer_requisition(requisition=req, lien_detail=lien_detail)

                    enregistrer_audit(
                        action=AuditLog.Action.CREATION,
                        user=request.user,
                        request=request,
                        app_label="requisitions",
                        cible=req,
                        message="Création d'une réquisition.",
                        meta={"etat": req.etat_requisition},
                    )

            except ValueError as e:
                messages.error(request, str(e))
                return render(
                    request,
                    "requisitions/creer.html",
                    {"form": form, "formset": formset},
                )

            messages.success(request, "Réquisition créée.")
            return redirect("requisitions:detail", pk=req.pk)

        messages.error(request, "Veuillez corriger les erreurs.")
        return render(request, "requisitions/creer.html", {"form": form, "formset": formset})

    form = RequisitionCreateForm()
    formset = LigneRequisitionCreateFormSet()
    return render(request, "requisitions/creer.html", {"form": form, "formset": formset})


@role_required(ROLE_SECRETAIRE, ROLE_GESTIONNAIRE, ROLE_DIRECTEUR_DAA)
def liste(request):
    q = (request.GET.get("q") or "").strip()
    etat = (request.GET.get("etat") or "").strip()

    qs = Requisition.objects.select_related(
        "soumetteur",
        "soumetteur__direction_affectee",
        "directeur_direction",
        "directeur_daa",
        "traitee_par",
        "recue_par",
    ).prefetch_related("lignes__article")

    rn = role_name(request.user)

    if rn == ROLE_SECRETAIRE:
        qs = qs.filter(soumetteur=request.user)

    elif rn == ROLE_GESTIONNAIRE:
        qs = qs.filter(etat_requisition=Requisition.ETAT_VALIDEE)

    elif rn == ROLE_DIRECTEUR_DAA:
        qs = qs.filter(directeur_daa=request.user, transferee_vers_directeur_daa=True)

    if q:
        qs = qs.filter(
            Q(motif_global__icontains=q)
            | Q(soumetteur__email__icontains=q)
            | Q(soumetteur__direction_affectee__nom__icontains=q)
        )

    if etat:
        qs = qs.filter(etat_requisition=etat)

    return render(
        request,
        "requisitions/liste.html",
        {
            "requisitions": qs.order_by("-date_preparation", "-id"),
            "q": q,
            "etat": etat,
            "etats": [e[0] for e in Requisition.ETATS],
        },
    )


@role_required(ROLE_GESTIONNAIRE)
def liste_traitees(request):
    q = (request.GET.get("q") or "").strip()

    qs = (
        Requisition.objects.select_related(
            "soumetteur",
            "soumetteur__direction_affectee",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        )
        .prefetch_related("lignes__article")
        .filter(etat_requisition=Requisition.ETAT_TRAITEE)
    )

    if q:
        qs = qs.filter(
            Q(motif_global__icontains=q)
            | Q(soumetteur__email__icontains=q)
            | Q(soumetteur__direction_affectee__nom__icontains=q)
            | Q(traitee_par__email__icontains=q)
            | Q(traitee_par__nom__icontains=q)
            | Q(traitee_par__prenom__icontains=q)
        )

    return render(
        request,
        "requisitions/requisitions_traitees.html",
        {
            "requisitions": qs.order_by("-date_livraison", "-id"),
            "q": q,
        },
    )


def detail(request, pk: int):
    req = get_object_or_404(
        Requisition.objects.select_related(
            "soumetteur",
            "soumetteur__direction_affectee",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        ).prefetch_related("lignes__article"),
        pk=pk,
    )

    if not _can_view_requisition(request.user, req):
        return _forbidden()

    rn = role_name(request.user)

    if request.user.is_authenticated:
        enregistrer_audit(
            action=AuditLog.Action.CONSULTATION,
            user=request.user,
            request=request,
            app_label="requisitions",
            cible=req,
            message="Consultation d'une réquisition.",
            meta={"etat": req.etat_requisition, "role_consultant": rn},
        )

    is_direction_readonly = (
        rn == ROLE_DIRECTEUR_DIRECTION and _same_direction(request.user, req)
    )

    can_confirm_direction = (
        is_direction_readonly and req.etat_requisition == Requisition.ETAT_EN_ATTENTE
    )

    can_modify_secretaire = (
        rn == ROLE_SECRETAIRE
        and req.soumetteur_id == request.user.id
        and req.est_modifiable_par_secretaire()
    )

    can_modify_direction = (
        rn == ROLE_DIRECTEUR_DIRECTION
        and _same_direction(request.user, req)
        and req.etat_requisition == Requisition.ETAT_EN_ATTENTE
    )

    can_accuser_reception = (
        rn == ROLE_SECRETAIRE
        and req.peut_accuser_reception_par_secretaire(request.user)
    )

    can_traiter = (
        rn == ROLE_GESTIONNAIRE
        and req.etat_requisition == Requisition.ETAT_VALIDEE
    )

    can_demander_modification_gestionnaire = (
        rn == ROLE_GESTIONNAIRE
        and req.etat_requisition == Requisition.ETAT_VALIDEE
    )

    can_transferer_daa = (
        rn == ROLE_GESTIONNAIRE
        and req.etat_requisition == Requisition.ETAT_VALIDEE
        and not req.transferee_vers_directeur_daa
    )

    can_demander_modification_daa = (
        rn == ROLE_DIRECTEUR_DAA
        and req.transferee_vers_directeur_daa
        and req.directeur_daa_id == request.user.id
        and req.etat_requisition not in (
            Requisition.ETAT_REJETEE,
            Requisition.ETAT_EN_ATTENTE_MODIF,
        )
    )

    context = {
        "requisition": req,
        "is_direction_readonly": is_direction_readonly,
        "can_confirm_direction": can_confirm_direction,
        "can_modify_secretaire": can_modify_secretaire,
        "can_modify_direction": can_modify_direction,
        "can_accuser_reception": can_accuser_reception,
        "can_traiter": can_traiter,
        "can_demander_modification_gestionnaire": can_demander_modification_gestionnaire,
        "can_transferer_daa": can_transferer_daa,
        "can_demander_modification_daa": can_demander_modification_daa,
    }
    return render(request, "requisitions/detail.html", context)


@role_required(ROLE_SECRETAIRE, ROLE_DIRECTEUR_DIRECTION)
def modifier(request, pk: int):
    req = get_object_or_404(
        Requisition.objects.select_related(
            "soumetteur",
            "soumetteur__direction_affectee",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        ).prefetch_related("lignes__article"),
        pk=pk,
    )

    if not _can_modify_requisition(request.user, req):
        messages.error(
            request,
            f"Modification interdite : état actuel = '{req.etat_requisition}'.",
        )
        return redirect("requisitions:detail", pk=req.pk)

    rn = role_name(request.user)

    if request.method == "POST":
        form = RequisitionUpdateForm(request.POST, instance=req)
        formset = LigneRequisitionUpdateFormSet(request.POST, instance=req)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    req = form.save(commit=False)
                    req.full_clean()
                    req.save()

                    formset.instance = req
                    formset.save()

                    if (
                        rn == ROLE_SECRETAIRE
                        and req.etat_requisition == Requisition.ETAT_EN_ATTENTE_MODIF
                    ):
                        req = secretaire_apres_modification(requisition=req)

                    message_audit = (
                        "Modification d'une réquisition par la secrétaire."
                        if rn == ROLE_SECRETAIRE
                        else "Modification d'une réquisition par le Directeur de direction."
                    )

                    enregistrer_audit(
                        action=AuditLog.Action.MODIFICATION,
                        user=request.user,
                        request=request,
                        app_label="requisitions",
                        cible=req,
                        message=message_audit,
                        meta={"etat": req.etat_requisition, "role_modificateur": rn},
                    )

            except ValueError as e:
                messages.error(request, str(e))
                return render(
                    request,
                    "requisitions/modifier.html",
                    {
                        "form": form,
                        "formset": formset,
                        "requisition": req,
                    },
                )

            messages.success(request, "Réquisition modifiée.")

            if rn == ROLE_SECRETAIRE:
                return redirect("requisitions:mes")

            return redirect("requisitions:detail", pk=req.pk)

        messages.error(request, "Veuillez corriger les erreurs.")

    else:
        form = RequisitionUpdateForm(instance=req)
        formset = LigneRequisitionUpdateFormSet(instance=req)

    return render(
        request,
        "requisitions/modifier.html",
        {
            "form": form,
            "formset": formset,
            "requisition": req,
        },
    )


@role_required(ROLE_DIRECTEUR_DIRECTION)
def valider_direction(request, pk: int):
    req = get_object_or_404(
        Requisition.objects.select_related(
            "soumetteur",
            "soumetteur__direction_affectee",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        ).prefetch_related("lignes__article"),
        pk=pk,
    )

    if not _same_direction(request.user, req):
        return _forbidden()

    if req.etat_requisition != Requisition.ETAT_EN_ATTENTE:
        messages.error(request, "Cette réquisition n'est plus en attente : action impossible.")
        return redirect("requisitions:detail", pk=req.pk)

    if request.method != "POST":
        return redirect("requisitions:detail", pk=req.pk)

    lien_detail = _abs(request, "requisitions:detail", pk=req.pk)

    try:
        req = valider_par_directeur_direction(
            requisition=req,
            directeur=request.user,
            lien_detail=lien_detail,
        )
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("requisitions:detail", pk=req.pk)

    enregistrer_audit(
        action=AuditLog.Action.VALIDATION,
        user=request.user,
        request=request,
        app_label="requisitions",
        cible=req,
        message="Validation d'une réquisition par le Directeur de direction.",
        meta={"etat": req.etat_requisition},
    )

    messages.success(request, "Réquisition confirmée (validée).")
    return redirect("core:a_confirmer")


@role_required(ROLE_GESTIONNAIRE, ROLE_DIRECTEUR_DAA)
def demander_modification_view(request, pk: int):
    req = get_object_or_404(
        Requisition.objects.select_related(
            "soumetteur",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        ).prefetch_related("lignes__article"),
        pk=pk,
    )

    rn = role_name(request.user)

    if rn == ROLE_GESTIONNAIRE:
        if req.etat_requisition != Requisition.ETAT_VALIDEE:
            return _forbidden()
    elif rn == ROLE_DIRECTEUR_DAA:
        if not (req.transferee_vers_directeur_daa and req.directeur_daa_id == request.user.id):
            return _forbidden()

    if request.method == "POST":
        motif = (request.POST.get("motif") or "").strip()
        if not motif:
            messages.error(request, "Motif obligatoire.")
            return redirect("requisitions:demander_modification", pk=req.pk)

        lien_detail = _abs(request, "requisitions:detail", pk=req.pk)

        try:
            req = demander_modification(
                requisition=req,
                acteur=request.user,
                motif=motif,
                lien_detail=lien_detail,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("requisitions:detail", pk=req.pk)

        enregistrer_audit(
            action=AuditLog.Action.MODIFICATION,
            user=request.user,
            request=request,
            app_label="requisitions",
            cible=req,
            message="Demande de modification d'une réquisition.",
            meta={"motif": motif, "etat": req.etat_requisition},
        )

        messages.success(
            request,
            "Demande de modification envoyée. État => En attente de modification.",
        )
        return redirect("requisitions:detail", pk=req.pk)

    return render(request, "requisitions/demander_modification.html", {"requisition": req})


@role_required(ROLE_GESTIONNAIRE)
def traiter(request, pk: int):
    req = get_object_or_404(
        Requisition.objects.select_related(
            "soumetteur",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        ).prefetch_related("lignes__article"),
        pk=pk,
    )

    if req.etat_requisition != Requisition.ETAT_VALIDEE:
        return _forbidden()

    if request.method == "POST":
        quantites = {}

        for l in req.lignes.all():
            key_quantite = f"quantite_livree_{l.id}"
            key_unite = f"unite_livree_{l.id}"

            try:
                quantite = int(request.POST.get(key_quantite, "0") or 0)
            except ValueError:
                quantite = 0

            unite = (request.POST.get(key_unite, "") or "").strip() or l.unite_demandee or "Unité"

            quantites[l.id] = {
                "quantite": quantite,
                "unite": unite,
            }

        lien_detail = _abs(request, "requisitions:detail", pk=req.pk)

        try:
            req = traiter_requisition(
                requisition=req,
                gestionnaire=request.user,
                quantites_livrees=quantites,
                lien_detail=lien_detail,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("requisitions:detail", pk=req.pk)
        except Exception as ex:
            messages.error(request, str(ex))
            return redirect("requisitions:detail", pk=req.pk)

        enregistrer_audit(
            action=AuditLog.Action.TRAITEMENT,
            user=request.user,
            request=request,
            app_label="requisitions",
            cible=req,
            message="Traitement d'une réquisition par le gestionnaire.",
            meta={"etat": req.etat_requisition, "quantites_livrees": quantites},
        )

        messages.success(request, "Réquisition traitée. État => Traité.")
        return redirect("requisitions:detail", pk=req.pk)

    return render(request, "requisitions/traiter.html", {"requisition": req})


@role_required(ROLE_SECRETAIRE)
def accuser_reception_view(request, pk: int):
    req = get_object_or_404(
        Requisition.objects.select_related(
            "soumetteur",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        ).prefetch_related("lignes__article"),
        pk=pk,
        soumetteur=request.user,
    )

    if request.method != "POST":
        return redirect("requisitions:detail", pk=req.pk)

    lien_detail = _abs(request, "requisitions:detail", pk=req.pk)

    try:
        req = accuser_reception(
            requisition=req,
            secretaire=request.user,
            lien_detail=lien_detail,
        )
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("requisitions:detail", pk=req.pk)

    enregistrer_audit(
        action=AuditLog.Action.VALIDATION,
        user=request.user,
        request=request,
        app_label="requisitions",
        cible=req,
        message="Accusé de réception d'une réquisition.",
        meta={"etat": req.etat_requisition, "date_reception": str(req.date_reception)},
    )

    messages.success(request, "Réception accusée avec succès.")
    return redirect("requisitions:detail", pk=req.pk)


@role_required(ROLE_GESTIONNAIRE)
def transferer_daa(request, pk: int):
    req = get_object_or_404(
        Requisition.objects.select_related(
            "soumetteur",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        ).prefetch_related("lignes__article"),
        pk=pk,
    )

    if req.etat_requisition != Requisition.ETAT_VALIDEE:
        messages.error(request, "Transfert impossible : la réquisition doit être 'Validé'.")
        return redirect("requisitions:detail", pk=req.pk)

    if req.transferee_vers_directeur_daa:
        messages.error(request, "Déjà transférée au Directeur DAA.")
        return redirect("requisitions:detail", pk=req.pk)

    if request.method == "POST":
        directeur_daa_id = request.POST.get("directeur_daa_id")
        directeur_daa = get_object_or_404(
            User,
            pk=directeur_daa_id,
            role__nom_role=ROLE_DIRECTEUR_DAA,
            statut="Actif",
        )

        lien_detail = _abs(request, "requisitions:detail", pk=req.pk)

        try:
            req = transferer_vers_directeur_daa(
                requisition=req,
                gestionnaire=request.user,
                directeur_daa=directeur_daa,
                lien_detail=lien_detail,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("requisitions:detail", pk=req.pk)

        enregistrer_audit(
            action=AuditLog.Action.TRANSFERT,
            user=request.user,
            request=request,
            app_label="requisitions",
            cible=req,
            message="Transfert d'une réquisition au Directeur DAA.",
            meta={
                "directeur_daa_id": str(directeur_daa.pk),
                "directeur_daa_email": str(directeur_daa.email or ""),
                "etat": req.etat_requisition,
            },
        )

        messages.success(request, "Transférée au Directeur DAA.")
        return redirect("requisitions:detail", pk=req.pk)

    directeurs_daa = User.objects.filter(
        role__nom_role=ROLE_DIRECTEUR_DAA,
        statut="Actif",
    ).order_by("email")
    return render(
        request,
        "requisitions/transferer_daa.html",
        {"requisition": req, "directeurs_daa": directeurs_daa},
    )


@role_required(ROLE_DIRECTEUR_DAA)
def valider_daa(request, pk: int):
    req = get_object_or_404(
        Requisition.objects.select_related(
            "soumetteur",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        ).prefetch_related("lignes__article"),
        pk=pk,
        directeur_daa=request.user,
        transferee_vers_directeur_daa=True,
    )

    if request.method == "POST":
        lien_detail = _abs(request, "requisitions:detail", pk=req.pk)

        try:
            req = valider_par_directeur_daa(
                requisition=req,
                directeur_daa=request.user,
                lien_detail=lien_detail,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("requisitions:detail", pk=req.pk)

        enregistrer_audit(
            action=AuditLog.Action.VALIDATION,
            user=request.user,
            request=request,
            app_label="requisitions",
            cible=req,
            message="Validation d'une réquisition par le Directeur DAA.",
            meta={"sceau": str(req.sceau_directeur_daa or ""), "etat": req.etat_requisition},
        )

        messages.success(request, "Réquisition confirmée (DAA).")
        return redirect("requisitions:detail", pk=req.pk)

    return render(
        request,
        "requisitions/confirm.html",
        {"requisition": req, "titre": "Confirmer (DAA)", "btn": "Confirmer"},
    )


@role_required(ROLE_DIRECTEUR_DAA)
def rejeter_daa(request, pk: int):
    req = get_object_or_404(
        Requisition.objects.select_related(
            "soumetteur",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        ).prefetch_related("lignes__article"),
        pk=pk,
        directeur_daa=request.user,
        transferee_vers_directeur_daa=True,
    )

    if request.method == "POST":
        motif = (request.POST.get("motif") or "").strip()
        lien_detail = _abs(request, "requisitions:detail", pk=req.pk)

        try:
            req = rejeter_par_directeur_daa(
                requisition=req,
                directeur_daa=request.user,
                motif=motif,
                lien_detail=lien_detail,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("requisitions:detail", pk=req.pk)

        enregistrer_audit(
            action=AuditLog.Action.REJET,
            user=request.user,
            request=request,
            app_label="requisitions",
            cible=req,
            message="Rejet d'une réquisition par le Directeur DAA.",
            meta={"motif": motif, "etat": req.etat_requisition},
        )

        messages.success(request, "Réquisition rejetée (DAA).")
        return redirect("requisitions:detail", pk=req.pk)

    return render(
        request,
        "requisitions/rejeter.html",
        {"requisition": req, "titre": "Rejeter (DAA)"},
    )


@role_required(ROLE_SECRETAIRE)
def mes_requisitions(request):
    q = (request.GET.get("q") or "").strip()
    etat = (request.GET.get("etat") or "").strip()

    qs = (
        Requisition.objects.select_related(
            "soumetteur",
            "soumetteur__direction_affectee",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        )
        .prefetch_related("lignes__article")
        .filter(soumetteur=request.user)
    )

    if q:
        qs = qs.filter(
            Q(soumetteur__direction_affectee__nom__icontains=q)
            | Q(motif_global__icontains=q)
            | Q(remarque__icontains=q)
        )

    if etat:
        qs = qs.filter(etat_requisition=etat)

    qs = qs.order_by("-date_preparation", "-id")

    return render(
        request,
        "requisitions/mes_requisitions.html",
        {
            "requisitions": qs,
            "q": q,
            "etat": etat,
            "etats": Requisition.ETATS,
        },
    )


@role_required(ROLE_DIRECTEUR_DIRECTION)
def rejeter_direction(request, pk: int):
    return HttpResponseForbidden("Accès refusé ")


@role_required(ROLE_GESTIONNAIRE)
def rejeter_gestionnaire_view(request, pk: int):
    return HttpResponseForbidden("Accès refusé ")

def detail_pdf(request, pk: int):
    req = get_object_or_404(
        Requisition.objects.select_related(
            "soumetteur",
            "soumetteur__direction_affectee",
            "directeur_direction",
            "directeur_daa",
            "traitee_par",
            "recue_par",
        ).prefetch_related("lignes__article"),
        pk=pk,
    )

    if not _can_view_requisition(request.user, req):
        return _forbidden()

    def fmt_dt(value):
        if not value:
            return "—"
        return value.strftime("%d/%m/%Y à %H:%M")

    def fmt_user(user):
        if not user:
            return "—"
        nom = f"{getattr(user, 'prenom', '')} {getattr(user, 'nom', '')}".strip()
        return nom or getattr(user, "email", "—") or "—"

    def footer(canvas, doc):
        canvas.saveState()
        width, _ = A4
        y = 10 * mm

        canvas.setStrokeColor(colors.HexColor("#d8e2ee"))
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, y + 5 * mm, width - doc.rightMargin, y + 5 * mm)

        canvas.setFont("Helvetica-Oblique", 8)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(
            doc.leftMargin,
            y,
            "Document administratif de la DGB."
        )
        canvas.drawRightString(
            width - doc.rightMargin,
            y,
            f"Réquisition REQ-{req.id}"
        )

        # Signatures fixes en bas de page
        signature_y = 20 * mm
        line_length = 58 * mm

        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(0.7)

        # Ligne gauche
        left_x1 = doc.leftMargin
        left_x2 = doc.leftMargin + line_length
        canvas.line(left_x1, signature_y, left_x2, signature_y)

        # Ligne droite
        right_x2 = width - doc.rightMargin
        right_x1 = right_x2 - line_length
        canvas.line(right_x1, signature_y, right_x2, signature_y)

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.black)

        canvas.drawCentredString(
            (left_x1 + left_x2) / 2,
            signature_y - 10,
            "Administration"
        )
        canvas.drawCentredString(
            (right_x1 + right_x2) / 2,
            signature_y - 10,
            "Demandeur"
        )

        canvas.restoreState()

    buffer = BytesIO()
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="requisition_{req.id}.pdf"'

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=11 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()

    style_brand_title = ParagraphStyle(
        "ReqBrandTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1f3b6d"),
        spaceAfter=0,
    )
    style_brand_subtitle = ParagraphStyle(
        "ReqBrandSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#38527d"),
        spaceAfter=0,
    )
    style_doc_code = ParagraphStyle(
        "ReqDocCode",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        alignment=2,
        textColor=colors.HexColor("#5f6f86"),
        spaceAfter=0,
    )
    style_doc_date = ParagraphStyle(
        "ReqDocDate",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=10,
        alignment=2,
        textColor=colors.HexColor("#7b8899"),
        spaceAfter=0,
    )
    style_title = ParagraphStyle(
        "ReqTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=24,
        alignment=1,
        textColor=colors.HexColor("#132238"),
        spaceAfter=0,
    )
    style_section = ParagraphStyle(
        "ReqSection",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor("#162338"),
        spaceAfter=0,
    )
    style_label = ParagraphStyle(
        "ReqLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=9,
        textColor=colors.HexColor("#6a7a90"),
        spaceAfter=2,
    )
    style_value = ParagraphStyle(
        "ReqValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=11.5,
        textColor=colors.HexColor("#132238"),
        spaceAfter=0,
    )
    style_body = ParagraphStyle(
        "ReqBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.4,
        leading=13,
        textColor=colors.HexColor("#132238"),
        spaceAfter=0,
    )
    style_small = ParagraphStyle(
        "ReqSmall",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#5e718d"),
        spaceAfter=0,
    )

    elements = []

    logo_path = finders.find("icons/mef.png")
    logo = None
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=20 * mm, height=20 * mm)
        except Exception:
            logo = None

    direction_label = "—"
    if req.soumetteur and getattr(req.soumetteur, "direction_affectee", None):
        direction_label = str(req.soumetteur.direction_affectee)
    elif getattr(req, "direction_demandeuse", None):
        direction_label = req.direction_demandeuse

    brand_block = [
        Paragraph("Ministère de l'Économie et des Finances", style_brand_title),
        Paragraph("Direction Générale du Budget / DAA", style_brand_subtitle),
    ]

    meta_block = [
        Paragraph(f"REQ-{req.id}", style_doc_code),
        Paragraph(f"Émis le {fmt_dt(req.date_preparation)}", style_doc_date),
    ]

    if logo:
        header_table = Table(
            [[logo, brand_block, meta_block]],
            colWidths=[22 * mm, 108 * mm, 40 * mm],
        )
    else:
        header_table = Table(
            [[brand_block, meta_block]],
            colWidths=[130 * mm, 40 * mm],
        )

    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (-1, 0), (-1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    separator = Table([[""]], colWidths=[170 * mm], rowHeights=[1.2 * mm])
    separator.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dfe7f1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    elements.append(header_table)
    elements.append(Spacer(1, 4 * mm))
    elements.append(separator)
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph("Détail de la réquisition", style_title))
    elements.append(Spacer(1, 5 * mm))

    info_table = Table(
        [[
            [
                Paragraph("<b>Numéro de réquisition</b>", style_label),
                Paragraph(f"REQ-{req.id}", style_value),
            ],
            [
                Paragraph("<b>Soumetteur</b>", style_label),
                Paragraph(fmt_user(req.soumetteur), style_value),
            ],
            [
                Paragraph("<b>Direction</b>", style_label),
                Paragraph(direction_label, style_value),
            ],
        ]],
        colWidths=[58 * mm, 58 * mm, 54 * mm],
    )
    info_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dbe4ef")),
                ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#e9eff5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))

    motif_box = Table(
        [[Paragraph("<b>Motif global</b>", style_section)],
         [Paragraph(req.motif_global or "—", style_body)]],
        colWidths=[170 * mm],
    )
    motif_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f7f9fc")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dbe4ef")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(motif_box)
    elements.append(Spacer(1, 4 * mm))

    if req.remarque:
        remarque_box = Table(
            [[Paragraph("<b>Remarque</b>", style_section)],
             [Paragraph(req.remarque, style_body)]],
            colWidths=[170 * mm],
        )
        remarque_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f7f9fc")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dbe4ef")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(remarque_box)
        elements.append(Spacer(1, 4 * mm))

    if req.demande_modification_motif:
        modif_box = Table(
            [[Paragraph("<b>Motif de demande de modification</b>", style_section)],
             [Paragraph(req.demande_modification_motif, style_body)]],
            colWidths=[170 * mm],
        )
        modif_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f7f9fc")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dbe4ef")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(modif_box)
        elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph("<b>Lignes de réquisition</b>", style_section))
    elements.append(Spacer(1, 2.5 * mm))

    table_data = [
        [
            Paragraph("<b>Article</b>", style_small),
            Paragraph("<b>Qté demandée</b>", style_small),
            Paragraph("<b>Conditionnement demandé</b>", style_small),
            Paragraph("<b>Qté livrée</b>", style_small),
            Paragraph("<b>Conditionnement livré</b>", style_small),
            Paragraph("<b>Motif</b>", style_small),
        ]
    ]

    for ligne in req.lignes.all():
        quantite_livree = str(ligne.quantite_livree) if int(ligne.quantite_livree or 0) > 0 else "—"
        conditionnement_livre = (
            str(ligne.unite_livree or "Unité") if int(ligne.quantite_livree or 0) > 0 else "—"
        )

        table_data.append(
            [
                Paragraph(getattr(ligne.article, "nom", "—"), style_value),
                Paragraph(str(ligne.quantite_demandee or 0), style_value),
                Paragraph(str(ligne.unite_demandee or "Unité"), style_value),
                Paragraph(quantite_livree, style_value),
                Paragraph(conditionnement_livre, style_value),
                Paragraph(ligne.motif_article or "—", style_value),
            ]
        )

    lignes_table = Table(
        table_data,
        colWidths=[44 * mm, 24 * mm, 34 * mm, 22 * mm, 32 * mm, 28 * mm],
        repeatRows=1,
    )
    lignes_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3f9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#183153")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.8),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dbe4ef")),
                ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#e9eff5")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfcfe")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("ALIGN", (3, 1), (3, -1), "RIGHT"),
            ]
        )
    )

    elements.append(lignes_table)

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response