from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class CartAddForm(forms.Form):
    """Formulaire léger pour l'ajout au panier depuis le catalogue."""

    quantity = forms.IntegerField(min_value=1, initial=1)
    product_id = forms.UUIDField(widget=forms.HiddenInput())


class CartUpdateForm(forms.Form):
    """Formulaire léger pour la mise à jour de quantité dans le panier."""

    quantity = forms.IntegerField(min_value=1, label=_("Quantité"))
