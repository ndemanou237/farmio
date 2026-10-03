from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.money import Money

from farmio.cart.models import Cart
from farmio.cart.models import CartItem
from farmio.catalog.models import Product
from farmio.notifications.services import create_notification
from farmio.orders.models import Order
from farmio.orders.models import OrderLine
from farmio.utils.enums import CartStatus
from farmio.utils.enums import OrderStatus
from farmio.utils.enums import ProductStatus


class CartValidationError(ValueError):
    """Erreur métier utilisée pour l'annulation d'un panier invalide."""


class CartValidationService:
    """Valide et réserve le stock lors de la commande.

    Une commande est créée par producteur.
    """

    def __init__(self, buyer):
        self.buyer = buyer

    @transaction.atomic
    def validate(self):
        cart = (
            Cart.objects.filter(
                buyer=self.buyer,
                status=CartStatus.ACTIVE,
                is_deleted=False,
            )
            .select_for_update()
            .prefetch_related("items__product__producer", "items__product__category")
            .first()
        )

        if cart is None or not cart.items.filter(is_deleted=False).exists():
            raise CartValidationError(_("Votre panier est vide."))

        items = list(
            cart.items.filter(is_deleted=False)
            .select_related("product__producer", "product__category")
            .order_by(
                "product__producer__name",
                "product__name",
            ),
        )

        if not items:
            raise CartValidationError(_("Votre panier est vide."))

        products = list(
            Product.objects.select_for_update().filter(
                pk__in=[item.product_id for item in items],
                is_deleted=False,
            ).select_related(
                "producer",
            ).order_by("pk"),
        )
        product_by_id = {product.id: product for product in products}

        grouped_items = {}
        for item in items:
            product = product_by_id.get(item.product_id)
            if product is None:
                raise CartValidationError(
                    _("Un produit de votre panier n'existe plus."),
                )
            if product.producer_id == self.buyer.pk:
                raise PermissionDenied(
                    _("Vous ne pouvez pas réserver vos propres produits."),
                )
            if product.status != ProductStatus.AVAILABLE:
                raise CartValidationError(
                    _("Un produit du panier n'est plus disponible."),
                )
            if not product.producer.can_sell:
                raise CartValidationError(
                    _("Un producteur du panier n'est plus autorisé à vendre."),
                )
            if product.quantity < item.quantity:
                raise CartValidationError(
                    _("Le stock disponible pour %s est insuffisant.") % product.name,
                )
            grouped_items.setdefault(product.producer_id, []).append((product, item))

        created_orders = []
        for grouped in grouped_items.values():
            producer = grouped[0][0].producer
            order = Order.objects.create(
                buyer=self.buyer,
                producer=producer,
                status=OrderStatus.PENDING,
                total_amount=Money(0, settings.DEFAULT_CURRENCY),
                pickup_location="",
                created_by=self.buyer,
                updated_by=self.buyer,
            )

            total_cents = Decimal("0")
            for _product, item in grouped:
                existing_product = product_by_id[item.product_id]
                existing_product.quantity = (
                    existing_product.quantity - item.quantity
                )
                existing_product.updated_by = self.buyer
                existing_product.save(
                    update_fields=["quantity", "updated_by", "updated_at"],
                )

                OrderLine.objects.create(
                    order=order,
                    product=existing_product,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    created_by=self.buyer,
                    updated_by=self.buyer,
                )
                total_cents += Decimal(str(item.unit_price.amount)) * item.quantity

            order.total_amount = Money(str(total_cents), settings.DEFAULT_CURRENCY)
            order.updated_by = self.buyer
            order.updated_at = timezone.now()
            order.save(update_fields=["total_amount", "updated_by", "updated_at"])
            create_notification(
                self.buyer,
                _("Commande créée"),
                _("Votre commande %(reference)s a été transmise au producteur.")
                % {"reference": order.reference},
                email_subject=_("Votre commande Farmio a été créée"),
            )
            create_notification(
                producer,
                _("Nouvelle commande"),
                _("Une nouvelle commande %(reference)s attend votre réponse.")
                % {"reference": order.reference},
                email_subject=_("Vous avez reçu une commande Farmio"),
            )
            created_orders.append(order)

        CartItem.objects.filter(cart=cart, is_deleted=False).update(
            is_deleted=True,
            updated_by=self.buyer,
            updated_at=timezone.now(),
        )
        cart.status = CartStatus.VALIDATED
        cart.updated_by = self.buyer
        cart.updated_at = timezone.now()
        cart.save(update_fields=["status", "updated_by", "updated_at"])

        return created_orders
