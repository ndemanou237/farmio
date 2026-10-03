from __future__ import annotations

from django import forms
from django.contrib.auth import forms as admin_forms
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget
from PIL import Image

from farmio.utils.phone import validate_phone_number

from .models import BuyerProfile
from .models import Location
from .models import ProducerProfile

User = get_user_model()

INPUT_CLASSES = "input-field"
OTP_CODE_LENGHT = 6
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_IDENTITY_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}


def validate_identity_document(uploaded_file):
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise ValidationError(_("Le document doit faire au maximum 5 Mo."))

    uploaded_file.seek(0)
    header = uploaded_file.read(12)
    uploaded_file.seek(0)
    content_type = uploaded_file.content_type
    is_pdf = header.startswith(b"%PDF-") and content_type == "application/pdf"
    is_image = False
    if content_type in ALLOWED_IDENTITY_MIME_TYPES - {"application/pdf"}:
        try:
            with Image.open(uploaded_file) as image:
                image.verify()
                is_image = image.format in {"JPEG", "PNG", "WEBP"}
        except OSError, Image.DecompressionBombError:
            is_image = False
        finally:
            uploaded_file.seek(0)

    if not is_pdf and not is_image:
        raise ValidationError(
            _("Le document doit être un PDF, JPEG, PNG ou WebP valide."),
        )


def _text(**attrs):
    base = {"class": INPUT_CLASSES}
    base.update(attrs)
    return forms.TextInput(attrs=base)


# ==============================================================================
# Formulaires admin (cookiecutter-django, conservés pour /admin/)
# ==============================================================================
class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.UserCreationForm):
    class Meta(admin_forms.UserCreationForm.Meta):
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("Cette adresse email est déjà utilisée.")},
        }


# ==============================================================================
# Inscription — noms de champs FIGÉS ici, ce sont ceux que les templates
# doivent référencer dans leurs {% include ... with field=form.xxx %}.
# ==============================================================================
class LocationFieldsMixin(forms.Form):
    country = CountryField().formfield(
        label=_("Pays"),
        initial="CM",
        widget=CountrySelectWidget(attrs={"class": INPUT_CLASSES}),
    )
    region = forms.CharField(label=_("Région"), max_length=100, widget=_text())
    city = forms.CharField(label=_("Ville"), max_length=100, widget=_text())

    def save_location(self) -> Location:
        location, _created = Location.objects.get_or_create(
            country=self.cleaned_data["country"],
            region=self.cleaned_data["region"],
            city=self.cleaned_data["city"],
        )
        return location


class BaseSignupForm(LocationFieldsMixin):
    name = forms.CharField(label=_("Nom complet"), max_length=255, widget=_text())
    email = forms.EmailField(label=_("Adresse email"), widget=_text(type="email"))
    phone_number = forms.CharField(
        label=_("Téléphone"),
        max_length=20,
        widget=_text(type="tel"),
    )
    password1 = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES}),
    )
    password2 = forms.CharField(
        label=_("Confirmation du mot de passe"),
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                _("Un compte existe déjà avec cette adresse email."),
            )
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data["phone_number"]
        validate_phone_number(phone)
        return phone

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("Les mots de passe ne correspondent pas."))
        if p1:
            password_validation.validate_password(p1)
        return cleaned


class BuyerSignupForm(BaseSignupForm):
    organization_name = forms.CharField(
        label=_("Nom de la structure (optionnel)"),
        max_length=150,
        required=False,
        widget=_text(),
    )

    def save(self) -> User:
        location = self.save_location()
        user = User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            name=self.cleaned_data["name"],
            phone_number=self.cleaned_data["phone_number"],
            is_buyer=True,
            is_producer=False,
            location=location,
        )
        BuyerProfile.objects.create(
            user=user,
            organization_name=self.cleaned_data.get("organization_name", ""),
        )
        return user


class ProducerSignupForm(BaseSignupForm):
    company_name = forms.CharField(
        label=_("Nom de l'entreprise"),
        max_length=150,
        widget=_text(),
    )
    business_registration_number = forms.CharField(
        label=_("Numéro RCCM / NIU (optionnel)"),
        max_length=50,
        required=False,
        widget=_text(),
    )
    identity_number = forms.CharField(
        label=_("Numéro de pièce d'identité (optionnel)"),
        max_length=50,
        required=False,
        widget=_text(),
    )
    identity_document = forms.FileField(
        label=_("Pièce d'identité (PDF, JPG, PNG)"),
        required=False,
        validators=[validate_identity_document],
        widget=forms.ClearableFileInput(
            attrs={"class": "hidden", "accept": ".pdf, .jpg, .jpeg, .png"},
        ),
    )
    description = forms.CharField(
        label=_("Décrivez votre activité"),
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 4}),
    )

    def save(self) -> User:
        location = self.save_location()
        user = User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            name=self.cleaned_data["name"],
            phone_number=self.cleaned_data["phone_number"],
            is_producer=True,
            location=location,
        )
        ProducerProfile.objects.create(
            user=user,
            company_name=self.cleaned_data["company_name"],
            business_registration_number=self.cleaned_data.get(
                "business_registration_number",
                "",
            ),
            identity_number=self.cleaned_data.get("identity_number", ""),
            identity_document=self.cleaned_data.get("identity_document"),
            description=self.cleaned_data.get("description", ""),
        )
        return user


