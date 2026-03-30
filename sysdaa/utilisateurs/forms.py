from __future__ import annotations

import json

from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import Direction, Utilisateur


PASSWORD_WIDGET_ATTRS = {
    "class": "form-control password-protected",
    "autocomplete": "new-password",
    "autocorrect": "off",
    "autocapitalize": "none",
    "spellcheck": "false",
    "data-password-protected": "true",
}

ROLE_GESTIONNAIRE = "Gestionnaire des ressources matérielles"
ROLE_DIRECTEUR_DAA = "Directeur DAA"
ROLE_DIRECTEUR_DIRECTION = "Directeur de direction"
ROLE_ASSISTANT_DIRECTEUR = "Assistant de directeur"
DIRECTION_DAA = "Direction des Affaires Administratives"


def _normalize_label(value: str) -> str:
    return (value or "").strip().lower()


class _UtilisateurBaseFormMixin:
    role_direction_locked_names = {
        _normalize_label(ROLE_GESTIONNAIRE),
        _normalize_label(ROLE_DIRECTEUR_DAA),
    }

    def _posted_role_id(self):
        return self.data.get(self.add_prefix("role")) or None

    def _resolve_selected_role(self):
        role_field = self.fields.get("role")
        if not role_field:
            return None

        role = getattr(self, "cleaned_data", {}).get("role")
        if role is not None:
            return role

        role_id = self._posted_role_id()
        if role_id:
            try:
                return role_field.queryset.get(pk=role_id)
            except Exception:
                return None

        return getattr(getattr(self, "instance", None), "role", None)

    def _selected_role_name(self) -> str:
        role = self._resolve_selected_role()
        return _normalize_label(getattr(role, "nom_role", ""))

    def _is_locked_daa_role(self) -> bool:
        return self._selected_role_name() in self.role_direction_locked_names

    def _is_assistant_role(self) -> bool:
        return self._selected_role_name() == _normalize_label(ROLE_ASSISTANT_DIRECTEUR)

    def _is_directeur_direction_role(self) -> bool:
        return self._selected_role_name() == _normalize_label(ROLE_DIRECTEUR_DIRECTION)

    def _current_instance_direction_id(self):
        instance = getattr(self, "instance", None)
        if instance is not None and getattr(instance, "pk", None):
            return getattr(instance, "direction_affectee_id", None)
        return None

    def _daa_direction(self):
        try:
            return Direction.objects.get(nom__iexact=DIRECTION_DAA)
        except Direction.DoesNotExist:
            return None

    def _active_directeurs_qs(self):
        return (
            Utilisateur.objects.filter(
                is_directeur_direction=True,
                statut=Utilisateur.STATUT_ACTIF,
                direction_affectee__isnull=False,
            )
            .select_related("direction_affectee", "role")
            .order_by("direction_affectee__nom", "prenom", "nom", "email")
        )

    def _active_assistants_qs(self):
        return (
            Utilisateur.objects.filter(
                is_assistant_directeur=True,
                statut=Utilisateur.STATUT_ACTIF,
                direction_affectee__isnull=False,
            )
            .select_related("direction_affectee", "role", "directeur_superviseur")
            .order_by("direction_affectee__nom", "prenom", "nom", "email")
        )

    def _assistant_blocked_direction_ids(self) -> list[int]:
        blocked_ids = set(
            self._active_assistants_qs().values_list("direction_affectee_id", flat=True)
        )

        current_direction_id = self._current_instance_direction_id()
        if current_direction_id:
            blocked_ids.discard(current_direction_id)

        return sorted(x for x in blocked_ids if x)

    def _director_blocked_direction_ids(self) -> list[int]:
        blocked_ids = set(
            self._active_directeurs_qs().values_list("direction_affectee_id", flat=True)
        )

        current_direction_id = self._current_instance_direction_id()
        if current_direction_id:
            blocked_ids.discard(current_direction_id)

        return sorted(x for x in blocked_ids if x)

    def _assistant_director_map(self) -> dict[str, dict[str, str]]:
        mapping: dict[str, dict[str, str]] = {}
        for directeur in self._active_directeurs_qs():
            direction_id = getattr(directeur, "direction_affectee_id", None)
            if not direction_id:
                continue
            mapping[str(direction_id)] = {
                "id": str(directeur.pk),
                "label": f"{directeur.prenom} {directeur.nom}".strip() or directeur.email,
            }
        return mapping

    def _configure_common_fields(self):
        self.fields["direction_affectee"].queryset = Direction.objects.order_by("nom")
        self.fields["direction_affectee"].required = False
        self.fields["role"].queryset = self.fields["role"].queryset.order_by("nom_role")

        assistant_blocked_direction_ids = self._assistant_blocked_direction_ids()
        director_blocked_direction_ids = self._director_blocked_direction_ids()
        assistant_director_map = self._assistant_director_map()
        daa_direction = self._daa_direction()

        self.fields["role"].widget.attrs.update(
            {
                "data-role-select": "true",
                "data-role-locked-daa": json.dumps(
                    [ROLE_GESTIONNAIRE, ROLE_DIRECTEUR_DAA],
                    ensure_ascii=False,
                ),
                "data-role-assistant": ROLE_ASSISTANT_DIRECTEUR,
                "data-role-director-direction": ROLE_DIRECTEUR_DIRECTION,
            }
        )

        self.fields["direction_affectee"].widget.attrs.update(
            {
                "data-direction-select": "true",
                "data-direction-daa-id": str(daa_direction.pk) if daa_direction else "",
                "data-direction-daa-label": DIRECTION_DAA,
                "data-assistant-blocked-directions": json.dumps(
                    assistant_blocked_direction_ids
                ),
                "data-director-blocked-directions": json.dumps(
                    director_blocked_direction_ids
                ),
                "data-assistant-director-map": json.dumps(
                    assistant_director_map,
                    ensure_ascii=False,
                ),
            }
        )

        if self._is_locked_daa_role() and daa_direction is not None:
            self.initial["direction_affectee"] = daa_direction.pk

    def _apply_locked_direction_rule(self, cleaned):
        if not self._is_locked_daa_role():
            return

        daa_direction = self._daa_direction()
        if daa_direction is None:
            self.add_error(
                "direction_affectee",
                "La direction 'Direction des Affaires Administratives' est introuvable.",
            )
            return

        cleaned["direction_affectee"] = daa_direction
        cleaned["directeur_superviseur"] = None

    def _apply_directeur_direction_rule(self, cleaned):
        if not self._is_directeur_direction_role():
            return

        direction = cleaned.get("direction_affectee")
        if not direction:
            self.add_error(
                "direction_affectee",
                "Veuillez choisir une direction pour ce directeur.",
            )
            cleaned["directeur_superviseur"] = None
            return

        blocked_ids = set(self._director_blocked_direction_ids())
        if direction.pk in blocked_ids:
            self.add_error(
                "direction_affectee",
                "Cette direction possède déjà un Directeur de direction actif.",
            )
            cleaned["directeur_superviseur"] = None
            return

        cleaned["directeur_superviseur"] = None

    def _apply_assistant_autowire(self, cleaned):
        if not self._is_assistant_role():
            return

        direction = cleaned.get("direction_affectee")
        if not direction:
            self.add_error(
                "direction_affectee",
                "Veuillez choisir une direction pour cet assistant.",
            )
            cleaned["directeur_superviseur"] = None
            return

        blocked_ids = set(self._assistant_blocked_direction_ids())
        if direction.pk in blocked_ids:
            self.add_error(
                "direction_affectee",
                "Cette direction possède déjà un Assistant de directeur actif.",
            )
            cleaned["directeur_superviseur"] = None
            return

        directeur = (
            Utilisateur.objects.filter(
                is_directeur_direction=True,
                statut=Utilisateur.STATUT_ACTIF,
                direction_affectee=direction,
            )
            .select_related("direction_affectee", "role")
            .order_by("prenom", "nom", "email")
            .first()
        )

        cleaned["directeur_superviseur"] = directeur if directeur is not None else None

    def _validate_business_rules(self, cleaned):
        if self._is_locked_daa_role():
            self._apply_locked_direction_rule(cleaned)
            return

        if self._is_directeur_direction_role():
            self._apply_directeur_direction_rule(cleaned)
            return

        if self._is_assistant_role():
            self._apply_assistant_autowire(cleaned)
            return

        cleaned["directeur_superviseur"] = None


