from __future__ import annotations

from django import forms
from django.utils import timezone

from articles.models import Categorie
from configurations.models import ConfigurationSysteme
from requisitions.models import Requisition
from utilisateurs.models import Direction


MOIS_CHOICES = (
    (1, "Janvier"),
    (2, "Février"),
    (3, "Mars"),
    (4, "Avril"),
    (5, "Mai"),
    (6, "Juin"),
    (7, "Juillet"),
    (8, "Août"),
    (9, "Septembre"),
    (10, "Octobre"),
    (11, "Novembre"),
    (12, "Décembre"),
)

PERIODE_CHOICES = (
    ("MENSUEL", "Mensuel"),
    ("ANNUEL", "Annuel"),
)

TYPE_RAPPORT_CHOICES = (
    ("", "Choisir"),
    ("stock_global", "Stock / Synthèse d'activité"),
    ("categorie_article", "Demandes par catégorie d'article"),
    ("direction", "Demandes par direction"),
    ("direction_plus_demandeuse", "Direction la plus demandeuse"),
    ("direction_moins_demandeuse", "Direction la moins demandeuse"),
    ("article_plus_demande", "Article le plus demandé"),
    ("article_moins_demande", "Article le moins demandé"),
)


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


def _etat_choices() -> tuple[tuple[str, str], ...]:
    try:
        field = Requisition._meta.get_field("etat_requisition")
        return (("", "Choisir"),) + tuple(field.choices or ())
    except Exception:
        return (("", "Choisir"),)


def _resolve_rapport_label(periode: str, type_rapport: str) -> str:
    if periode == "ANNUEL" and type_rapport == "stock_global":
        return "Synthèse annuelle d'activité"
    if periode == "MENSUEL" and type_rapport == "stock_global":
        return "État global du stock"
    if type_rapport == "categorie_article":
        return "Demandes par catégorie d'article"
    if type_rapport == "direction":
        return "Demandes par direction"
    if type_rapport == "direction_plus_demandeuse":
        return "Direction la plus demandeuse"
    if type_rapport == "direction_moins_demandeuse":
        return "Direction la moins demandeuse"
    if type_rapport == "article_plus_demande":
        return "Article le plus demandé"
    if type_rapport == "article_moins_demande":
        return "Article le moins demandé"
    return "Rapport analytique"


