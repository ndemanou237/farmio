from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from farmio.catalog.models import Product
from farmio.core.models import BaseModel
from farmio.utils.enums import OrderStatus
from farmio.utils.slugs import DbFunctions


class Order(BaseModel):
    """Commande lié a un panier"""

    reference = models.CharField(_("référence"), max_length=20, blank=True)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("acheteur"),
        on_delete=models.PROTECT,
        related_name="orders_placed",
        limit_choices_to={"is_buyer": True},
    )
    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("producteur"),
        on_delete=models.PROTECT,
        related_name="orders_received",
        limit_choices_to={"is_producer": True},
    )
    status = models.CharField(
        _("statut"),
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )
    total_amount = MoneyField(
        _("montant total"),
        max_digits=12,
        decimal_places=2,
        default_currency=settings.DEFAULT_CURRENCY,
    )

    pickup_location = models.CharField(_("lieu de remise"), max_length=255, blank=True)
    pickup_date = models.DateField(_("date de remise"), null=True, blank=True)
    pickup_time = models.TimeField(_("heure de remise"), null=True, blank=True)
    confirmed_at = models.DateTimeField(
        _("date de confirmation"),
        null=True,
        blank=True,
    )
    confirmation_deadline = models.DateTimeField(
        _("date limite de confirmation"),
        null=True,
        blank=True,
    )
    auto_confirmation = models.BooleanField(
        _("confirmation automatique"),
        default=False,
    )

    class Meta:
        verbose_name = _("commande")
        verbose_name_plural = _("commandes")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["producer", "status"]),
            models.Index(fields=["buyer", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["reference"],
                condition=Q(is_deleted=False),
                name="uniq_order_reference_active",
            ),
        ]

    def __str__(self) -> str:
        return f"Commande {self.reference} — {self.producer}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = DbFunctions.random_string_generator(size=10).upper()
        if not self.confirmation_deadline:
            self.confirmation_deadline = timezone.now() + timedelta(hours=48)
        super().save(*args, **kwargs)

    @property
    def is_confirmation_overdue(self) -> bool:
        return (
            self.status == OrderStatus.PENDING
            and timezone.now() >= self.confirmation_deadline
        )


class OrderLine(BaseModel):
    """Ligne de commande d'un commande"""

    order = models.ForeignKey(
        Order,
        verbose_name=_("commande"),
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        Product,
        verbose_name=_("produit"),
        on_delete=models.PROTECT,
        related_name="order_lines",
    )
    quantity = models.PositiveIntegerField(_("quantité"))
    unit_price = MoneyField(
        _("prix unitaire"),
        max_digits=12,
        decimal_places=2,
        default_currency=settings.DEFAULT_CURRENCY,
    )

    class Meta:
        verbose_name = _("ligne de commande")
        verbose_name_plural = _("lignes de commande")

    def __str__(self) -> str:
        return f"{self.quantity} x {self.product.name}"

    @property
    def total(self):
        return self.unit_price * self.quantity
