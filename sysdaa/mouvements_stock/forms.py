from __future__ import annotations

from django import forms

from articles.models import Article


CONDITIONNEMENTS_STANDARDS = [
    "Unité",
    "Boîte",
    "Paquet",
    "Carton",
    "Caisse",
    "Ramette",
    "Rame",
    "Douzaine",
    "Sac",
    "Bidon",
    "Bouteille",
    "Flacon",
    "Lot",
]

MOTIFS_SORTIE_CHOICES = [
    ("", "Sélectionnez un motif"),
    ("Périmé", "Périmé"),
    ("Endommagé", "Endommagé"),
    ("Sorti pour un travail", "Sorti pour un travail"),
    ("Perdu", "Perdu"),
    ("Cassé", "Cassé"),
    ("Volé", "Volé"),
    ("Don", "Don"),
    ("Transfert interne", "Transfert interne"),
    ("Autres", "Autres"),
]


def _add_class(widget: forms.Widget, css: str) -> None:
    existing = (widget.attrs.get("class") or "").strip()
    widget.attrs["class"] = f"{existing} {css}".strip() if existing else css


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


class ArticleSelectWidget(forms.Select):
    def __init__(self, *args, disable_out_of_stock=False, **kwargs):
        self.disable_out_of_stock = disable_out_of_stock
        super().__init__(*args, **kwargs)

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name=name,
            value=value,
            label=label,
            selected=selected,
            index=index,
            subindex=subindex,
            attrs=attrs,
        )

        raw_value = getattr(value, "value", value)

        if raw_value not in (None, "", 0, "0"):
            try:
                article = self.choices.queryset.get(pk=raw_value)
            except Exception:
                article = None

            if article is not None:
                stock_unites = int(article.stock_actuel or 0)

                option["attrs"]["data-article-unite"] = (
                    _normalize_text(article.unite) or "Unité"
                )
                option["attrs"]["data-article-qpc"] = str(
                    int(article.quantite_par_conditionnement or 1)
                )
                option["attrs"]["data-stock-unites"] = str(stock_unites)
                option["attrs"]["data-stock-affichage"] = article.stock_actuel_affichage
                option["attrs"]["data-stock-rupture"] = "1" if stock_unites <= 0 else "0"

                if stock_unites <= 0 and self.disable_out_of_stock:
                    option["attrs"]["disabled"] = True
                    option["attrs"]["class"] = (
                        f'{option["attrs"].get("class", "")} option-indisponible'.strip()
                    )
                    option["label"] = f"{article.nom} — Indisponible (rupture de stock)"

        return option


class ArticleChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: Article) -> str:
        return obj.nom


class BaseMouvementStockForm(forms.Form):
    article = ArticleChoiceField(
        queryset=Article.objects.select_related("categorie").order_by("nom"),
        label="Article",
        widget=ArticleSelectWidget(),
    )

    quantite = forms.IntegerField(
        min_value=1,
        label="Quantité",
    )

    conditionnement_operation = forms.ChoiceField(
        label="Conditionnement utilisé",
        choices=[("", "Sélectionnez un conditionnement")],
    )

    conditionnement_operation_libre = forms.CharField(
        required=False,
        label="Autre conditionnement",
    )

    quantite_par_conditionnement_operation = forms.IntegerField(
        min_value=1,
        required=False,
        label="Nombre d’unités dans 1 conditionnement utilisé",
    )

    autoriser_conditionnement_libre = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["article"].empty_label = "Sélectionnez un article"
        self.fields["article"].widget.disable_out_of_stock = isinstance(self, SortieStockForm)

        self.fields["quantite"].widget.attrs.update(
            {
                "min": 1,
                "step": 1,
                "inputmode": "numeric",
                "placeholder": "Ex. 5",
            }
        )

        self.fields["conditionnement_operation_libre"].widget.attrs.update(
            {
                "placeholder": "Ex. Sachet, Tube, Fardeau...",
            }
        )

        self.fields["quantite_par_conditionnement_operation"].widget.attrs.update(
            {
                "min": 1,
                "step": 1,
                "inputmode": "numeric",
                "placeholder": "Ex. 12",
            }
        )

        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                _add_class(field.widget, "form-select")
            else:
                _add_class(field.widget, "form-control")

        article = None
        article_id = None

        if self.is_bound:
            article_id = self.data.get(self.add_prefix("article")) or self.data.get("article")
        elif self.initial:
            article_id = self.initial.get("article")

        if article_id:
            try:
                article = Article.objects.get(pk=article_id)
            except (Article.DoesNotExist, ValueError, TypeError):
                article = None

        self._configure_conditionnement_choices(article)

    def _configure_conditionnement_choices(self, article: Article | None) -> None:
        choices: list[tuple[str, str]] = [("", "Sélectionnez un conditionnement")]

        if self.autoriser_conditionnement_libre:
            for conditionnement in CONDITIONNEMENTS_STANDARDS:
                choices.append((conditionnement, conditionnement))

            if article is not None:
                unite_article = _normalize_text(article.unite)
                if unite_article and unite_article not in CONDITIONNEMENTS_STANDARDS:
                    choices.append((unite_article, unite_article))

            choices.append(("AUTRE", "Autres"))
        else:
            choices.append(("Unité", "Unité"))

            if article is not None:
                unite_article = _normalize_text(article.unite) or "Unité"
                if unite_article != "Unité":
                    choices.append((unite_article, unite_article))

        self.fields["conditionnement_operation"].choices = choices

    def _resolve_conditionnement(self, article: Article) -> tuple[str, int]:
        conditionnement = _normalize_text(
            self.cleaned_data.get("conditionnement_operation")
        )
        conditionnement_libre = _normalize_text(
            self.cleaned_data.get("conditionnement_operation_libre")
        )
        qpc_saisi = int(self.cleaned_data.get("quantite_par_conditionnement_operation") or 0)

        unite_article = _normalize_text(article.unite) or "Unité"
        qpc_article = int(article.quantite_par_conditionnement or 1)

        if conditionnement == "Unité":
            return "Unité", 1

        if conditionnement == unite_article:
            return unite_article, qpc_article

        if self.autoriser_conditionnement_libre and conditionnement == "AUTRE":
            if not conditionnement_libre:
                raise forms.ValidationError(
                    {
                        "conditionnement_operation_libre": (
                            "Veuillez préciser le nouveau conditionnement."
                        )
                    }
                )

            if qpc_saisi <= 0:
                raise forms.ValidationError(
                    {
                        "quantite_par_conditionnement_operation": (
                            "Veuillez indiquer combien d’unités contient ce conditionnement."
                        )
                    }
                )

            return conditionnement_libre, qpc_saisi

        if self.autoriser_conditionnement_libre and conditionnement in CONDITIONNEMENTS_STANDARDS:
            if qpc_saisi <= 0:
                raise forms.ValidationError(
                    {
                        "quantite_par_conditionnement_operation": (
                            "Veuillez indiquer combien d’unités contient ce conditionnement."
                        )
                    }
                )

            return conditionnement, qpc_saisi

        raise forms.ValidationError(
            {
                "conditionnement_operation": "Veuillez choisir un conditionnement valide."
            }
        )

    def clean_quantite(self):
        quantite = int(self.cleaned_data.get("quantite") or 0)
        if quantite <= 0:
            raise forms.ValidationError("La quantité doit être supérieure à 0.")
        return quantite

    def clean_article(self):
        article = self.cleaned_data.get("article")
        if article is None:
            return article

        if int(article.stock_actuel or 0) <= 0 and isinstance(self, SortieStockForm):
            raise forms.ValidationError(
                "Cet article est indisponible car il est en rupture de stock."
            )
        return article


