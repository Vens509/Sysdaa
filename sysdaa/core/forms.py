from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.forms import AuthenticationForm

BOOTSTRAP_INPUT_TYPES = {
    "text",
    "email",
    "password",
    "number",
    "url",
    "tel",
    "search",
    "date",
    "datetime-local",
}


class BootstrapFormMixin:
    """
    Ajoute automatiquement les classes Bootstrap aux widgets.
    - input => form-control
    - select => form-select
    - checkbox => form-check-input
    """

    def _apply_bootstrap(self):
        for name, field in self.fields.items():
            w = field.widget

            if isinstance(w, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                w.attrs.setdefault("class", "")
                if "form-check-input" not in w.attrs["class"]:
                    w.attrs["class"] = (w.attrs["class"] + " form-check-input").strip()
                continue

            if isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "")
                if "form-select" not in w.attrs["class"]:
                    w.attrs["class"] = (w.attrs["class"] + " form-select").strip()
                continue

            w.attrs.setdefault("class", "")
            if isinstance(w, forms.Textarea):
                if "form-control" not in w.attrs["class"]:
                    w.attrs["class"] = (w.attrs["class"] + " form-control").strip()
                continue

            if hasattr(w, "input_type") and w.input_type in BOOTSTRAP_INPUT_TYPES:
                if "form-control" not in w.attrs["class"]:
                    w.attrs["class"] = (w.attrs["class"] + " form-control").strip()

            if not w.attrs.get("placeholder") and field.label:
                w.attrs["placeholder"] = field.label


class BootstrapModelForm(BootstrapFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class BootstrapForm(BootstrapFormMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class CustomPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    """
    Formulaire pour la page 'Modifier mon mot de passe'.

    Important :
    On conserve la compatibilité avec static/utilisateurs/password-security.js
    qui cible explicitement :
      - id_password1
      - id_password2

    Donc :
      - new_password1 -> id_password1
      - new_password2 -> id_password2
    """

    old_password = forms.CharField(
        label="Ancien mot de passe",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "class": "password-protected",
                "id": "id_old_password",
            }
        ),
    )

    new_password1 = forms.CharField(
        label="Nouveau mot de passe",
        strip=False,
        help_text="",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "class": "password-protected",
                "id": "id_password1",
            }
        ),
    )

    new_password2 = forms.CharField(
        label="Confirmation du nouveau mot de passe",
        strip=False,
        help_text="",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "class": "password-protected",
                "id": "id_password2",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._apply_bootstrap()

        self.fields["old_password"].widget.attrs.update(
            {
                "placeholder": "Ancien mot de passe",
                "autocorrect": "off",
                "autocapitalize": "none",
                "spellcheck": "false",
            }
        )

        self.fields["new_password1"].widget.attrs.update(
            {
                "placeholder": "Nouveau mot de passe",
                "autocorrect": "off",
                "autocapitalize": "none",
                "spellcheck": "false",
            }
        )

        self.fields["new_password2"].widget.attrs.update(
            {
                "placeholder": "Confirmation du nouveau mot de passe",
                "autocorrect": "off",
                "autocapitalize": "none",
                "spellcheck": "false",
            }
        )

        self.fields["new_password1"].help_text = ""
        self.fields["new_password2"].help_text = ""

    @property
    def password_rules_html(self):
        return """
<ul class="mb-0 ps-3">
  <li>Votre mot de passe ne doit pas trop ressembler à vos autres informations personnelles.</li>
  <li>Votre mot de passe doit contenir au minimum 8 caractères.</li>
  <li>Votre mot de passe ne peut pas être un mot de passe couramment utilisé.</li>
  <li>Votre mot de passe ne peut pas être entièrement numérique.</li>
</ul>
""".strip()
class ActiveStatusAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "inactive": "Connexion impossible : ce compte est inactif.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()

        username = self.fields.get("username")
        password = self.fields.get("password")

        if username:
            username.widget.attrs.update({"placeholder": "Adresse email", "autocomplete": "username"})
        if password:
            password.widget.attrs.update({"placeholder": "Mot de passe", "autocomplete": "current-password"})

    def confirm_login_allowed(self, user):
        if not getattr(user, "is_active", False) or getattr(user, "statut", "") != getattr(user, "STATUT_ACTIF", "Actif"):
            raise forms.ValidationError(self.error_messages["inactive"], code="inactive")
        return super().confirm_login_allowed(user)