# ==============================================================================
# Connexion
# ==============================================================================
class FarmioLoginForm(AuthenticationForm):
    username = forms.EmailField(label=_("Adresse email"), widget=_text(type="email"))
    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES}),
    )

    error_messages = {
        "invalid_login": _("Adresse email ou mot de passe incorrect."),
        "inactive": _("Ce compte est désactivé."),
    }


# ==============================================================================
# OTP
# ==============================================================================


class OtpVerifyForm(forms.Form):
    """Formulaire de vérification du code OTP."""

    code = forms.CharField(
        label=_("Code de vérification"),
        min_length=6,
        max_length=6,
        required=True,
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "maxlength": "6",
            },
        ),
    )

    def clean_code(self):
        code = self.cleaned_data["code"]

        if not code.isdigit():
            raise forms.ValidationError(
                _("Le code doit contenir uniquement des chiffres."),
            )

        if len(code) != OTP_CODE_LENGHT:
            raise forms.ValidationError(
                _("Le code doit contenir %(lenght)d chiffres.")
                % {"lenght": OTP_CODE_LENGHT},
            )

        return code


# ==============================================================================
# Profil
# ==============================================================================
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "phone_number"]
        widgets = {"name": _text(), "phone_number": _text(type="tel")}
        labels = {"name": _("Nom complet"), "phone_number": _("Téléphone")}

    def clean_phone_number(self):
        phone = self.cleaned_data["phone_number"]
        if phone:
            validate_phone_number(phone)
        return phone


class ProducerProfileUpdateForm(forms.ModelForm):
    identity_document = forms.FileField(
        label=_("Pièce d'identité (PDF, JPG, PNG)"),
        required=False,
        validators=[validate_identity_document],
        widget=forms.ClearableFileInput(attrs={"class": INPUT_CLASSES}),
    )

    class Meta:
        model = ProducerProfile
        fields = [
            "company_name",
            "business_registration_number",
            "identity_number",
            "identity_document",
            "description",
        ]
        widgets = {
            "company_name": _text(),
            "business_registration_number": _text(),
            "identity_number": _text(),
            "identity_document": forms.ClearableFileInput(
                attrs={"class": INPUT_CLASSES},
            ),
            "description": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 4}),
        }


# ==============================================================================
# Mot de passe
# ==============================================================================
class FarmioPasswordChangeForm(forms.Form):
    old_password = forms.CharField(
        label=_("Mot de passe actuel"),
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES}),
    )
    new_password1 = forms.CharField(
        label=_("Nouveau mot de passe"),
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES}),
    )
    new_password2 = forms.CharField(
        label=_("Confirmez le nouveau mot de passe"),
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES}),
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data["old_password"]
        if not self.user.check_password(old_password):
            raise forms.ValidationError(_("Mot de passe actuel incorrect."))
        return old_password

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("new_password1"), cleaned.get("new_password2")
        if p1 and p2 and p1 != p2:
            self.add_error(
                "new_password2",
                _("Les mots de passe ne correspondent pas."),
            )
        if p1:
            password_validation.validate_password(p1, self.user)
        return cleaned

    def save(self):
        self.user.set_password(self.cleaned_data["new_password1"])
        self.user.save(update_fields=["password"])
        return self.user


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(label=_("Adresse email"), widget=_text(type="email"))


class PasswordResetConfirmForm(forms.Form):
    new_password1 = forms.CharField(
        label=_("Nouveau mot de passe"),
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES}),
    )
    new_password2 = forms.CharField(
        label=_("Confirmez le nouveau mot de passe"),
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASSES}),
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("new_password1"), cleaned.get("new_password2")
        if p1 and p2 and p1 != p2:
            self.add_error(
                "new_password2",
                _("Les mots de passe ne correspondent pas."),
            )
        if p1:
            password_validation.validate_password(p1, self.user)
        return cleaned

    def save(self):
        self.user.set_password(self.cleaned_data["new_password1"])
        self.user.save(update_fields=["password"])
        return self.user


# ==============================================================================
# Approbation producteur (admin)
# ==============================================================================
class ProducerReviewForm(forms.Form):
    DECISION_CHOICES = (
        ("APPROVE", _("Approuver")),
        ("REJECT", _("Rejeter")),
    )
    decision = forms.ChoiceField(choices=DECISION_CHOICES, widget=forms.RadioSelect)
    reason = forms.CharField(
        label=_("Motif (obligatoire en cas de rejet)"),
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 3}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("decision") == "REJECT" and not cleaned.get("reason"):
            self.add_error("reason", _("Merci de préciser le motif du rejet."))
        return cleaned
