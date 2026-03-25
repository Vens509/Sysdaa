from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from audit.models import AuditLog
from audit.services import audit_log as enregistrer_audit

from core.permissions import utilisateurs_required

from .forms import (
    AdminResetPasswordForm,
    UtilisateurCreationForm,
    UtilisateurUpdateForm,
)
from .models import Utilisateur


def _login_url() -> str:
    return reverse("custom_login")


@login_required(login_url=_login_url)
@utilisateurs_required
def liste_utilisateurs(request):
    qs = Utilisateur.objects.select_related("role", "direction_affectee").order_by("email")
    q = (request.GET.get("q") or "").strip()

    if q:
        qs = qs.filter(
            Q(email__icontains=q)
            | Q(nom__icontains=q)
            | Q(prenom__icontains=q)
            | Q(role__nom_role__icontains=q)
            | Q(direction_affectee__nom__icontains=q)
        )

    utilisateurs = qs

    enregistrer_audit(
        action=AuditLog.Action.CONSULTATION,
        user=request.user,
        request=request,
        app_label="utilisateurs",
        message="Consultation de la liste des utilisateurs.",
        meta={
            "q": q,
            "nombre_resultats": utilisateurs.count(),
        },
    )

    return render(
        request,
        "utilisateurs/liste.html",
        {
            "utilisateurs": utilisateurs,
            "q": q,
        },
    )


@login_required(login_url=_login_url)
@utilisateurs_required
def creer_utilisateur_view(request):
    if request.method == "POST":
        form = UtilisateurCreationForm(request.POST)
        if form.is_valid():
            user_obj = form.save()

            enregistrer_audit(
                action=AuditLog.Action.CREATION,
                user=request.user,
                request=request,
                app_label="utilisateurs",
                cible=user_obj,
                identifiant_saisi=user_obj.email,
                message="Création d'un utilisateur.",
                meta={
                    "email": user_obj.email,
                    "nom": user_obj.nom,
                    "prenom": user_obj.prenom,
                    "role": str(user_obj.role),
                    "direction_affectee": str(user_obj.direction_affectee) if user_obj.direction_affectee else "",
                    "statut": user_obj.statut,
                },
            )

            messages.success(request, "Utilisateur créé avec succès.")
            return redirect("utilisateurs:liste")

        enregistrer_audit(
            action=AuditLog.Action.CREATION,
            user=request.user,
            request=request,
            app_label="utilisateurs",
            niveau=AuditLog.Niveau.WARNING,
            succes=False,
            identifiant_saisi=request.POST.get("email", ""),
            message="Échec de création d'un utilisateur : formulaire invalide.",
            meta={
                "email": request.POST.get("email", ""),
                "nom": request.POST.get("nom", ""),
                "prenom": request.POST.get("prenom", ""),
                "role": request.POST.get("role", ""),
                "erreurs": form.errors.get_json_data(),
            },
        )

        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = UtilisateurCreationForm()

    return render(request, "utilisateurs/form.html", {"form": form, "mode": "create"})


@login_required(login_url=_login_url)
@utilisateurs_required
def modifier_utilisateur_view(request, pk: int):
    user_obj = get_object_or_404(Utilisateur.objects.select_related("role", "direction_affectee"), pk=pk)

    if request.method == "POST":
        ancien_email = user_obj.email
        ancien_nom = user_obj.nom
        ancien_prenom = user_obj.prenom
        ancien_role = str(user_obj.role) if user_obj.role else ""
        ancienne_direction = str(user_obj.direction_affectee) if user_obj.direction_affectee else ""
        ancien_statut = user_obj.statut

        form = UtilisateurUpdateForm(request.POST, instance=user_obj)
        if form.is_valid():
            user_modifie = form.save()

            meta = {
                "avant": {
                    "email": ancien_email,
                    "nom": ancien_nom,
                    "prenom": ancien_prenom,
                    "role": ancien_role,
                    "direction_affectee": ancienne_direction,
                    "statut": ancien_statut,
                },
                "apres": {
                    "email": user_modifie.email,
                    "nom": user_modifie.nom,
                    "prenom": user_modifie.prenom,
                    "role": str(user_modifie.role) if user_modifie.role else "",
                    "direction_affectee": str(user_modifie.direction_affectee) if user_modifie.direction_affectee else "",
                    "statut": user_modifie.statut,
                },
            }

            action = AuditLog.Action.MODIFICATION
            message = "Modification d'un utilisateur."

            if ancien_role != (str(user_modifie.role) if user_modifie.role else ""):
                action = AuditLog.Action.ATTRIBUTION_ROLE
                message = "Modification d'un utilisateur avec changement de rôle."

            enregistrer_audit(
                action=action,
                user=request.user,
                request=request,
                app_label="utilisateurs",
                cible=user_modifie,
                identifiant_saisi=user_modifie.email,
                message=message,
                meta=meta,
            )

            messages.success(request, "Utilisateur modifié avec succès.")
            return redirect("utilisateurs:liste")

        enregistrer_audit(
            action=AuditLog.Action.MODIFICATION,
            user=request.user,
            request=request,
            app_label="utilisateurs",
            niveau=AuditLog.Niveau.WARNING,
            succes=False,
            cible_type="Utilisateur",
            cible_id=str(user_obj.pk),
            cible_label=str(user_obj),
            identifiant_saisi=request.POST.get("email", "") or user_obj.email,
            message="Échec de modification d'un utilisateur : formulaire invalide.",
            meta={
                "email": request.POST.get("email", ""),
                "nom": request.POST.get("nom", ""),
                "prenom": request.POST.get("prenom", ""),
                "role": request.POST.get("role", ""),
                "statut": request.POST.get("statut", ""),
                "erreurs": form.errors.get_json_data(),
            },
        )

        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = UtilisateurUpdateForm(instance=user_obj)

    return render(
        request,
        "utilisateurs/form.html",
        {"form": form, "mode": "edit", "u": user_obj},
    )


