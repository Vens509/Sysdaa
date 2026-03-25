from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    # Optionnel (ex: notif liée à une réquisition)
    requisition = models.ForeignKey(
        "requisitions.Requisition",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )

    titre = models.CharField(max_length=160, blank=True, default="")
    message = models.TextField()

    lu = models.BooleanField(default=False)
    date_creation = models.DateTimeField(default=timezone.now)
    date_lecture = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_creation", "-id"]
        indexes = [
            models.Index(fields=["destinataire", "lu", "date_creation"]),
            models.Index(fields=["requisition"]),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self) -> str:
        base = self.titre.strip() or "Notification"
        return f"{base} -> {self.destinataire} (lu={self.lu})"

    def marquer_lu(self):
        if not self.lu:
            self.lu = True
            self.date_lecture = timezone.now()
            self.save(update_fields=["lu", "date_lecture"])
