from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver
from two_factor.signals import user_verified

from audit.models import AuditLog
from audit.services import audit_log

from .models import Utilisateur
from .services import synchroniser_email_otp_utilisateur


@receiver(post_save, sender=Utilisateur)
def sync_email_otp_device_on_user_save(sender, instance: Utilisateur, **kwargs):
    synchroniser_email_otp_utilisateur(instance)


@receiver(user_verified)
def audit_user_verified(sender, request, user, device, **kwargs):
    audit_log(
        action=AuditLog.Action.CONNEXION,
        user=user,
        request=request,
        app_label="utilisateurs",
        message="Connexion validée par OTP email.",
        meta={
            "otp_device_class": device.__class__.__name__,
            "otp_device_name": getattr(device, "name", ""),
        },
    )