from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    class Niveau(models.TextChoices):
        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        ERROR = "ERROR", "Error"

    class Action(models.TextChoices):
        GENERATION_RAPPORT = "GENERATION_RAPPORT", "Génération rapport"

        CREATION = "CREATION", "Création"
        CONSULTATION = "CONSULTATION", "Consultation"
        MODIFICATION = "MODIFICATION", "Modification"
        SUPPRESSION = "SUPPRESSION", "Suppression"

        VALIDATION = "VALIDATION", "Validation"
        REJET = "REJET", "Rejet"
        TRAITEMENT = "TRAITEMENT", "Traitement"
        TRANSFERT = "TRANSFERT", "Transfert"

        CONNEXION = "CONNEXION", "Connexion"
        DECONNEXION = "DECONNEXION", "Déconnexion"

        ACTIVATION = "ACTIVATION", "Activation"
        DESACTIVATION = "DESACTIVATION", "Désactivation"
        ATTRIBUTION_ROLE = "ATTRIBUTION_ROLE", "Attribution rôle"

        # -------- NOTIFICATIONS --------
        ENVOI_NOTIFICATION = "ENVOI_NOTIFICATION", "Envoi notification"
        ENVOI_EMAIL_NOTIFICATION = "ENVOI_EMAIL_NOTIFICATION", "Envoi email notification"
        CONSULTATION_NOTIFICATIONS = "CONSULTATION_NOTIFICATIONS", "Consultation notifications"
        LECTURE_NOTIFICATION = "LECTURE_NOTIFICATION", "Lecture notification"

    class Meta:
        verbose_name = "Audit"
        verbose_name_plural = "Audits"
        ordering = ["-date_action", "-id"]
        indexes = [
            models.Index(fields=["date_action"]),
            models.Index(fields=["app", "action"]),
            models.Index(fields=["cible_type", "cible_id"]),
            models.Index(fields=["acteur", "date_action"]),
            models.Index(fields=["niveau", "date_action"]),
            models.Index(fields=["identifiant_saisi"]),
        ]

    date_action = models.DateTimeField(default=timezone.now)

    niveau = models.CharField(
        max_length=10,
        choices=Niveau.choices,
        default=Niveau.INFO,
    )

    app = models.CharField(max_length=80)

    action = models.CharField(
        max_length=80,
        choices=Action.choices,
    )

    acteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audits",
    )

    identifiant_saisi = models.CharField(
        max_length=150,
        blank=True,
        default="",
    )

    ip = models.GenericIPAddressField(null=True, blank=True)

    user_agent = models.CharField(
        max_length=300,
        blank=True,
        default="",
    )

    cible_type = models.CharField(
        max_length=120,
        blank=True,
        default="",
    )

    cible_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
    )

    cible_label = models.CharField(
        max_length=200,
        blank=True,
        default="",
    )

    message = models.CharField(
        max_length=250,
        blank=True,
        default="",
    )

    details = models.JSONField(
        blank=True,
        default=dict,
    )

    succes = models.BooleanField(default=True)

    def __str__(self) -> str:
        cible = (
            f"{self.cible_type}:{self.cible_id}"
            if self.cible_type and self.cible_id
            else "-"
        )
        return f"[{self.date_action:%Y-%m-%d %H:%M}] {self.app}.{self.action} cible={cible} ok={self.succes}"