class RapportGenerationForm(forms.Form):
    annee_fiscale = forms.ChoiceField(
        label="Année fiscale",
        choices=(),
    )
    mois = forms.ChoiceField(
        label="Mois",
        choices=MOIS_CHOICES,
        required=False,
    )
    type_rapport = forms.ChoiceField(
        label="Type de rapport",
        choices=TYPE_RAPPORT_CHOICES,
        required=False,
    )
    periode = forms.ChoiceField(
        label="Période",
        choices=PERIODE_CHOICES,
        initial="MENSUEL",
    )
    categorie = forms.ModelChoiceField(
        label="Catégorie d'article",
        queryset=Categorie.objects.none(),
        required=False,
        empty_label="Choisir",
    )
    direction = forms.ModelChoiceField(
        label="Direction",
        queryset=Direction.objects.none(),
        required=False,
        empty_label="Choisir",
    )
    etat_requisition = forms.ChoiceField(
        label="État de réquisition",
        choices=_etat_choices(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        configs = list(ConfigurationSysteme.objects.order_by("-annee_debut", "-id"))
        self.fields["annee_fiscale"].choices = [(str(cfg.pk), cfg.code) for cfg in configs]

        active_cfg = (
            ConfigurationSysteme.objects.filter(est_active=True)
            .order_by("-annee_debut", "-id")
            .first()
        )
        if active_cfg:
            self.fields["annee_fiscale"].initial = str(active_cfg.pk)
        elif self.fields["annee_fiscale"].choices:
            self.fields["annee_fiscale"].initial = self.fields["annee_fiscale"].choices[0][0]

        self.fields["categorie"].queryset = Categorie.objects.order_by("libelle")
        self.fields["direction"].queryset = Direction.objects.order_by("nom")
        self.fields["etat_requisition"].choices = _etat_choices()

        mois_courant = timezone.localdate().month
        if "mois" not in self.initial:
            self.fields["mois"].initial = mois_courant

        self.fields["type_rapport"].initial = ""
        self.fields["categorie"].initial = None
        self.fields["direction"].initial = None
        self.fields["etat_requisition"].initial = ""

        self.fields["annee_fiscale"].widget.attrs.update(
            {
                "data-role": "annee-fiscale",
            }
        )
        self.fields["mois"].widget.attrs.update(
            {
                "data-role": "mois",
            }
        )
        self.fields["type_rapport"].widget.attrs.update(
            {
                "data-role": "type-rapport",
            }
        )
        self.fields["periode"].widget.attrs.update(
            {
                "data-role": "periode",
            }
        )
        self.fields["categorie"].widget.attrs.update(
            {
                "data-role": "categorie",
            }
        )
        self.fields["direction"].widget.attrs.update(
            {
                "data-role": "direction",
            }
        )
        self.fields["etat_requisition"].widget.attrs.update(
            {
                "data-role": "etat-requisition",
            }
        )

        _bootstrapify_form_fields(self)

    def clean_annee_fiscale(self) -> ConfigurationSysteme:
        value = self.cleaned_data.get("annee_fiscale")
        try:
            return ConfigurationSysteme.objects.get(pk=int(value))
        except (TypeError, ValueError, ConfigurationSysteme.DoesNotExist):
            raise forms.ValidationError("Année fiscale invalide.")

    def clean_mois(self) -> int | None:
        value = self.cleaned_data.get("mois")
        if value in (None, ""):
            return None

        try:
            mois = int(value)
        except (TypeError, ValueError):
            raise forms.ValidationError("Mois invalide.")

        if mois < 1 or mois > 12:
            raise forms.ValidationError("Mois invalide.")

        return mois

    def clean_type_rapport(self) -> str:
        value = (self.cleaned_data.get("type_rapport") or "").strip()
        if value == "":
            return "stock_global"
        return value

    def clean_etat_requisition(self) -> str:
        value = (self.cleaned_data.get("etat_requisition") or "").strip()
        return value

    def clean(self):
        cleaned_data = super().clean()

        periode = cleaned_data.get("periode")
        mois = cleaned_data.get("mois")
        type_rapport = (cleaned_data.get("type_rapport") or "stock_global").strip()
        categorie = cleaned_data.get("categorie")
        direction = cleaned_data.get("direction")
        etat_requisition = (cleaned_data.get("etat_requisition") or "").strip()

        if periode == "MENSUEL" and mois is None:
            self.add_error("mois", "Le mois est obligatoire pour un rapport mensuel.")

        if periode == "ANNUEL":
            cleaned_data["mois"] = None

        is_default_stock_logic = type_rapport == "stock_global"

        if is_default_stock_logic and etat_requisition:
            cleaned_data["categorie"] = None
            cleaned_data["direction"] = None
            categorie = None
            direction = None

        if type_rapport in {"direction", "direction_plus_demandeuse", "direction_moins_demandeuse"}:
            cleaned_data["direction"] = None
            direction = None

        if type_rapport in {"direction_plus_demandeuse", "direction_moins_demandeuse"} and etat_requisition:
            cleaned_data["etat_requisition"] = ""
            etat_requisition = ""

        if type_rapport in {"article_plus_demande", "article_moins_demande"} and etat_requisition:
            cleaned_data["etat_requisition"] = ""
            etat_requisition = ""

        # Le type "Demandes par catégorie d'article" doit rester inchangé :
        # on ne rend pas la catégorie obligatoire et on ignore ce filtre
        # pour ne pas modifier le comportement historique.
        if type_rapport == "categorie_article" and categorie is not None:
            cleaned_data["categorie"] = None
            categorie = None

        cleaned_data["rapport_cible_label"] = _resolve_rapport_label(periode, type_rapport)
        cleaned_data["type_rapport"] = type_rapport

        cleaned_data["combinaison_logique"] = {
            "periode": periode,
            "type_rapport": type_rapport,
            "utilise_mois": periode == "MENSUEL",
            "utilise_categorie": (
                type_rapport == "stock_global" and cleaned_data.get("categorie") is not None
            ),
            "utilise_direction": cleaned_data.get("direction") is not None,
            "utilise_etat_requisition": bool(cleaned_data.get("etat_requisition")),
            "mode_principal": (
                "requisition_etat_direction"
                if type_rapport == "stock_global" and bool(cleaned_data.get("etat_requisition"))
                else "requisition_article"
                if type_rapport == "stock_global" and cleaned_data.get("direction") is not None
                else type_rapport
            ),
        }

        return cleaned_data