class UtilisateurCreationForm(_UtilisateurBaseFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(
            attrs={
                **PASSWORD_WIDGET_ATTRS,
                "id": "id_password1",
                "placeholder": "Mot de passe",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirmation",
        widget=forms.PasswordInput(
            attrs={
                **PASSWORD_WIDGET_ATTRS,
                "id": "id_password2",
                "placeholder": "Confirmation du mot de passe",
            }
        ),
    )

    class Meta:
        model = Utilisateur
        fields = (
            "email",
            "nom",
            "prenom",
            "direction_affectee",
            "role",
        )
        widgets = {
            "email": forms.EmailInput(
                attrs={"class": "form-control", "autocomplete": "username"}
            ),
            "nom": forms.TextInput(attrs={"class": "form-control"}),
            "prenom": forms.TextInput(attrs={"class": "form-control"}),
            "direction_affectee": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["directeur_superviseur"] = forms.ModelChoiceField(
            queryset=self._active_directeurs_qs(),
            required=False,
            widget=forms.HiddenInput(),
        )

        self._configure_common_fields()

    def clean_password1(self):
        pwd = self.cleaned_data.get("password1") or ""
        validate_password(pwd)
        return pwd

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")

        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Les mots de passe ne correspondent pas.")

        self._validate_business_rules(cleaned)
        cleaned["statut"] = Utilisateur.STATUT_ACTIF
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.statut = Utilisateur.STATUT_ACTIF
        user.direction_affectee = self.cleaned_data.get("direction_affectee")
        user.directeur_superviseur = self.cleaned_data.get("directeur_superviseur")
        if commit:
            user.save()
        return user


class UtilisateurUpdateForm(_UtilisateurBaseFormMixin, forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = (
            "email",
            "nom",
            "prenom",
            "direction_affectee",
            "role",
            "statut",
        )
        widgets = {
            "email": forms.EmailInput(
                attrs={"class": "form-control", "autocomplete": "username"}
            ),
            "nom": forms.TextInput(attrs={"class": "form-control"}),
            "prenom": forms.TextInput(attrs={"class": "form-control"}),
            "direction_affectee": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "statut": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["directeur_superviseur"] = forms.ModelChoiceField(
            queryset=self._active_directeurs_qs(),
            required=False,
            widget=forms.HiddenInput(),
        )

        self._configure_common_fields()

    def clean(self):
        cleaned = super().clean()
        self._validate_business_rules(cleaned)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.direction_affectee = self.cleaned_data.get("direction_affectee")
        user.directeur_superviseur = self.cleaned_data.get("directeur_superviseur")
        if commit:
            user.save()
        return user


class AdminResetPasswordForm(forms.Form):
    password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(
            attrs={
                **PASSWORD_WIDGET_ATTRS,
                "id": "id_password1",
                "placeholder": "Nouveau mot de passe",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirmation",
        widget=forms.PasswordInput(
            attrs={
                **PASSWORD_WIDGET_ATTRS,
                "id": "id_password2",
                "placeholder": "Confirmation du mot de passe",
            }
        ),
    )

    def clean_password1(self):
        pwd = self.cleaned_data.get("password1") or ""
        validate_password(pwd)
        return pwd

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Les mots de passe ne correspondent pas.")
        return cleaned
