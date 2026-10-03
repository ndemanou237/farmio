"""Contrôle d'accès spécifique au catalogue : vérifie que le producteur
connecté est bien le propriétaire du produit avant modification/suppression.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from .models import Product


class ProductOwnerMixin:
    """Charge le produit via son slug et vérifie que request.user est le propriétaire.

    Utilisé par les vues d'édition/suppression/gestion de stock : un producteur
    ne doit jamais pouvoir modifier le produit d'un autre (RG-04).
    """

    slug_url_kwarg = "slug"

    def get_object(self, queryset=None):
        product = get_object_or_404(Product, slug=self.kwargs[self.slug_url_kwarg])
        if product.producer_id != self.request.user.pk:
            raise PermissionDenied(
                str(_("Vous ne pouvez modifier que vos propres produits.")),
            )
        return product
