from __future__ import annotations

from django import forms

from .models import AdresseFournisseur, ArticleFournisseur, Fournisseur


class FournisseurForm(forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = ["nom"]
        widgets = {
            "nom": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nom du fournisseur",
                }
            ),
        }


class AdresseFournisseurForm(forms.ModelForm):
    class Meta:
        model = AdresseFournisseur
        fields = ["numero", "rue", "ville", "pays"]
        widgets = {
            "numero": forms.TextInput(attrs={"class": "form-control", "placeholder": "N°"}),
            "rue": forms.TextInput(attrs={"class": "form-control", "placeholder": "Rue"}),
            "ville": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ville"}),
            "pays": forms.TextInput(attrs={"class": "form-control", "placeholder": "Pays"}),
        }


class ArticleFournisseurForm(forms.ModelForm):
    class Meta:
        model = ArticleFournisseur
        fields = ["article"]
        widgets = {
            "article": forms.Select(attrs={"class": "form-select"}),
        }