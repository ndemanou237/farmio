from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from farmio.catalog.models import Product
from farmio.core.models import BaseModel
from farmio.utils.enums import CartStatus


class Cart(BaseModel):
    """Panier de l'acheteur — un seul panier ACTIVE à la fois par acheteur"""

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("acheteur"),
        on_delete=models.CASCADE,
        related_name="carts",
        limit_choices_to={"is_buyer": True},
    )
    status = models.CharField(
        _("statut"),
        max_length=20,
        choices=CartStatus.choices,
        default=CartStatus.ACTIVE,
    )

    class Meta:
        verbose_name = _("panier")
        verbose_name_plural = _("paniers")
        constraints = [
            # Un seul panier "ACTIVE" non supprimé par acheteur — les paniers
            # VALIDATED/EMPTY (historique) ne comptent pas dans cette contrainte.
            models.UniqueConstraint(
                fields=["buyer"],
                condition=Q(status="ACTIVE", is_deleted=False),
                name="uniq_active_cart_per_buyer",
            ),
        ]

    def __str__(self) -> str:
        return f"Panier de {self.buyer} ({self.get_status_display()})"

    @property
    def items_count(self) -> int:
        return self.items.count()


class CartItem(BaseModel):
    """Ligne de panier lié au panier"""

    cart = models.ForeignKey(
        Cart,
        verbose_name=_("panier"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        verbose_name=_("produit"),
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(_("quantité"), default=1)
    unit_price = MoneyField(
        _("prix unitaire figé"),
        max_digits=12,
        decimal_places=2,
        default_currency=settings.DEFAULT_CURRENCY,
    )

    class Meta:
        verbose_name = _("article du panier")
        verbose_name_plural = _("articles du panier")
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                condition=Q(is_deleted=False),
                name="uniq_cart_product_active",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.product.price
        super().save(*args, **kwargs)
