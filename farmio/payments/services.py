from __future__ import annotations

import logging
from decimal import Decimal
from decimal import InvalidOperation
from typing import Any

import stripe
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.money import Money

from farmio.notifications.services import create_notification
from farmio.orders.models import Order
from farmio.payments.models import PaymentTransaction
from farmio.utils.enums import OrderStatus
from farmio.utils.enums import PaymentMethod
from farmio.utils.enums import PaymentProvider
from farmio.utils.enums import PaymentTransactionStatus
from farmio.utils.enums import PaymentTransactionType

logger = logging.getLogger(__name__)
ZERO_DECIMAL_CURRENCIES = {"bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf"}


class PaymentError(ValueError):
    """A payment request that cannot be safely initiated or finalized."""


def _stripe_amount(amount: Money) -> int:
    currency = amount.currency.code.lower()
    exponent = 0 if currency in ZERO_DECIMAL_CURRENCIES else 2
    multiplier = Decimal(10) ** exponent
    try:
        minor_amount = Decimal(amount.amount) * multiplier
    except (InvalidOperation, TypeError) as exc:
        raise PaymentError(_("Montant de paiement invalide.")) from exc
    if minor_amount != minor_amount.to_integral_value() or minor_amount <= 0:
        raise PaymentError(_("Le montant ne peut pas être représenté par Stripe."))
    return int(minor_amount)


def _get_order_for_payment(order_id: str, buyer) -> Order:
    try:
        order = Order.objects.select_for_update().select_related(
            "buyer",
            "producer",
        ).get(pk=order_id, is_deleted=False)
    except (Order.DoesNotExist, ValueError) as exc:
        raise PaymentError(_("Commande introuvable.")) from exc
    if order.buyer_id != buyer.pk:
        raise PermissionDenied(_("Vous ne pouvez payer que vos propres commandes."))
    if order.status not in {OrderStatus.PENDING, OrderStatus.CONFIRMED}:
        raise PaymentError(_("Cette commande ne peut plus être payée."))
    successful_payment = PaymentTransaction.objects.filter(
        order=order,
        transaction_type=PaymentTransactionType.CHARGE,
        status=PaymentTransactionStatus.SUCCESS,
    ).exists()
    if successful_payment:
        raise PaymentError(_("Cette commande a déjà été payée."))
    if order.total_amount.amount <= 0:
        raise PaymentError(_("Le montant de la commande est invalide."))
    return order


def start_stripe_checkout(
    order_id: str,
    buyer,
    *,
    success_url: str,
    cancel_url: str,
) -> tuple[PaymentTransaction, str]:
    """Create/reuse a Stripe test-mode Checkout session for the authorized buyer."""
    secret_key = settings.STRIPE_SECRET_KEY
    if not secret_key:
        raise PaymentError(_("Le paiement par carte n'est pas configuré."))
    if not getattr(settings, "STRIPE_TEST_MODE", True) or not secret_key.startswith(
        "sk_test_",
    ):
        raise PaymentError(_("Farmio accepte uniquement les clés Stripe de test."))

    session_url = ""
    provider_error: str | None = None
    payment: PaymentTransaction | None = None
    with transaction.atomic():
        order = _get_order_for_payment(order_id, buyer)
        payment = (
            PaymentTransaction.objects.select_for_update()
            .filter(
                order=order,
                transaction_type=PaymentTransactionType.CHARGE,
                provider=PaymentProvider.STRIPE,
                status=PaymentTransactionStatus.PENDING,
            )
            .order_by("-created_at")
            .first()
        )
        if payment and payment.metadata.get("checkout_url"):
            return payment, payment.metadata["checkout_url"]
        if payment is None:
            payment = PaymentTransaction.objects.create(
                order=order,
                transaction_type=PaymentTransactionType.CHARGE,
                status=PaymentTransactionStatus.PENDING,
                amount=order.total_amount,
                refunded_amount=Money(0, order.total_amount.currency),
                method=PaymentMethod.CARD,
                provider=PaymentProvider.STRIPE,
                created_by=buyer,
                updated_by=buyer,
            )

        stripe.api_key = secret_key
        amount_minor = _stripe_amount(order.total_amount)
        product_names = [line.product.name for line in order.lines.select_related("product")]
        product_title = _("Commande Farmio %(reference)s") % {
            "reference": order.reference,
        }
        if product_names:
            product_title = f"{product_title} — {', '.join(product_names[:3])}"
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                client_reference_id=str(order.pk),
                line_items=[
                    {
                        "price_data": {
                            "currency": order.total_amount.currency.code.lower(),
                            "product_data": {"name": product_title[:250]},
                            "unit_amount": amount_minor,
                        },
                        "quantity": 1,
                    },
                ],
                success_url=success_url,
                cancel_url=f"{cancel_url}?payment_id={payment.pk}",
                metadata={
                    "order_id": str(order.pk),
                    "payment_transaction_id": str(payment.pk),
                },
                idempotency_key=f"farmio-payment-{payment.pk}",
            )
            session_url = session.url or ""
            if not session_url:
                provider_error = "Stripe n'a pas retourné d'URL de paiement."
            else:
                payment.provider_reference = session.id
                payment.provider_transaction_id = session.id
                payment.metadata = {
                    **payment.metadata,
                    "checkout_url": session_url,
                    "checkout_session_id": session.id,
                    "mode": "test",
                }
                payment.provider_response = {"checkout_session_id": session.id}
                payment.updated_by = buyer
                payment.save(
                    update_fields=[
                        "provider_reference",
                        "provider_transaction_id",
                        "metadata",
                        "provider_response",
                        "updated_by",
                        "updated_at",
                    ],
                )
        except stripe.StripeError as exc:
            provider_error = "Le prestataire de paiement est momentanément indisponible."
            logger.warning("Stripe checkout initiation failed: %s", exc)

        if provider_error:
            payment.status = PaymentTransactionStatus.FAILED
            payment.failure_reason = provider_error
            payment.processed_at = timezone.now()
            payment.save(
                update_fields=["status", "failure_reason", "processed_at", "updated_at"],
            )

    if provider_error:
        raise PaymentError(_(provider_error))
    if payment is None or not session_url:
        raise PaymentError(_("Impossible de démarrer le paiement."))
    return payment, session_url


