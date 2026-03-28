from __future__ import annotations

import re

from django import forms

from fournisseurs.models import Fournisseur
from .models import Article, Categorie, _normaliser_libelle_unite


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ["libelle"]
        widgets = {
            "libelle": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Libellé de la catégorie",
                }
            )
        }

    def clean_libelle(self) -> str:
        libelle = (self.cleaned_data.get("libelle") or "").strip()
        if not libelle:
            raise forms.ValidationError("Le libellé de la catégorie est obligatoire.")
        return libelle


class ArticleForm(forms.ModelForm):
    categorie = forms.ModelChoiceField(
        queryset=Categorie.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    categorie_libre = forms.CharField(
        required=False,
        label="Nouvelle catégorie",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Saisir une nouvelle catégorie",
            }
        ),
    )

    fournisseurs = forms.ModelMultipleChoiceField(
        queryset=Fournisseur.objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-select",
                "size": 6,
            }
        ),
    )

    fournisseurs_libres = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": (
                    "Saisir un ou plusieurs nouveaux fournisseurs "
                    "(1 par ligne, ou séparés par des virgules)"
                ),
            }
        ),
    )

    stock_minimal_saisi = forms.IntegerField(
        min_value=1,
        label="Seuil minimal d’alerte",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": 1,
                "step": 1,
                "placeholder": "Ex. 2",
            }
        ),
        help_text=(
            "Saisir un seuil strictement supérieur à zéro dans le même conditionnement principal."
        ),
    )

    class Meta:
        model = Article
        fields = [
            "nom",
            "unite",
            "quantite_par_conditionnement",
            "categorie",
        ]
        widgets = {
            "nom": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nom de l'article",
                }
            ),
            "unite": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex. Unité, Boîte, Douzaine, Paquet, Carton…",
                }
            ),
            "quantite_par_conditionnement": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "step": 1,
                    "placeholder": "Ex. 12 pour une douzaine, 20 pour une boîte de 20",
                }
            ),
        }
        labels = {
            "nom": "Nom de l’article",
            "unite": "Conditionnement principal",
            "quantite_par_conditionnement": "Nombre d’unités dans 1 conditionnement",
            "categorie": "Catégorie",
        }
        help_texts = {
            "unite": (
                "Conditionnement visible pour l’utilisateur. "
                "Ex. Unité, Boîte, Douzaine, Paquet, Carton."
            ),
            "quantite_par_conditionnement": (
                "Obligatoire si le conditionnement n’est pas « Unité ». "
                "Ex. Boîte de 20, carton de 24."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["categorie"].queryset = Categorie.objects.all().order_by("libelle")
        self.fields["fournisseurs"].queryset = Fournisseur.objects.all().order_by("nom")

        article_verrouille = bool(
            self.instance
            and self.instance.pk
            and (self.instance.a_historique_mouvements() or self.instance.a_historique_requisitions())
        )

        if self.instance and self.instance.pk:
            self.fields["fournisseurs"].initial = (
                self.instance.fournisseurs.all().order_by("nom")
            )

            qpc = int(self.instance.quantite_par_conditionnement or 1)
            stock_minimal_affichable = (
                self.instance.stock_minimal // qpc
                if qpc and self.instance.stock_minimal % qpc == 0
                else self.instance.stock_minimal
            )
            self.fields["stock_minimal_saisi"].initial = stock_minimal_affichable or 1
        else:
            self.fields["stock_minimal_saisi"].initial = 1

        if article_verrouille:
            self.fields["unite"].disabled = True
            self.fields["quantite_par_conditionnement"].disabled = True

            self.fields["unite"].help_text = (
                "Le conditionnement principal ne peut plus être modifié "
                "car cet article a déjà un historique."
            )
            self.fields["quantite_par_conditionnement"].help_text = (
                "La quantité par conditionnement ne peut plus être modifiée "
                "car cet article a déjà un historique."
            )

    @staticmethod
    def _split_fournisseurs(value: str) -> list[str]:
        if not value:
            return []

        morceaux = re.split(r"[\n,;]+", value)
        resultat: list[str] = []
        vus: set[str] = set()

        for item in morceaux:
            nom = (item or "").strip()
            if not nom:
                continue

            cle = nom.casefold()
            if cle in vus:
                continue

            vus.add(cle)
            resultat.append(nom)

        return resultat

    def _article_a_historique_sensible(self) -> bool:
        if not self.instance or not self.instance.pk:
            return False

        if self.instance.mouvements.exists():
            return True

        if self.instance.lignes_requisitions.exists():
            return True

        return False

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

    def clean_unite(self) -> str:
        unite = _normaliser_libelle_unite(self.cleaned_data.get("unite") or "")
        if not unite:
            raise forms.ValidationError("Veuillez renseigner le conditionnement principal.")
        return unite

    def clean_stock_minimal_saisi(self) -> int:
        valeur = self.cleaned_data.get("stock_minimal_saisi")
        if valeur is None:
            raise forms.ValidationError("Le seuil minimal est obligatoire.")
        if valeur <= 0:
            raise forms.ValidationError("Le seuil minimal doit être strictement supérieur à zéro.")
        return valeur

    def clean_quantite_par_conditionnement(self) -> int:
        valeur = self.cleaned_data.get("quantite_par_conditionnement")
        if valeur is None:
            return 1
        if valeur <= 0:
            raise forms.ValidationError(
                "La quantité par conditionnement doit être strictement supérieure à zéro."
            )
        return valeur

    def clean(self):
        cleaned_data = super().clean()

        categorie = cleaned_data.get("categorie")
        categorie_libre = (cleaned_data.get("categorie_libre") or "").strip()

        if not categorie and not categorie_libre:
            self.add_error(
                "categorie",
                "Veuillez choisir une catégorie existante ou en saisir une nouvelle.",
            )

        fournisseurs_libres = (cleaned_data.get("fournisseurs_libres") or "").strip()
        cleaned_data["fournisseurs_nouveaux"] = self._split_fournisseurs(fournisseurs_libres)

        historique_sensible = self._article_a_historique_sensible()

        if historique_sensible:
            unite = _normaliser_libelle_unite(self.instance.unite or "")
            qpc = int(self.instance.quantite_par_conditionnement or 1)
            stock_minimal_saisi = int(cleaned_data.get("stock_minimal_saisi") or 0)
            stock_minimal_unites = stock_minimal_saisi * qpc
            stock_initial_unites = int(self.instance.stock_initial or 0)
        else:
            unite = _normaliser_libelle_unite(cleaned_data.get("unite") or "")
            qpc_saisi = int(cleaned_data.get("quantite_par_conditionnement") or 0)
            stock_minimal_saisi = int(cleaned_data.get("stock_minimal_saisi") or 0)

            qpc_imposee = self._quantite_imposee_par_unite(unite)

            if qpc_imposee is not None:
                if qpc_saisi not in (0, qpc_imposee):
                    self.add_error(
                        "quantite_par_conditionnement",
                        (
                            f"Pour le conditionnement « {unite} », la quantité par conditionnement "
                            f"doit être exactement {qpc_imposee}."
                        ),
                    )
                qpc = qpc_imposee
            else:
                qpc = qpc_saisi

                if qpc <= 0:
                    self.add_error(
                        "quantite_par_conditionnement",
                        (
                            "Pour un article stocké autrement qu’à l’unité, veuillez préciser "
                            "combien d’unités contient ce conditionnement."
                        ),
                    )
                    qpc = 1

            stock_initial_unites = 0 if not self.instance or not self.instance.pk else int(self.instance.stock_initial or 0)
            stock_minimal_unites = stock_minimal_saisi * qpc

        cleaned_data["unite"] = unite
        cleaned_data["quantite_par_conditionnement"] = qpc
        cleaned_data["stock_initial"] = stock_initial_unites
        cleaned_data["stock_minimal"] = stock_minimal_unites

        return cleaned_data

    def save(self, commit: bool = True) -> Article:
        article = super().save(commit=False)

        article.unite = self.cleaned_data["unite"]
        article.unite_base = "Unité"
        article.quantite_par_conditionnement = self.cleaned_data["quantite_par_conditionnement"]
        article.stock_minimal = self.cleaned_data["stock_minimal"]

        if article.pk:
            article.stock_initial = int(article.stock_initial or 0)
        else:
            article.stock_initial = 0
            article.stock_actuel = 0

        if commit:
            article.full_clean()
            article.save()
            self.save_m2m()

        return article