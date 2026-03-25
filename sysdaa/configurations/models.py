from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ConfigurationSysteme(models.Model):
    annee_debut = models.IntegerField()
    annee_fin = models.IntegerField()
    est_active = models.BooleanField(default=False, db_index=True)

    configurateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="configurations_systeme_creees",
    )

    class Meta:
        db_table = "configurations_systeme"
        verbose_name = "Configuration système"
        verbose_name_plural = "Configurations système"
        ordering = ["-annee_debut", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["annee_debut", "annee_fin"],
                name="uq_configuration_systeme_annee_fiscale",
            ),
            models.UniqueConstraint(
                fields=["est_active"],
                condition=Q(est_active=True),
                name="uq_configuration_systeme_unique_active",
            ),
        ]

    def clean(self):
        super().clean()

        if self.annee_debut is None or self.annee_fin is None:
            raise ValidationError("L'année fiscale doit avoir une année de début et une année de fin.")

        if self.annee_fin != self.annee_debut + 1:
            raise ValidationError("L'année fiscale doit couvrir deux années consécutives.")

    @property
    def code(self) -> str:
        return f"{self.annee_debut}-{self.annee_fin}"

    def __str__(self) -> str:
        statut = "active" if self.est_active else "inactive"
        return f"Configuration fiscale {self.code} ({statut})"


class ClotureStockMensuelle(models.Model):
    annee = models.IntegerField()
    mois = models.PositiveSmallIntegerField()
    date_execution = models.DateTimeField(default=timezone.now, db_index=True)

    nombre_articles_total = models.PositiveIntegerField(default=0)
    nombre_articles_mis_a_jour = models.PositiveIntegerField(default=0)

    configurateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="clotures_stock_mensuelles_creees",
    )

    class Meta:
        db_table = "clotures_stock_mensuelles"
        verbose_name = "Clôture stock mensuelle"
        verbose_name_plural = "Clôtures stock mensuelles"
        ordering = ["-annee", "-mois", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["annee", "mois"],
                name="uq_cloture_stock_mensuelle_periode",
            ),
            models.CheckConstraint(
                condition=Q(mois__gte=1) & Q(mois__lte=12),
                name="ck_cloture_stock_mensuelle_mois_1_12",
            ),
        ]
        indexes = [
            models.Index(fields=["annee", "mois"]),
            models.Index(fields=["date_execution"]),
        ]

    def clean(self):
        super().clean()

        erreurs: dict[str, str] = {}

        if self.annee is None:
            erreurs["annee"] = "L'année est obligatoire."

        if self.mois is None:
            erreurs["mois"] = "Le mois est obligatoire."
        elif not (1 <= int(self.mois) <= 12):
            erreurs["mois"] = "Le mois doit être compris entre 1 et 12."

        if self.nombre_articles_total is not None and int(self.nombre_articles_total) < 0:
            erreurs["nombre_articles_total"] = "La valeur ne peut pas être négative."

        if self.nombre_articles_mis_a_jour is not None and int(self.nombre_articles_mis_a_jour) < 0:
            erreurs["nombre_articles_mis_a_jour"] = "La valeur ne peut pas être négative."

        if (
            self.nombre_articles_total is not None
            and self.nombre_articles_mis_a_jour is not None
            and int(self.nombre_articles_mis_a_jour) > int(self.nombre_articles_total)
        ):
            erreurs["nombre_articles_mis_a_jour"] = (
                "Le nombre d'articles mis à jour ne peut pas dépasser le total."
            )

        if erreurs:
            raise ValidationError(erreurs)

    @property
    def code_periode(self) -> str:
        return f"{self.annee:04d}-{self.mois:02d}"

    def __str__(self) -> str:
        return f"Clôture stock {self.code_periode}"
