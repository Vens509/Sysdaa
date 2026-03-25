from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class MouvementStock(models.Model):
    class TypeMouvement(models.TextChoices):
        ENTREE = "ENTREE", "Entrée"
        SORTIE = "SORTIE", "Sortie"

    article = models.ForeignKey(
        "articles.Article",
        on_delete=models.PROTECT,
        related_name="mouvements",
    )

    requisition = models.ForeignKey(
        "requisitions.Requisition",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mouvements_stock",
        help_text="Optionnel. Utilisé surtout pour les sorties liées au traitement d'une réquisition.",
    )

    motif_sortie = models.TextField(
        blank=True,
        default="",
        help_text="Motif libre pour une sortie manuelle hors réquisition.",
    )

    quantite = models.PositiveIntegerField(
        help_text="Quantité saisie dans le conditionnement choisi pour l’opération."
    )

    conditionnement_mouvement = models.CharField(
        max_length=60,
        default="Unité",
        blank=True,
        help_text="Conditionnement utilisé pour cette opération : Unité, Boîte, Paquet, etc.",
    )

    quantite_par_conditionnement_mouvement = models.PositiveIntegerField(
        default=1,
        help_text="Nombre d’unités réelles contenues dans 1 conditionnement de l’opération.",
    )

    quantite_unites = models.PositiveIntegerField(
        default=1,
        help_text="Équivalent réel de l’opération en unités de base.",
    )

    type_mouvement = models.CharField(max_length=10, choices=TypeMouvement.choices)
    date_mouvement = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ["-date_mouvement", "-id"]
        indexes = [
            models.Index(fields=["type_mouvement", "date_mouvement"]),
            models.Index(fields=["article", "date_mouvement"]),
            models.Index(fields=["conditionnement_mouvement"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantite__gte=1),
                name="ck_mvt_stock_quantite_ge_1",
            ),
            models.CheckConstraint(
                condition=models.Q(quantite_par_conditionnement_mouvement__gte=1),
                name="ck_mvt_stock_qpc_mvt_ge_1",
            ),
            models.CheckConstraint(
                condition=models.Q(quantite_unites__gte=1),
                name="ck_mvt_stock_quantite_unites_ge_1",
            ),
        ]

    def __str__(self) -> str:
        origine = (
            f"REQ-{self.requisition_id}"
            if self.requisition_id
            else (self.motif_sortie[:40] if self.motif_sortie else "Sans motif")
        )
        return (
            f"{self.get_type_mouvement_display()} | "
            f"{self.article} | "
            f"{self.quantite_affichage} | "
            f"eq={self.quantite_unites} unités | "
            f"{origine} | "
            f"{self.date_mouvement:%Y-%m-%d %H:%M}"
        )

    @property
    def est_sortie_manuelle(self) -> bool:
        return (
            self.type_mouvement == self.TypeMouvement.SORTIE
            and self.requisition_id is None
        )

    @property
    def est_sortie_requisition(self) -> bool:
        return (
            self.type_mouvement == self.TypeMouvement.SORTIE
            and self.requisition_id is not None
        )

    @property
    def conditionnement_operation_normalise(self) -> str:
        return (self.conditionnement_mouvement or "Unité").strip() or "Unité"

    @property
    def quantite_affichage(self) -> str:
        unite = self.conditionnement_operation_normalise
        suffixe = unite if int(self.quantite or 0) == 1 else f"{unite}s"
        return f"{self.quantite} {suffixe}"

    @property
    def equivalent_unites_affichage(self) -> str:
        qte = int(self.quantite_unites or 0)
        suffixe = "unité" if qte == 1 else "unités"
        return f"{qte} {suffixe}"

    @property
    def resume_operation(self) -> str:
        if self.conditionnement_operation_normalise.casefold() in {"unité", "unite"}:
            return self.equivalent_unites_affichage
        return (
            f"{self.quantite_affichage} "
            f"(1 {self.conditionnement_operation_normalise.casefold()} = "
            f"{self.quantite_par_conditionnement_mouvement} unités)"
        )

    def clean(self):
        super().clean()

        erreurs: dict[str, str] = {}

        self.motif_sortie = (self.motif_sortie or "").strip()
        self.conditionnement_mouvement = (
            (self.conditionnement_mouvement or "").strip() or "Unité"
        )

        quantite = int(self.quantite or 0)
        qpc_mvt = int(self.quantite_par_conditionnement_mouvement or 0)
        quantite_unites = int(self.quantite_unites or 0)

        if quantite <= 0:
            erreurs["quantite"] = "La quantité doit être supérieure à 0."

        if qpc_mvt <= 0:
            erreurs["quantite_par_conditionnement_mouvement"] = (
                "La quantité par conditionnement de l’opération doit être supérieure à 0."
            )

        if not self.conditionnement_mouvement:
            erreurs["conditionnement_mouvement"] = (
                "Le conditionnement de l’opération est obligatoire."
            )

        quantite_unites_calculee = quantite * qpc_mvt
        if quantite_unites <= 0:
            self.quantite_unites = quantite_unites_calculee
            quantite_unites = self.quantite_unites

        if quantite_unites != quantite_unites_calculee:
            erreurs["quantite_unites"] = (
                "L’équivalent réel en unités est incohérent avec la quantité et le conditionnement saisis."
            )

        if self.type_mouvement == self.TypeMouvement.ENTREE:
            if self.requisition_id is not None:
                erreurs["requisition"] = (
                    "Une entrée de stock ne peut pas être liée à une réquisition."
                )
            if self.motif_sortie:
                erreurs["motif_sortie"] = (
                    "Le motif de sortie ne s'applique pas à une entrée de stock."
                )

        elif self.type_mouvement == self.TypeMouvement.SORTIE:
            if self.requisition_id is None and not self.motif_sortie:
                erreurs["motif_sortie"] = (
                    "Le motif est obligatoire pour une sortie manuelle hors réquisition."
                )

            if self.requisition_id is not None and self.motif_sortie:
                erreurs["motif_sortie"] = (
                    "Le motif manuel ne doit pas être renseigné pour une sortie issue d'une réquisition."
                )

        if erreurs:
            raise ValidationError(erreurs)