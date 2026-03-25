from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django_otp.plugins.otp_email.models import EmailDevice

from core.permissions import otp_required_for_user
from .models import Role

User = get_user_model()

EMAIL_DEVICE_NAME = "otp_email"


@dataclass(frozen=True)
class CreationUtilisateurResultat:
    utilisateur_id: int


def creer_utilisateur(
    email: str,
    nom: str,
    prenom: str,
    role_id: int,
    password: str,
    statut: str = "Actif",
) -> CreationUtilisateurResultat:
    role = Role.objects.get(pk=role_id)

    user = User.objects.create_user(
        email=email,
        nom=nom,
        prenom=prenom,
        role=role,
        statut=statut,
        password=password,
    )
    return CreationUtilisateurResultat(utilisateur_id=user.id)


def synchroniser_email_otp_utilisateur(user) -> None:
    if user is None or not getattr(user, "pk", None):
        return

    email = (getattr(user, "email", "") or "").strip().lower()
    is_active = bool(getattr(user, "is_active", False))
    otp_obligatoire = otp_required_for_user(user)

    qs = EmailDevice.objects.filter(user=user, name=EMAIL_DEVICE_NAME)

    if not is_active or not email or not otp_obligatoire:
        qs.delete()
        return

    device, _created = EmailDevice.objects.get_or_create(
        user=user,
        name=EMAIL_DEVICE_NAME,
        defaults={
            "confirmed": True,
            "email": email,
        },
    )

    changed = False

    if device.email != email:
        device.email = email
        changed = True

    if not device.confirmed:
        device.confirmed = True
        changed = True

    if changed:
        device.save(update_fields=["email", "confirmed"])