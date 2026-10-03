"""Formulaires du catalogue.

Note importante : conformément à la roadmap, aucune compression/redimension-
nement d'image n'est effectué ici (pas de traitement Pillow) — les fichiers
sont enregistrés tels que reçus.
"""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image

from .models import Product

INPUT_CLASSES = "input-field"


class MultipleFileInput(forms.ClearableFileInput):
    """Widget acceptant plusieurs fichiers (Django ne le fournit pas nativement)."""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Champ associé à MultipleFileInput — renvoie une liste de fichiers nettoyés."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data]
        return single_file_clean(data, initial)


MAX_UPLOAD_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def validate_product_image(uploaded_file):
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise ValidationError(_("Chaque image doit faire au maximum 5 Mo."))

    try:
        with Image.open(uploaded_file) as image:
            image.verify()
            image_format = image.format
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValidationError(_("Le fichier n'est pas une image valide.")) from exc
    finally:
        uploaded_file.seek(0)

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError(_("Seuls les formats JPEG, PNG et WebP sont acceptés."))

    if uploaded_file.content_type != ALLOWED_IMAGE_FORMATS[image_format]:
        raise ValidationError(
            _("Le type réel de l'image ne correspond pas à son contenu."),
        )


class MultipleImageField(forms.ImageField):
    """Champ ImageField acceptant plusieurs fichiers et contrôles serveur."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            files = [forms.ImageField.clean(self, item, initial) for item in data]
        else:
            files = [forms.ImageField.clean(self, data, initial)] if data else []
        for uploaded_file in files:
            validate_product_image(uploaded_file)
        return files


class ProductForm(forms.ModelForm):
    """Formulaire de création/édition d'un produit — hors gestion des images."""

    class Meta:
        model = Product
        fields = [
            "category",
            "name",
            "description",
            "price",
            "quantity",
            "unit",
            "status",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": INPUT_CLASSES}),
            "name": forms.TextInput(
                attrs={
                    "class": INPUT_CLASSES,
                    "placeholder": _("Ex. Tomates fraîches"),
                },
            ),
            "description": forms.Textarea(
                attrs={
                    "class": INPUT_CLASSES,
                    "rows": 5,
                    "placeholder": _("Décrivez votre produit..."),
                },
            ),
            "quantity": forms.NumberInput(
                attrs={
                    "class": INPUT_CLASSES,
                    "min": 0,
                    "step": "0.01",
                    "placeholder": _("Ex. 100"),
                },
            ),
            "unit": forms.Select(attrs={"class": INPUT_CLASSES}),
            "status": forms.Select(attrs={"class": INPUT_CLASSES}),
        }
        labels = {
            "category": _("Catégorie"),
            "name": _("Nom du produit"),
            "description": _("Description"),
            "price": _("Prix unitaire"),
            "quantity": _("Quantité disponible"),
            "unit": _("Unité"),
            "status": _("Statut"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Style du widget monétaire généré par django-money
        if "price" in self.fields:
            self.fields["price"].widget.attrs.update(
                {
                    "class": INPUT_CLASSES,
                    "min": "0",
                    "step": "0.01",
                    "placeholder": _("Ex. 5000"),
                },
            )


class ProductImageUploadForm(forms.Form):
    """Formulaire d'upload de plusieurs images, utilisé lors de la création/édition.

    Le champ `main_image_index` (caché, rempli en JS) indique quel fichier de
    la sélection doit devenir l'image principale (is_main=True).
    """

    images = MultipleImageField(
        label=_("Photos du produit"),
        required=False,
        widget=MultipleFileInput(
            attrs={"class": INPUT_CLASSES, "accept": "image/jpeg,image/png,image/webp"},
        ),
    )
    main_image_index = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={"data-role": "main-image-index"}),
    )


class ProductStockForm(forms.ModelForm):
    """Formulaire allégé pour la mise à jour rapide du stock et du statut."""

    class Meta:
        model = Product
        fields = ["quantity", "status"]
        widgets = {
            "quantity": forms.NumberInput(attrs={"class": INPUT_CLASSES, "min": 0}),
            "status": forms.Select(attrs={"class": INPUT_CLASSES}),
        }
        labels = {"quantity": _("Quantité disponible"), "status": _("Statut")}
