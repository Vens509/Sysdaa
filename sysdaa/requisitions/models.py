from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from articles.models import _normaliser_libelle_unite


class Requisition(models.Model):
    ETAT_EN_ATTENTE = "En attente"
    ETAT_VALIDEE = "Validé"
    ETAT_REJETEE = "Rejeté"
    ETAT_TRAITEE = "Traité"
    ETAT_EN_ATTENTE_MODIF = "En attente de modification"

    ETATS = (
        (ETAT_EN_ATTENTE, ETAT_EN_ATTENTE),
        (ETAT_VALIDEE, ETAT_VALIDEE),
        (ETAT_REJETEE, ETAT_REJETEE),
        (ETAT_TRAITEE, ETAT_TRAITEE),
        (ETAT_EN_ATTENTE_MODIF, ETAT_EN_ATTENTE_MODIF),
    )

    date_preparation = models.DateTimeField(default=timezone.now)

    etat_requisition = models.CharField(
        max_length=30,
        choices=ETATS,
        default=ETAT_EN_ATTENTE,
    )

    motif_global = models.TextField(blank=True, default="")
    remarque = models.TextField(blank=True, default="")

    date_approbation = models.DateTimeField(null=True, blank=True)
    date_livraison = models.DateTimeField(null=True, blank=True)
    date_reception = models.DateTimeField(null=True, blank=True)

    soumetteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requisitions_soumises",
    )

    directeur_direction = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="requisitions_a_valider_direction",
    )

    transferee_vers_directeur_daa = models.BooleanField(default=False)
    date_transfert_directeur_daa = models.DateTimeField(null=True, blank=True)

    directeur_daa = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="requisitions_a_valider_daa",
    )

    sceau_directeur_daa = models.UUIDField(null=True, blank=True, unique=True)
    date_sceau_directeur_daa = models.DateTimeField(null=True, blank=True)

    demande_modification_motif = models.TextField(blank=True, default="")
    demande_modification_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="requisitions_modif_demandees",
    )
    date_demande_modification = models.DateTimeField(null=True, blank=True)

    traitee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="requisitions_traitees",
    )
    recue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="requisitions_recues",
    )

    class Meta:
        verbose_name = "Réquisition"
        verbose_name_plural = "Réquisitions"
        ordering = ("-date_preparation", "-id")
        indexes = [
            models.Index(fields=["etat_requisition", "date_preparation"]),
        ]

    @property
    def direction_demandeuse(self) -> str:
        u = getattr(self, "soumetteur", None)
        d = getattr(u, "direction_affectee", None) if u else None
        if not d:
            return ""
        return (getattr(d, "nom", "") or "").strip()

    def __str__(self) -> str:
        direction = self.direction_demandeuse or "-"
        return f"REQ-{self.id} | {direction} | {self.etat_requisition}"

    def clean(self):
        if self.etat_requisition not in dict(self.ETATS):
            raise ValidationError({"etat_requisition": "Etat de réquisition invalide."})

    def est_modifiable_par_secretaire(self) -> bool:
        return self.etat_requisition in (self.ETAT_EN_ATTENTE, self.ETAT_EN_ATTENTE_MODIF)

    def est_validable_par_directeur_direction(self) -> bool:
        return self.etat_requisition == self.ETAT_EN_ATTENTE

    def est_traitable_par_gestionnaire(self) -> bool:
        return self.etat_requisition == self.ETAT_VALIDEE

    def est_transferable_vers_daa(self) -> bool:
        return self.etat_requisition == self.ETAT_VALIDEE and not self.transferee_vers_directeur_daa

    def est_action_daa_possible(self) -> bool:
        return (
            bool(self.transferee_vers_directeur_daa)
            and self.directeur_daa_id is not None
            and self.etat_requisition not in (self.ETAT_TRAITEE, self.ETAT_REJETEE)
        )

    def reception_confirmee(self) -> bool:
        return self.date_reception is not None and self.recue_par_id is not None

    def peut_accuser_reception_par_secretaire(self, user) -> bool:
        return (
            user is not None
            and getattr(user, "is_authenticated", False)
            and self.soumetteur_id == user.id
            and self.etat_requisition == self.ETAT_TRAITEE
            and self.date_livraison is not None
            and self.date_reception is None
        )

    def generer_sceau_daa(self):
        if self.sceau_directeur_daa is None:
            self.sceau_directeur_daa = uuid.uuid4()
            self.date_sceau_directeur_daa = timezone.now()