class EntreeStockForm(BaseMouvementStockForm):
    autoriser_conditionnement_libre = True

    quantite = forms.IntegerField(
        min_value=1,
        label="Quantité à ajouter",
    )

    def clean(self):
        cleaned_data = super().clean()

        article = cleaned_data.get("article")
        quantite = cleaned_data.get("quantite")

        if article is None or quantite in (None, ""):
            return cleaned_data

        try:
            conditionnement, qpc = self._resolve_conditionnement(article)
        except forms.ValidationError as exc:
            self.add_error(None, exc)
            return cleaned_data

        cleaned_data["conditionnement_mouvement"] = conditionnement
        cleaned_data["quantite_par_conditionnement_mouvement"] = int(qpc)
        cleaned_data["quantite_unites"] = int(quantite) * int(qpc)

        return cleaned_data


class SortieStockForm(BaseMouvementStockForm):
    autoriser_conditionnement_libre = False

    quantite = forms.IntegerField(
        min_value=1,
        label="Quantité à sortir",
    )

    motif_sortie_selection = forms.ChoiceField(
        label="Motif de la sortie",
        choices=MOTIFS_SORTIE_CHOICES,
    )

    motif_sortie_autre = forms.CharField(
        required=False,
        label="Précisez le motif",
        widget=forms.Textarea(attrs={"rows": 3}),
        max_length=255,
    )

    motif_sortie = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["motif_sortie_autre"].widget.attrs.setdefault(
            "placeholder",
            "Précisez le motif de cette sortie...",
        )

    def clean(self):
        cleaned_data = super().clean()

        article = cleaned_data.get("article")
        quantite = cleaned_data.get("quantite")
        motif_selection = _normalize_text(cleaned_data.get("motif_sortie_selection"))
        motif_autre = _normalize_text(cleaned_data.get("motif_sortie_autre"))

        if not motif_selection:
            self.add_error("motif_sortie_selection", "Veuillez choisir un motif.")
        elif motif_selection == "Autres":
            if not motif_autre:
                self.add_error("motif_sortie_autre", "Veuillez préciser le motif.")
            else:
                cleaned_data["motif_sortie"] = motif_autre
        else:
            cleaned_data["motif_sortie"] = motif_selection

        if article is None or quantite in (None, ""):
            return cleaned_data

        try:
            conditionnement, qpc = self._resolve_conditionnement(article)
        except forms.ValidationError as exc:
            self.add_error(None, exc)
            return cleaned_data

        quantite_unites = int(quantite) * int(qpc)
        stock_actuel = int(article.stock_actuel or 0)

        if stock_actuel <= 0:
            self.add_error("article", "Cet article est indisponible.")
            return cleaned_data

        if quantite_unites > stock_actuel:
            self.add_error(
                "quantite",
                (
                    "Il n’y a pas cette quantité disponible. "
                    f"Disponibilité actuelle : {article.stock_actuel_affichage}."
                ),
            )

        cleaned_data["conditionnement_mouvement"] = conditionnement
        cleaned_data["quantite_par_conditionnement_mouvement"] = int(qpc)
        cleaned_data["quantite_unites"] = int(quantite_unites)

        return cleaned_data