@login_required(login_url=_login_url)
@utilisateurs_required
def toggle_statut_utilisateur_view(request, pk: int):
    user_obj = get_object_or_404(Utilisateur.objects.select_related("role", "direction_affectee"), pk=pk)

    if request.user.pk == user_obj.pk:
        enregistrer_audit(
            action=AuditLog.Action.DESACTIVATION,
            user=request.user,
            request=request,
            app_label="utilisateurs",
            niveau=AuditLog.Niveau.WARNING,
            succes=False,
            cible=user_obj,
            identifiant_saisi=user_obj.email,
            message="Échec de modification du statut : tentative d'auto-désactivation.",
            meta={
                "email": user_obj.email,
                "statut_actuel": user_obj.statut,
            },
        )

        messages.error(request, "Action impossible : vous ne pouvez pas désactiver votre propre compte.")
        return redirect("utilisateurs:liste")

    ancien_statut = (user_obj.statut or "").strip()
    user_obj.statut = "Inactif" if ancien_statut == "Actif" else "Actif"
    user_obj.save(update_fields=["statut"])

    action = AuditLog.Action.DESACTIVATION if user_obj.statut == "Inactif" else AuditLog.Action.ACTIVATION
    message = "Désactivation d'un utilisateur." if user_obj.statut == "Inactif" else "Activation d'un utilisateur."

    enregistrer_audit(
        action=action,
        user=request.user,
        request=request,
        app_label="utilisateurs",
        cible=user_obj,
        identifiant_saisi=user_obj.email,
        message=message,
        meta={
            "email": user_obj.email,
            "ancien_statut": ancien_statut,
            "nouveau_statut": user_obj.statut,
        },
    )

    messages.success(request, f"Statut mis à jour : {user_obj.email} -> {user_obj.statut}")
    return redirect("utilisateurs:liste")


@login_required(login_url=_login_url)
@utilisateurs_required
def reset_password_utilisateur_view(request, pk: int):
    user_obj = get_object_or_404(Utilisateur.objects.select_related("role", "direction_affectee"), pk=pk)

    if request.user.pk == user_obj.pk:
        enregistrer_audit(
            action=AuditLog.Action.MODIFICATION,
            user=request.user,
            request=request,
            app_label="utilisateurs",
            niveau=AuditLog.Niveau.WARNING,
            succes=False,
            cible=user_obj,
            identifiant_saisi=user_obj.email,
            message="Échec de réinitialisation du mot de passe : tentative sur son propre compte.",
            meta={
                "email": user_obj.email,
            },
        )

        messages.error(request, "Action impossible : utilisez la procédure normale pour votre propre mot de passe.")
        return redirect("utilisateurs:liste")

    if request.method == "POST":
        form = AdminResetPasswordForm(request.POST)
        if form.is_valid():
            user_obj.set_password(form.cleaned_data["password1"])
            user_obj.save(update_fields=["password"])

            enregistrer_audit(
                action=AuditLog.Action.MODIFICATION,
                user=request.user,
                request=request,
                app_label="utilisateurs",
                cible=user_obj,
                identifiant_saisi=user_obj.email,
                message="Réinitialisation administrative du mot de passe d'un utilisateur.",
                meta={
                    "email": user_obj.email,
                },
            )

            messages.success(request, f"Mot de passe réinitialisé pour {user_obj.email}.")
            return redirect("utilisateurs:liste")

        enregistrer_audit(
            action=AuditLog.Action.MODIFICATION,
            user=request.user,
            request=request,
            app_label="utilisateurs",
            niveau=AuditLog.Niveau.WARNING,
            succes=False,
            cible=user_obj,
            identifiant_saisi=user_obj.email,
            message="Échec de réinitialisation administrative du mot de passe : formulaire invalide.",
            meta={
                "email": user_obj.email,
                "erreurs": form.errors.get_json_data(),
            },
        )

        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = AdminResetPasswordForm()

    return render(
        request,
        "utilisateurs/reset_password.html",
        {"form": form, "u": user_obj},
    )