class LigneRequisition(models.Model):
    requisition = models.ForeignKey(
        Requisition,
        on_delete=models.CASCADE,
        related_name="lignes",
    )
    article = models.ForeignKey(
        "articles.Article",
        on_delete=models.PROTECT,
        related_name="lignes_requisitions",
    )

    unite_demandee = models.CharField(
        max_length=60,
        default="Unité",
        help_text="Unité choisie par l’utilisateur pour cette ligne : Unité ou conditionnement principal.",
    )
    quantite_demandee = models.PositiveIntegerField()
    quantite_demandee_unites = models.PositiveIntegerField(default=0)

    unite_livree = models.CharField(
        max_length=60,
        blank=True,
        default="",
        help_text="Unité réellement utilisée lors de la livraison.",
    )
    quantite_livree = models.PositiveIntegerField(default=0)
    quantite_livree_unites = models.PositiveIntegerField(default=0)

    motif_article = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Ligne de réquisition"
        verbose_name_plural = "Lignes de réquisition"
        ordering = ("id",)

    def __str__(self) -> str:
        return (
            f"REQ-{self.requisition_id} | {self.article} | "
            f"demandée={self.quantite_demandee_affichage} "
            f"livrée={self.quantite_livree_affichage}"
        )

    @staticmethod
    def _pluraliser(libelle: str, quantite: int) -> str:
        libelle = (libelle or "").strip()
        if not libelle:
            return "unité" if quantite == 1 else "unités"
        if quantite == 1:
            return libelle
        if libelle.lower().endswith("s"):
            return libelle
        return f"{libelle}s"

    @property
    def quantite_demandee_affichage(self) -> str:
        q = int(self.quantite_demandee or 0)
        unite = self._pluraliser(self.unite_demandee or "Unité", q)
        return f"{q} {unite}"

    @property
    def quantite_livree_affichage(self) -> str:
        q = int(self.quantite_livree or 0)
        unite = self.unite_livree or self.unite_demandee or "Unité"
        unite = self._pluraliser(unite, q)
        return f"{q} {unite}"

    @property
    def quantite_demandee_unites_affichage(self) -> str:
        if not self.article_id:
            return f"{int(self.quantite_demandee_unites or 0)} unités"
        return self.article.formater_quantite_pour_affichage(int(self.quantite_demandee_unites or 0))

    @property
    def quantite_livree_unites_affichage(self) -> str:
        if not self.article_id:
            return f"{int(self.quantite_livree_unites or 0)} unités"
        return self.article.formater_quantite_pour_affichage(int(self.quantite_livree_unites or 0))

    def unites_autorisees(self) -> list[str]:
        if not self.article_id:
            return ["Unité"]

        article = self.article
        if getattr(article, "est_stocke_par_unite", False):
            return ["Unité"]

        return ["Unité", article.unite]

    def clean(self):
        qd = int(self.quantite_demandee or 0)
        ql = int(self.quantite_livree or 0)

        if self.article_id is None and qd not in (None, 0):
            raise ValidationError({"article": "Article obligatoire si une quantité est saisie."})

        if self.article_id is not None and qd <= 0:
            raise ValidationError({"quantite_demandee": "Quantité demandée obligatoire (>= 1)."})

        if ql < 0:
            raise ValidationError({"quantite_livree": "Quantité livrée invalide."})

        if qd < 0:
            raise ValidationError({"quantite_demandee": "Quantité demandée invalide."})

        if self.article_id is None:
            self.quantite_demandee_unites = 0
            self.quantite_livree_unites = 0
            return

        self.unite_demandee = _normaliser_libelle_unite(self.unite_demandee or "Unité")
        self.unite_livree = _normaliser_libelle_unite(self.unite_livree or "")

        article = self.article
        stock_actuel = int(article.stock_actuel or 0)

        if article.est_stocke_par_unite:
            self.unite_demandee = "Unité"
            self.quantite_demandee_unites = qd
        else:
            unites_autorisees = self.unites_autorisees()
            if self.unite_demandee not in unites_autorisees:
                raise ValidationError(
                    {
                        "unite_demandee": (
                            f"Unité demandée invalide. Valeurs autorisées : {', '.join(unites_autorisees)}."
                        )
                    }
                )

            try:
                self.quantite_demandee_unites = article.convertir_vers_unites_base(
                    self.quantite_demandee,
                    self.unite_demandee,
                )
            except ValidationError as exc:
                raise ValidationError({"unite_demandee": exc.messages[0]})

        if self.quantite_demandee_unites <= 0:
            raise ValidationError({"quantite_demandee": "Quantité demandée invalide."})

        if stock_actuel <= 0:
            raise ValidationError({"article": "Cet article est indisponible."})

        if self.quantite_demandee_unites > stock_actuel:
            raise ValidationError(
                {
                    "quantite_demandee": (
                        "La quantité demandée dépasse le stock disponible pour cet article."
                    )
                }
            )

        if ql == 0:
            self.unite_livree = self.unite_livree or ""
            self.quantite_livree_unites = 0
            return

        if article.est_stocke_par_unite:
            self.unite_livree = "Unité"
            self.quantite_livree_unites = ql
        else:
            unites_autorisees = self.unites_autorisees()
            unite_livree = self.unite_livree or self.unite_demandee or "Unité"

            if unite_livree not in unites_autorisees:
                raise ValidationError(
                    {
                        "unite_livree": (
                            f"Unité livrée invalide. Valeurs autorisées : {', '.join(unites_autorisees)}."
                        )
                    }
                )

            try:
                self.quantite_livree_unites = article.convertir_vers_unites_base(
                    self.quantite_livree,
                    unite_livree,
                )
            except ValidationError as exc:
                raise ValidationError({"unite_livree": exc.messages[0]})

        if self.quantite_livree_unites > self.quantite_demandee_unites:
            raise ValidationError(
                "La quantité livrée ne peut pas dépasser la quantité demandée."
            )