from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from farmio.catalog.models import Product
from farmio.notifications.services import create_notification
from farmio.orders.models import Order
from farmio.payments.models import PaymentTransaction
from farmio.utils.enums import OrderStatus
from farmio.utils.enums import PaymentTransactionStatus

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def cancel_pending_orders_after_48h_task(self):
    """Annule automatiquement les commandes en attente depuis plus de 48 heures."""
    expired_orders = Order.objects.filter(
        status=OrderStatus.PENDING,
        is_deleted=False,
        confirmation_deadline__lt=timezone.now(),
    ).exclude(
        payment_transactions__transaction_type="charge",
        payment_transactions__status=PaymentTransactionStatus.SUCCESS,
    ).select_related("buyer", "producer").prefetch_related("lines__product")

    for order in expired_orders:
        try:
            with transaction.atomic():
                current_order = Order.objects.select_for_update().get(pk=order.pk)
                if current_order.status != OrderStatus.PENDING:
                    continue

                for line in current_order.lines.select_related("product"):
                    product = Product.objects.select_for_update().get(
                        pk=line.product_id,
                    )
                    product.quantity = product.quantity + line.quantity
                    product.updated_by = current_order.buyer
                    product.save(
                        update_fields=["quantity", "updated_by", "updated_at"],
                    )

                current_order.status = OrderStatus.CANCELLED
                current_order.updated_by = current_order.buyer
                current_order.updated_at = timezone.now()
                current_order.save(update_fields=["status", "updated_by", "updated_at"])
                PaymentTransaction.objects.filter(
                    order=current_order,
                    status=PaymentTransactionStatus.PENDING,
                ).update(
                    status=PaymentTransactionStatus.CANCELLED,
                    processed_at=timezone.now(),
                )
                create_notification(
                    current_order.buyer,
                    "Commande annulée",
                    f"La commande {current_order.reference} a expiré et a été annulée.",
                    email_subject="Commande Farmio annulée",
                )
                create_notification(
                    current_order.producer,
                    "Commande annulée",
                    f"La commande {current_order.reference} a expiré et a été annulée.",
                    email_subject="Commande Farmio annulée",
                )
        except Order.DoesNotExist:
            logger.warning("Commande %s introuvable lors de l'autocancel", order.pk)
            continue

    return True
