from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from audit.models import AuditLog
from audit.services import audit_log as enregistrer_audit

from .models import Notification


@dataclass(frozen=True)
class NotificationResultat:
    notification_id: int
    email_envoye: bool


def _email_actif() -> bool:
    """
    L'email ne doit jamais casser une action métier.
    On envoie seulement si un backend email est configuré.
    """
    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    return bool(backend and backend != "django.core.mail.backends.dummy.EmailBackend")


def _safe_send_email(*, to_email: str, subject: str, body: str) -> bool:
    """
    Envoi protégé : ne lève pas d'exception (pour ne jamais casser le workflow).
    """
    if not to_email or not _email_actif():
        return False
    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "SERVER_EMAIL", "")
        send_mail(
            subject=subject,
            message=body,
            from_email=from_email or None,
            recipient_list=[to_email],
            fail_silently=True,
        )
        return True
    except Exception:
        return False


@transaction.atomic
def envoyer_notification(*, destinataire, message: str, requisition=None, titre: str = "") -> NotificationResultat:
    """
    Enregistre une notification en BD (sans email).
    (API existante conservée pour ne rien casser.)
    """
    notif = Notification.objects.create(
        destinataire=destinataire,
        requisition=requisition,
        titre=(titre or "").strip(),
        message=(message or "").strip(),
    )

    try:
        enregistrer_audit(
            action=AuditLog.Action.ENVOI_NOTIFICATION,
            acteur=destinataire,
            app_label="notifications",
            cible_type="Notification",
            cible_id=str(notif.pk),
            cible_label=(notif.titre or "Notification").strip() or f"Notification #{notif.pk}",
            message="Envoi d'une notification interne.",
            details={
                "notification_id": notif.pk,
                "destinataire_id": getattr(destinataire, "pk", None),
                "destinataire_email": getattr(destinataire, "email", "") or "",
                "titre": notif.titre,
                "requisition_id": getattr(requisition, "pk", None),
                "email_envoye": False,
            },
            identifiant_saisi=getattr(destinataire, "email", "") or "",
        )
    except Exception:
        pass

    return NotificationResultat(notification_id=notif.id, email_envoye=False)


@transaction.atomic
def envoyer_notification_et_email(
    *,
    destinataire,
    titre: str,
    message: str,
    requisition=None,
    lien: str | None = None,
) -> NotificationResultat:
    """
    1) Crée la notification en BD
    2) Envoie un email (si backend configuré) avec éventuellement un lien vers l'écran concerné
       (ex: detail réquisition / page transfert / page validation)
    """
    notif = Notification.objects.create(
        destinataire=destinataire,
        requisition=requisition,
        titre=(titre or "").strip(),
        message=(message or "").strip(),
    )

    # Email (optionnel)
    to_email = getattr(destinataire, "email", "") or ""
    subject = (titre or "SYSDAA - Notification").strip()

    body_lines = []
    if titre:
        body_lines.append(titre.strip())
        body_lines.append("")

    body_lines.append((message or "").strip())

    if lien:
        body_lines.append("")
        body_lines.append("Lien :")
        body_lines.append(lien.strip())

    body = "\n".join([l for l in body_lines if l is not None])

    email_envoye = _safe_send_email(to_email=to_email, subject=subject, body=body)

    try:
        enregistrer_audit(
            action=AuditLog.Action.ENVOI_NOTIFICATION,
            acteur=destinataire,
            app_label="notifications",
            cible_type="Notification",
            cible_id=str(notif.pk),
            cible_label=(notif.titre or "Notification").strip() or f"Notification #{notif.pk}",
            message="Envoi d'une notification interne avec tentative d'email.",
            details={
                "notification_id": notif.pk,
                "destinataire_id": getattr(destinataire, "pk", None),
                "destinataire_email": to_email,
                "titre": notif.titre,
                "requisition_id": getattr(requisition, "pk", None),
                "lien": lien or "",
                "email_envoye": email_envoye,
            },
            identifiant_saisi=to_email,
        )
    except Exception:
        pass

    if email_envoye:
        try:
            enregistrer_audit(
                action=AuditLog.Action.ENVOI_EMAIL_NOTIFICATION,
                acteur=destinataire,
                app_label="notifications",
                cible_type="Notification",
                cible_id=str(notif.pk),
                cible_label=(notif.titre or "Notification").strip() or f"Notification #{notif.pk}",
                message="Envoi email de notification réussi.",
                details={
                    "notification_id": notif.pk,
                    "destinataire_id": getattr(destinataire, "pk", None),
                    "destinataire_email": to_email,
                    "titre": notif.titre,
                    "requisition_id": getattr(requisition, "pk", None),
                    "lien": lien or "",
                },
                identifiant_saisi=to_email,
            )
        except Exception:
            pass
    else:
        try:
            enregistrer_audit(
                action=AuditLog.Action.ENVOI_EMAIL_NOTIFICATION,
                acteur=destinataire,
                app_label="notifications",
                niveau=AuditLog.Niveau.WARNING,
                succes=False,
                cible_type="Notification",
                cible_id=str(notif.pk),
                cible_label=(notif.titre or "Notification").strip() or f"Notification #{notif.pk}",
                message="Échec ou non-envoi de l'email de notification.",
                details={
                    "notification_id": notif.pk,
                    "destinataire_id": getattr(destinataire, "pk", None),
                    "destinataire_email": to_email,
                    "titre": notif.titre,
                    "requisition_id": getattr(requisition, "pk", None),
                    "lien": lien or "",
                },
                identifiant_saisi=to_email,
            )
        except Exception:
            pass

    return NotificationResultat(notification_id=notif.id, email_envoye=email_envoye)