def start_mobile_money_intent(
    order_id: str,
    buyer,
    provider_key: str,
) -> PaymentTransaction:
    """Record an explicitly unconfigured Mobile Money intent; never report it paid."""
    if provider_key not in {"orange_money", "mtn_momo", "other"}:
        raise PaymentError(_("Fournisseur Mobile Money invalide."))
    with transaction.atomic():
        order = _get_order_for_payment(order_id, buyer)
        existing = PaymentTransaction.objects.select_for_update().filter(
            order=order,
            transaction_type=PaymentTransactionType.CHARGE,
            provider=PaymentProvider.MOBILE_MONEY_MANUAL,
            status=PaymentTransactionStatus.PENDING,
        ).first()
        if existing:
            return existing
        return PaymentTransaction.objects.create(
            order=order,
            transaction_type=PaymentTransactionType.CHARGE,
            status=PaymentTransactionStatus.PENDING,
            amount=order.total_amount,
            refunded_amount=Money(0, order.total_amount.currency),
            method=PaymentMethod.MOBILE_MONEY,
            provider=PaymentProvider.MOBILE_MONEY_MANUAL,
            provider_reference=f"FM-{order.reference}-{timezone.now():%Y%m%d%H%M%S}",
            metadata={
                "provider_key": provider_key,
                "integration_configured": False,
                "notice": "No payment request was sent and no funds were collected.",
            },
            created_by=buyer,
            updated_by=buyer,
        )


def cancel_pending_payment(payment_id: str, buyer) -> PaymentTransaction:
    with transaction.atomic():
        try:
            payment = PaymentTransaction.objects.select_for_update().select_related(
                "order",
            ).get(pk=payment_id)
        except (PaymentTransaction.DoesNotExist, ValueError) as exc:
            raise PaymentError(_("Transaction introuvable.")) from exc
        if payment.order.buyer_id != buyer.pk:
            raise PermissionDenied(_("Vous ne pouvez pas modifier cette transaction."))
        if payment.status == PaymentTransactionStatus.PENDING:
            payment.status = PaymentTransactionStatus.CANCELLED
            payment.processed_at = timezone.now()
            payment.updated_by = buyer
            payment.save(
                update_fields=["status", "processed_at", "updated_by", "updated_at"],
            )
        return payment


def _notify_payment_result(payment: PaymentTransaction, succeeded: bool) -> None:
    order = payment.order
    if succeeded:
        title = _("Paiement confirmé")
        buyer_message = _("Le paiement de la commande %(reference)s a été confirmé.")
        producer_message = _("La commande %(reference)s a été payée.")
        subject = _("Paiement confirmé sur Farmio")
    else:
        title = _("Paiement échoué")
        buyer_message = _("Le paiement de la commande %(reference)s a échoué.")
        producer_message = _("Le paiement de la commande %(reference)s a échoué.")
        subject = _("Échec de paiement Farmio")
    values = {"reference": order.reference}
    create_notification(
        order.buyer,
        title,
        buyer_message % values,
        email_subject=subject,
    )
    if succeeded:
        create_notification(
            order.producer,
            title,
            producer_message % values,
            email_subject=subject,
        )


