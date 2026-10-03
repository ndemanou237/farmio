from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from farmio.core.models import BaseModel
from farmio.orders.models import Order
from farmio.utils.enums import PaymentMethod
from farmio.utils.enums import PaymentProvider
from farmio.utils.enums import PaymentTransactionStatus
from farmio.utils.enums import PaymentTransactionType


class PaymentTransaction(BaseModel):
    """Transaction de paiement liée à une commande."""

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="payment_transactions",
        verbose_name=_("commande"),
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("transaction parente"),
        help_text=_(
            "Référence à la transaction d'origine pour les remboursements "
            "ou annulations.",
        ),
    )

    transaction_type = models.CharField(
        _("type"),
        max_length=20,
        choices=PaymentTransactionType.choices,
    )

    status = models.CharField(
        _("statut"),
        max_length=25,
        choices=PaymentTransactionStatus.choices,
        default=PaymentTransactionStatus.PENDING,
        db_index=True,
    )

    amount = MoneyField(
        _("montant"),
        max_digits=12,
        decimal_places=2,
    )

    refunded_amount = MoneyField(
        _("montant remboursé"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    method = models.CharField(
        _("moyen de paiement"),
        max_length=20,
        choices=PaymentMethod.choices,
    )

    provider = models.CharField(
        _("fournisseur de paiement"),
        max_length=50,
        choices=PaymentProvider.choices,
        help_text=_(
            "Exemple : Stripe, Flutterwave, MTN, Orange.",
        ),
    )

    provider_reference = models.CharField(
        _("référence fournisseur"),
        max_length=200,
        blank=True,
        help_text=_(
            "Référence utilisée pour identifier la transaction auprès du fournisseur.",
        ),
    )

    provider_transaction_id = models.CharField(
        _("ID de transaction fournisseur"),
        max_length=200,
        blank=True,
        db_index=True,
        help_text=_(
            "Identifiant de transaction fourni par le prestataire de paiement.",
        ),
    )

    provider_response = models.JSONField(
        _("réponse du fournisseur"),
        default=dict,
        blank=True,
        help_text=_(
            "Réponse brute retournée par le fournisseur de paiement.",
        ),
    )

    initiated_at = models.DateTimeField(
        _("date d'initiation"),
        auto_now_add=True,
    )

    processed_at = models.DateTimeField(
        _("date de traitement"),
        null=True,
        blank=True,
    )

    failure_reason = models.TextField(
        _("motif d'échec"),
        blank=True,
    )

    notes = models.TextField(
        _("notes"),
        blank=True,
    )

    metadata = models.JSONField(
        _("métadonnées"),
        default=dict,
        blank=True,
    )

    class Meta:
        verbose_name = _("transaction de paiement")
        verbose_name_plural = _("transactions de paiement")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_transaction_id"],
                condition=~models.Q(provider_transaction_id=""),
                name="uniq_payment_provider_transaction_id",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.get_transaction_type_display()} "
            f"#{self.pk} - {self.amount} "
            f"({self.get_status_display()})"
        )
