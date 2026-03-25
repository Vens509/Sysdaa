from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


UNITE_UNITAIRE_EQUIVALENTS = {
    "u",
    "unite",
    "unité",
    "piece",
    "pièce",
    "article",
}

DOUZAINE_EQUIVALENTS = {
    "douzaine",
    "dz",
    "dozen",
}


def _normaliser_libelle_unite(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""

    value_min = value.casefold()

    if value_min in UNITE_UNITAIRE_EQUIVALENTS:
        return "Unité"

    if value_min in DOUZAINE_EQUIVALENTS:
        return "Douzaine"

    return value[:1].upper() + value[1:]


class Categorie(models.Model):
    libelle = models.CharField(max_length=120, unique=True)

    class Meta:
        db_table = "categories"
        ordering = ("libelle",)
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    def __str__(self) -> str:
        return self.libelle


class Article(models.Model):
    nom = models.CharField(
        max_length=180,
        help_text="Nom unique de l’article.",
    )

    unite = models.CharField(
        max_length=60,
        help_text="Conditionnement principal visible par l’utilisateur : Unité, Boîte, Douzaine, Paquet, Carton…",
    )

    unite_base = models.CharField(
        max_length=30,
        default="Unité",
        help_text="Unité réelle de calcul du stock. Pour cette première version, elle reste Unité.",
    )

    quantite_par_conditionnement = models.PositiveIntegerField(
        default=1,
        help_text="Nombre d’unités réelles contenues dans 1 conditionnement.",
    )

    stock_initial = models.PositiveIntegerField(default=0)
    stock_actuel = models.PositiveIntegerField(default=0)
    stock_minimal = models.PositiveIntegerField(default=0)

    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.PROTECT,
        related_name="articles",
    )

    utilisateur_enregistreur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="articles_enregistres",
    )

    date_creation = models.DateTimeField(default=timezone.now)
    date_modification = models.DateTimeField(auto_now=True)

    fournisseurs = models.ManyToManyField(
        "fournisseurs.Fournisseur",
        through="fournisseurs.ArticleFournisseur",
        related_name="articles",
        blank=True,
    )

    class Meta:
        db_table = "articles"
        ordering = ("nom",)
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        indexes = [
            models.Index(fields=["nom"]),
            models.Index(fields=["categorie"]),
            models.Index(fields=["unite"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stock_initial__gte=0),
                name="ck_article_stock_initial_ge_0",
            ),
            models.CheckConstraint(
                condition=models.Q(stock_actuel__gte=0),
                name="ck_article_stock_actuel_ge_0",
            ),
            models.CheckConstraint(
                condition=models.Q(stock_minimal__gte=0),
                name="ck_article_stock_minimal_ge_0",
            ),
            models.CheckConstraint(
                condition=models.Q(quantite_par_conditionnement__gte=1),
                name="ck_article_qte_par_conditionnement_ge_1",
            ),
            models.UniqueConstraint(
                Lower("nom"),
                name="uq_article_nom_lower",
            ),
        ]

    def __str__(self) -> str:
        if self.est_stocke_par_unite:
            return f"{self.nom} ({self.unite})"
        return f"{self.nom} ({self.unite} de {self.quantite_par_conditionnement})"

    @property
    def est_stocke_par_unite(self) -> bool:
        return self.quantite_par_conditionnement == 1

    @property
    def en_alerte(self) -> bool:
        return self.stock_actuel <= self.stock_minimal

    @property
    def est_en_rupture(self) -> bool:
        return self.stock_actuel == 0

    @property
    def libelle_conditionnement(self) -> str:
        if self.est_stocke_par_unite:
            return "Unité"
        return f"{self.unite} ({self.quantite_par_conditionnement} unités)"

    @property
    def resume_conditionnement(self) -> str:
        if self.est_stocke_par_unite:
            return "Stock géré directement à l’unité."
        return f"1 {self.unite.casefold()} = {self.quantite_par_conditionnement} unités."

    def quantite_conditionnements_depuis_unites(self, quantite_unites: int) -> tuple[int, int]:
        quantite_unites = int(quantite_unites or 0)
        qpc = int(self.quantite_par_conditionnement or 1)
        return divmod(quantite_unites, qpc)

    def formater_quantite_pour_affichage(self, quantite_unites: int) -> str:
        quantite_unites = int(quantite_unites or 0)

        if self.est_stocke_par_unite:
            suffixe = "unité" if quantite_unites == 1 else "unités"
            return f"{quantite_unites} {suffixe}"

        nb_conditionnements, reste = self.quantite_conditionnements_depuis_unites(quantite_unites)

        parts: list[str] = []
        if nb_conditionnements:
            libelle_cond = self.unite if nb_conditionnements == 1 else f"{self.unite}s"
            parts.append(f"{nb_conditionnements} {libelle_cond}")

        if reste:
            libelle_reste = "unité" if reste == 1 else "unités"
            parts.append(f"{reste} {libelle_reste}")

        if not parts:
            return "0 unité"

        return " et ".join(parts)

    @property
    def stock_initial_affichage(self) -> str:
        return self.formater_quantite_pour_affichage(self.stock_initial)

    @property
    def stock_actuel_affichage(self) -> str:
        return self.formater_quantite_pour_affichage(self.stock_actuel)

    @property
    def stock_minimal_affichage(self) -> str:
        return self.formater_quantite_pour_affichage(self.stock_minimal)

    def convertir_vers_unites_base(self, quantite: int, unite_saisie: str | None = None) -> int:
        quantite = int(quantite or 0)
        unite_saisie = _normaliser_libelle_unite(unite_saisie or "")

        if not unite_saisie or unite_saisie == "Unité":
            return quantite

        if unite_saisie == _normaliser_libelle_unite(self.unite):
            return quantite * int(self.quantite_par_conditionnement or 1)

        raise ValidationError(
            {
                "unite": (
                    f"Unité de saisie invalide pour cet article. "
                    f"Valeurs attendues : Unité ou {self.unite}."
                )
            }
        )

    def a_historique_mouvements(self) -> bool:
        if not self.pk:
            return False
        return self.mouvements.exists()

    def a_historique_requisitions(self) -> bool:
        if not self.pk:
            return False
        return self.lignes_requisitions.exists()

    def stock_initial_est_verrouille(self) -> bool:
        if not self.pk:
            return False
        return self.a_historique_mouvements() or self.a_historique_requisitions()

    @staticmethod
    def _quantite_imposee_par_unite(unite: str) -> int | None:
        unite_normalisee = _normaliser_libelle_unite(unite or "")
        mapping = {
            "Unité": 1,
            "Bidon": 1,
            "Bouteille": 1,
            "Douzaine": 12,
        }
        return mapping.get(unite_normalisee)

    def clean(self):
        self.nom = " ".join((self.nom or "").strip().split())
        self.unite = _normaliser_libelle_unite(self.unite)
        self.unite_base = _normaliser_libelle_unite(self.unite_base or "Unité")

        erreurs: dict[str, str] = {}

        if not self.nom:
            erreurs["nom"] = "Le nom de l’article est obligatoire."

        if not self.unite:
            erreurs["unite"] = "Veuillez renseigner l’unité ou le conditionnement principal."

        if self.unite_base != "Unité":
            erreurs["unite_base"] = "Dans cette version, l’unité de base doit rester « Unité »."

        doublon_qs = Article.objects.filter(nom__iexact=self.nom)
        if self.pk:
            doublon_qs = doublon_qs.exclude(pk=self.pk)
        if doublon_qs.exists():
            erreurs["nom"] = "Un article portant ce nom existe déjà."

        qpc_imposee = self._quantite_imposee_par_unite(self.unite)

        if qpc_imposee is not None:
            self.quantite_par_conditionnement = qpc_imposee
        else:
            if int(self.quantite_par_conditionnement or 0) <= 0:
                erreurs["quantite_par_conditionnement"] = (
                    "Pour un article stocké autrement qu’à l’unité, "
                    "veuillez préciser combien d’unités contient ce conditionnement."
                )

        if self.pk:
            ancien = (
                Article.objects.filter(pk=self.pk)
                .only("stock_initial", "unite", "quantite_par_conditionnement")
                .first()
            )

            if ancien is not None and self.stock_initial_est_verrouille():
                if int(self.stock_initial) != int(ancien.stock_initial):
                    erreurs["stock_initial"] = (
                        "Le stock initial ne peut plus être modifié "
                        "car cet article a déjà un historique de mouvements ou de réquisitions."
                    )

            if ancien is not None and self.stock_initial_est_verrouille():
                if self.unite != ancien.unite:
                    erreurs["unite"] = (
                        "Le conditionnement principal ne peut plus être modifié "
                        "car cet article a déjà un historique de mouvements ou de réquisitions."
                    )

                if int(self.quantite_par_conditionnement or 0) != int(ancien.quantite_par_conditionnement or 0):
                    erreurs["quantite_par_conditionnement"] = (
                        "La quantité par conditionnement ne peut plus être modifiée "
                        "car cet article a déjà un historique de mouvements ou de réquisitions."
                    )

        if erreurs:
            raise ValidationError(erreurs)

    def save(self, *args, **kwargs):
        self.nom = " ".join((self.nom or "").strip().split())
        self.unite = _normaliser_libelle_unite(self.unite)
        self.unite_base = _normaliser_libelle_unite(self.unite_base or "Unité")

        qpc_imposee = self._quantite_imposee_par_unite(self.unite)
        if qpc_imposee is not None:
            self.quantite_par_conditionnement = qpc_imposee

        if self.pk is None:
            self.stock_actuel = self.stock_initial

        super().save(*args, **kwargs)