def process_stripe_event(event: Any) -> bool:
    """Apply a verified Stripe event once, validating order, currency and amount."""
    event_type = getattr(event, "type", "")
    event_id = getattr(event, "id", "")
    data = getattr(event, "data", None)
    session = getattr(data, "object", None)
    if session is None:
        return False
    metadata = getattr(session, "metadata", {}) or {}
    metadata = metadata.to_dict() if hasattr(metadata, "to_dict") else metadata
    payment_id = metadata.get("payment_transaction_id")
    if not payment_id:
        return False

    transitioned = False
    with transaction.atomic():
        payment_identity = PaymentTransaction.objects.filter(
            pk=payment_id,
            provider=PaymentProvider.STRIPE,
            transaction_type=PaymentTransactionType.CHARGE,
        ).values("order_id").first()
        if payment_identity is None:
            return False
        try:
            order = Order.objects.select_for_update().select_related(
                "buyer",
                "producer",
            ).get(pk=payment_identity["order_id"])
        except Order.DoesNotExist:
            return False
        try:
            payment = PaymentTransaction.objects.select_for_update().get(
                pk=payment_id,
                provider=PaymentProvider.STRIPE,
                transaction_type=PaymentTransactionType.CHARGE,
            )
        except (PaymentTransaction.DoesNotExist, ValueError):
            return False
        if payment.provider_response.get("last_event_id") == event_id:
            return True
        if payment.status in {
            PaymentTransactionStatus.SUCCESS,
            PaymentTransactionStatus.REFUNDED,
            PaymentTransactionStatus.PARTIALLY_REFUNDED,
            PaymentTransactionStatus.FRAUD,
        }:
            return True
        if str(getattr(session, "id", "")) != payment.provider_reference:
            return False

        if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            if getattr(session, "payment_status", "") != "paid":
                return True
            if order.status not in {OrderStatus.PENDING, OrderStatus.CONFIRMED}:
                payment.status = PaymentTransactionStatus.FRAUD
                payment.failure_reason = "Stripe confirmed payment for a closed order."
                payment.processed_at = timezone.now()
                payment.provider_transaction_id = str(
                    getattr(session, "payment_intent", "") or payment.provider_reference,
                )
                payment.provider_response = {
                    **payment.provider_response,
                    "last_event_id": event_id,
                    "last_event_type": event_type,
                }
                payment.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "processed_at",
                        "provider_transaction_id",
                        "provider_response",
                        "updated_at",
                    ],
                )
                for administrator in type(order.buyer).objects.filter(
                    is_staff=True,
                    is_active=True,
                ):
                    create_notification(
                        administrator,
                        _("Paiement à examiner"),
                        _("Stripe a confirmé un paiement pour la commande clôturée %(reference)s.")
                        % {"reference": order.reference},
                        email_subject=_("Action requise : paiement Farmio"),
                    )
                return True
            expected_amount = _stripe_amount(payment.amount)
            session_amount = getattr(session, "amount_total", None)
            session_currency = str(getattr(session, "currency", "")).upper()
            if (
                session_amount != expected_amount
                or session_currency != payment.amount.currency.code.upper()
            ):
                payment.status = PaymentTransactionStatus.FAILED
                payment.failure_reason = "Stripe amount or currency did not match the order."
                payment.processed_at = timezone.now()
                transitioned = True
                succeeded = False
            else:
                payment.status = PaymentTransactionStatus.SUCCESS
                payment.failure_reason = ""
                payment.processed_at = timezone.now()
                payment.provider_transaction_id = str(
                    getattr(session, "payment_intent", "") or payment.provider_reference,
                )
                transitioned = True
                succeeded = True
        elif event_type in {
            "checkout.session.async_payment_failed",
            "checkout.session.expired",
        }:
            payment.status = (
                PaymentTransactionStatus.FAILED
                if event_type.endswith("payment_failed")
                else PaymentTransactionStatus.CANCELLED
            )
            payment.failure_reason = (
                "Stripe payment failed."
                if payment.status == PaymentTransactionStatus.FAILED
                else "Stripe Checkout session expired."
            )
            payment.processed_at = timezone.now()
            transitioned = True
            succeeded = False
        else:
            return True

        payment.provider_response = {
            **payment.provider_response,
            "last_event_id": event_id,
            "last_event_type": event_type,
            "payment_status": getattr(session, "payment_status", ""),
        }
        payment.save(
            update_fields=[
                "status",
                "failure_reason",
                "processed_at",
                "provider_transaction_id",
                "provider_response",
                "updated_at",
            ],
        )
        if transitioned:
            _notify_payment_result(payment, succeeded)
    return transitioned
