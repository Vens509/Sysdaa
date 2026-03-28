from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from articles.models import Article, _normaliser_libelle_unite
from .models import LigneRequisition, Requisition


def _add_class(widget: forms.Widget, css: str) -> None:
    existing = (widget.attrs.get("class") or "").strip()
    widget.attrs["class"] = f"{existing} {css}".strip() if existing else css


def _bootstrapify_form_fields(form: forms.Form) -> None:
    for _, field in form.fields.items():
        w = field.widget
        if isinstance(w, forms.CheckboxInput):
            _add_class(w, "form-check-input")
        elif isinstance(w, (forms.Select, forms.SelectMultiple)):
            _add_class(w, "form-select")
        else:
            _add_class(w, "form-control")


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _article_est_disponible(article: Article) -> bool:
    return int(article.stock_actuel or 0) > 0


def _normaliser_categorie_filtre(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _choices_unites_pour_article(article: Article | None) -> list[tuple[str, str]]:
    if article is None:
        return [("Unité", "Unité")]

    unite_article = _normaliser_libelle_unite(article.unite)

    if article.est_stocke_par_unite or unite_article == "Unité":
        return [("Unité", "Unité")]

    return [
        ("Unité", "Unité"),
        (unite_article, unite_article),
    ]


def _build_article_meta(article: Article) -> dict:
    unite_article = _normaliser_libelle_unite(article.unite)
    categorie_libelle = getattr(article.categorie, "libelle", "") or ""
    unites_autorisees = ["Unité"]

    if not article.est_stocke_par_unite and unite_article != "Unité":
        unites_autorisees.append(unite_article)

    return {
        "id": article.pk,
        "nom": article.nom,
        "nom_normalise": " ".join((article.nom or "").strip().casefold().split()),
        "categorie": categorie_libelle,
        "categorie_key": _normaliser_categorie_filtre(categorie_libelle),
        "unite_principale": unite_article,
        "unite_base": article.unite_base,
        "quantite_par_conditionnement": int(article.quantite_par_conditionnement or 1),
        "stock_actuel_unites": int(article.stock_actuel or 0),
        "resume_conditionnement": article.resume_conditionnement,
        "libelle_conditionnement": article.libelle_conditionnement,
        "est_stocke_par_unite": bool(article.est_stocke_par_unite),
        "est_disponible": _article_est_disponible(article),
        "unites_autorisees": unites_autorisees,
    }


class RequisitionCreateForm(forms.ModelForm):
    class Meta:
        model = Requisition
        fields = ["motif_global"]
        widgets = {
            "motif_global": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["motif_global"].label = "Motif global"
        self.fields["motif_global"].required = True
        self.fields["motif_global"].widget.attrs.setdefault(
            "placeholder",
            "Décrivez le besoin...",
        )

        _bootstrapify_form_fields(self)

    def clean_motif_global(self) -> str:
        v = (self.cleaned_data.get("motif_global") or "").strip()
        if not v:
            raise ValidationError("Le motif global est obligatoire.")
        return v


class RequisitionUpdateForm(forms.ModelForm):
    class Meta:
        model = Requisition
        fields = ["motif_global", "remarque"]
        widgets = {
            "motif_global": forms.Textarea(attrs={"rows": 3}),
            "remarque": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["motif_global"].label = "Motif global"
        self.fields["remarque"].label = "Remarque (optionnel)"

        self.fields["motif_global"].required = True
        self.fields["motif_global"].widget.attrs.setdefault(
            "placeholder",
            "Décrivez le besoin...",
        )
        self.fields["remarque"].widget.attrs.setdefault(
            "placeholder",
            "Remarque...",
        )

        _bootstrapify_form_fields(self)

    def clean_motif_global(self) -> str:
        v = (self.cleaned_data.get("motif_global") or "").strip()
        if not v:
            raise ValidationError("Le motif global est obligatoire.")
        return v


class LigneRequisitionForm(forms.ModelForm):
    categorie_article = forms.ChoiceField(
        label="Catégorie",
        choices=[("", "Toutes catégories")],
        required=False,
        widget=forms.Select(),
    )

    unite_demandee = forms.ChoiceField(
        label="Conditionnement demandé",
        choices=[("Unité", "Unité")],
        widget=forms.Select(),
        required=False,
    )

    class Meta:
        model = LigneRequisition
        fields = ["article", "unite_demandee", "quantite_demandee", "motif_article"]
        widgets = {
            "motif_article": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        articles = list(Article.objects.select_related("categorie").order_by("nom"))

        self.fields["article"].queryset = Article.objects.filter(
            pk__in=[a.pk for a in articles]
        )

        self.fields["article"].label = "Article"
        self.fields["article"].empty_label = "Sélectionnez un article"
        self.fields["quantite_demandee"].label = "Quantité demandée"
        self.fields["motif_article"].label = "Motif (optionnel)"

        categories_uniques: list[str] = []
        categories_vues: set[str] = set()
        for a in articles:
            libelle = (getattr(a.categorie, "libelle", "") or "").strip()
            cle = _normaliser_categorie_filtre(libelle)
            if not libelle or not cle or cle in categories_vues:
                continue
            categories_vues.add(cle)
            categories_uniques.append(libelle)

        self.fields["categorie_article"].choices = [
            ("", "Toutes catégories"),
            *[(lib, lib) for lib in categories_uniques],
        ]

        article_meta_map = {str(a.pk): _build_article_meta(a) for a in articles}
        self.fields["article"].widget.attrs["data-article-meta-map"] = json.dumps(
            article_meta_map,
            ensure_ascii=False,
        )

        articles_disponibles = [a for a in articles if _article_est_disponible(a)]
        articles_indisponibles = [a for a in articles if not _article_est_disponible(a)]

        choices = [("", "Sélectionnez un article")]

        for a in articles_disponibles:
            label = f"{a.nom} — {a.libelle_conditionnement}"
            choices.append((a.pk, label))

        for a in articles_indisponibles:
            label = f"{a.nom} — {a.libelle_conditionnement} — Indisponible"
            choices.append((a.pk, label))

        self.fields["article"].choices = choices
        self.fields["article"].widget.attrs["data-search-placeholder"] = (
            "Rechercher un article..."
        )
        self.fields["article"].widget.attrs["data-empty-search-message"] = (
            "Aucun article trouvé pour cette saisie."
        )

        article_courant = None
        categorie_initiale = ""

        if self.is_bound:
            article_id = self.data.get(self.add_prefix("article"))
            categorie_postee = (
                self.data.get(self.add_prefix("categorie_article")) or ""
            ).strip()

            if article_id:
                try:
                    article_courant = Article.objects.select_related("categorie").get(pk=article_id)
                except Article.DoesNotExist:
                    article_courant = None

            if categorie_postee:
                categorie_initiale = categorie_postee
            elif article_courant and article_courant.categorie_id:
                categorie_initiale = getattr(article_courant.categorie, "libelle", "") or ""

        elif self.instance and self.instance.pk and self.instance.article_id:
            article_courant = self.instance.article
            categorie_initiale = getattr(article_courant.categorie, "libelle", "") or ""

        self.fields["categorie_article"].initial = categorie_initiale

        self.fields["unite_demandee"].choices = _choices_unites_pour_article(article_courant)
        self.fields["unite_demandee"].widget.attrs["data-default-value"] = (
            _normaliser_libelle_unite(self.instance.unite_demandee)
            if self.instance and self.instance.pk
            else "Unité"
        )

        self.fields["quantite_demandee"].min_value = 1
        self.fields["quantite_demandee"].widget = forms.NumberInput(
            attrs={
                "min": "1",
                "step": "1",
                "inputmode": "numeric",
                "placeholder": "Ex. 2",
            }
        )

        self.fields["motif_article"].widget.attrs.setdefault(
            "placeholder",
            "Précisez le besoin pour cet article...",
        )

        _bootstrapify_form_fields(self)

    def clean(self):
        cleaned = super().clean()

        article = cleaned.get("article")
        qd = cleaned.get("quantite_demandee")
        categorie_article = (cleaned.get("categorie_article") or "").strip()

        if article is not None and categorie_article:
            categorie_article_libelle = (getattr(article.categorie, "libelle", "") or "").strip()
            if _normaliser_categorie_filtre(categorie_article_libelle) != _normaliser_categorie_filtre(categorie_article):
                self.add_error(
                    "article",
                    "Cet article ne correspond pas à la catégorie choisie.",
                )
                return cleaned

        if article is None or _is_blank(qd):
            return cleaned

        try:
            qd_int = int(qd)
        except (TypeError, ValueError):
            raise ValidationError("Quantité invalide.")

        if qd_int <= 0:
            self.add_error("quantite_demandee", "La quantité doit être supérieure ou égale à 1.")
            return cleaned

        stock_actuel = int(article.stock_actuel or 0)
        if stock_actuel <= 0:
            self.add_error("article", "Cet article est indisponible.")
            return cleaned

        if article.est_stocke_par_unite:
            unite_demandee = "Unité"
            quantite_demandee_unites = qd_int
        else:
            unite_demandee = _normaliser_libelle_unite(cleaned.get("unite_demandee") or "Unité")
            unites_autorisees = [u[0] for u in _choices_unites_pour_article(article)]

            if unite_demandee not in unites_autorisees:
                self.add_error(
                    "unite_demandee",
                    f"Conditionnement invalide pour cet article. Valeurs autorisées : {', '.join(unites_autorisees)}.",
                )
                return cleaned

            try:
                quantite_demandee_unites = article.convertir_vers_unites_base(
                    qd_int,
                    unite_demandee,
                )
            except ValidationError as exc:
                self.add_error("unite_demandee", exc.messages[0])
                return cleaned

        if quantite_demandee_unites <= 0:
            self.add_error("quantite_demandee", "Quantité demandée invalide.")
            return cleaned

        if quantite_demandee_unites > stock_actuel:
            self.add_error(
                "quantite_demandee",
                "Il y a pas cette quantité en stock.",
            )
            return cleaned

        cleaned["unite_demandee"] = unite_demandee
        cleaned["quantite_demandee_unites"] = quantite_demandee_unites
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)

        article = self.cleaned_data.get("article")
        quantite_demandee = int(self.cleaned_data.get("quantite_demandee") or 0)

        if article and article.est_stocke_par_unite:
            unite_demandee = "Unité"
            quantite_demandee_unites = quantite_demandee
        else:
            unite_demandee = _normaliser_libelle_unite(
                self.cleaned_data.get("unite_demandee") or "Unité"
            )
            quantite_demandee_unites = int(
                self.cleaned_data.get("quantite_demandee_unites") or 0
            )

        obj.article = article
        obj.unite_demandee = unite_demandee
        obj.quantite_demandee = quantite_demandee
        obj.quantite_demandee_unites = quantite_demandee_unites

        if not obj.pk:
            obj.unite_livree = ""
            obj.quantite_livree = 0
            obj.quantite_livree_unites = 0

        if commit:
            obj.full_clean()
            obj.save()

        return obj


class BaseLigneRequisitionFormSet(BaseInlineFormSet):
    def _is_form_empty(self, form: forms.Form) -> bool:
        if not hasattr(form, "cleaned_data"):
            return False

        cd = form.cleaned_data or {}
        if cd.get("DELETE"):
            return False

        article = cd.get("article")
        unite_demandee = (cd.get("unite_demandee") or "").strip()
        qd = cd.get("quantite_demandee")
        motif = (cd.get("motif_article") or "").strip()

        return (article is None) and (unite_demandee == "") and _is_blank(qd) and (motif == "")

    def clean(self):
        super().clean()

        nb_valides = 0
        incoherences = False
        articles_vus: set[int] = set()

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            cd = form.cleaned_data or {}

            if cd.get("DELETE"):
                continue

            if self._is_form_empty(form):
                cd["DELETE"] = True
                continue

            article = cd.get("article")
            qd = cd.get("quantite_demandee")
            unite_demandee = (cd.get("unite_demandee") or "").strip()

            if article is None and (not _is_blank(qd) or unite_demandee):
                form.add_error("article", "Choisissez un article pour cette ligne.")
                incoherences = True
                continue

            if article is not None and _is_blank(qd):
                form.add_error("quantite_demandee", "Saisissez une quantité demandée (>= 1).")
                incoherences = True
                continue

            if article is not None:
                try:
                    qd_int = int(qd)
                except (TypeError, ValueError):
                    form.add_error("quantite_demandee", "Quantité invalide.")
                    incoherences = True
                    continue

                if qd_int <= 0:
                    form.add_error(
                        "quantite_demandee",
                        "La quantité doit être supérieure ou égale à 1.",
                    )
                    incoherences = True
                    continue

                stock_actuel = int(article.stock_actuel or 0)
                if stock_actuel <= 0:
                    form.add_error("article", "Cet article est indisponible.")
                    incoherences = True
                    continue

                if article.est_stocke_par_unite:
                    qd_unites = qd_int
                else:
                    if not unite_demandee:
                        form.add_error("unite_demandee", "Choisissez le conditionnement demandé.")
                        incoherences = True
                        continue
                    qd_unites = int(cd.get("quantite_demandee_unites") or 0)

                if qd_unites <= 0:
                    form.add_error("quantite_demandee", "Quantité demandée invalide.")
                    incoherences = True
                    continue

                if qd_unites > stock_actuel:
                    form.add_error(
                        "quantite_demandee",
                        "Il y a pas cette quantité en stock.",
                    )
                    incoherences = True
                    continue

                if getattr(article, "pk", None) is not None:
                    if article.pk in articles_vus:
                        form.add_error(
                            "article",
                            "Cet article est déjà présent dans la réquisition.",
                        )
                        incoherences = True
                        continue
                    articles_vus.add(article.pk)

                nb_valides += 1

        if nb_valides == 0:
            raise ValidationError(
                "Ajoutez au moins un article disponible avec une quantité valide."
            )

        if incoherences:
            raise ValidationError(
                "Certaines lignes sont incomplètes, invalides ou indisponibles."
            )


LigneRequisitionCreateFormSet = inlineformset_factory(
    Requisition,
    LigneRequisition,
    form=LigneRequisitionForm,
    formset=BaseLigneRequisitionFormSet,
    extra=1,
    can_delete=True,
)

LigneRequisitionUpdateFormSet = inlineformset_factory(
    Requisition,
    LigneRequisition,
    form=LigneRequisitionForm,
    formset=BaseLigneRequisitionFormSet,
    extra=0,
    can_delete=True,
)

LigneRequisitionFormSet = LigneRequisitionCreateFormSet