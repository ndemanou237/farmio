from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from farmio.core.models import BaseModel
from farmio.orders.models import Order


class Review(BaseModel):
    """Avis d'un acheteur sur un producteur"""

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("acheteur"),
        on_delete=models.CASCADE,
        related_name="reviews_written",
        limit_choices_to={"is_buyer": True},
    )
    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("producteur"),
        on_delete=models.CASCADE,
        related_name="reviews_received",
        limit_choices_to={"is_producer": True},
    )
    order = models.ForeignKey(
        Order,
        verbose_name=_("commande"),
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        _("note"),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(_("commentaire"), blank=True)

    class Meta:
        verbose_name = _("avis")
        verbose_name_plural = _("avis")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(is_deleted=False),
                name="uniq_review_per_order_active",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.rating}/5 — {self.producer} par {self.buyer}"
