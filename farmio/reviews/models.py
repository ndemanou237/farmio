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


class ReviewModerationStatus(models.TextChoices):
    PENDING = "pending", _("En attente")
    APPROVED = "approved", _("Approuvé")
    REJECTED = "rejected", _("Rejeté")
    HIDDEN = "hidden", _("Masqué")


class ReviewModeration(BaseModel):
    """Persistent moderation metadata kept separate from the existing Review schema."""

    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name="moderation",
        verbose_name=_("avis"),
    )
    status = models.CharField(
        _("statut de modération"),
        max_length=12,
        choices=ReviewModerationStatus.choices,
        default=ReviewModerationStatus.PENDING,
        db_index=True,
    )
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderated_reviews",
        verbose_name=_("modéré par"),
    )
    moderated_at = models.DateTimeField(_("date de modération"), null=True, blank=True)
    moderation_note = models.TextField(_("note de modération"), blank=True)

    class Meta:
        verbose_name = _("modération d'avis")
        verbose_name_plural = _("modérations d'avis")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.review_id} — {self.get_status_display()}"
