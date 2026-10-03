from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from farmio.cart.models import Cart
from farmio.cart.models import CartItem
from farmio.catalog.models import Product
from farmio.utils.enums import CartStatus


def get_or_create_active_cart(buyer: Any) -> Cart:
    """Renvoie le panier actif de l'acheteur, sans créer de panier supplémentaire."""
    cart = (
        Cart.objects.filter(
            buyer=buyer,
            status=CartStatus.ACTIVE,
            is_deleted=False,
        )
        .select_related("buyer")
        .first()
    )
    if cart is not None:
        return cart
    return Cart.objects.create(buyer=buyer, status=CartStatus.ACTIVE, created_by=buyer)


def get_cart_items_for_display(cart: Cart):
    return (
        cart.items.filter(is_deleted=False)
        .select_related("product__producer__location", "product__category")
        .prefetch_related("product__images")
        .order_by("product__producer__name", "product__name")
    )


@transaction.atomic
def add_product_to_cart(
    buyer: Any,
    product_id: str | Any,
    quantity: int = 1,
) -> CartItem:
    """Ajoute un produit au panier sans modifier le stock réel."""
    if quantity <= 0:
        raise ValidationError(_("La quantité doit être supérieure à 0."))

    product = (
        Product.objects.filter(pk=product_id, is_deleted=False)
        .select_related("producer", "category")
        .first()
    )
    if product is None:
        raise ValidationError(_("Produit introuvable."))
    if product.producer_id == buyer.pk:
        raise ValidationError(_("Vous ne pouvez pas commander vos propres produits."))
    if product.status != "AVAILABLE":
        raise ValidationError(_("Ce produit n'est pas disponible pour le moment."))
    if not product.producer.can_sell:
        raise ValidationError(_("Ce producteur n'est pas autorisé à vendre."))
    if product.quantity < quantity:
        raise ValidationError(
            _("Quantité demandée supérieure à la disponibilité du produit (%s).")
            % product.quantity,
        )

    cart = get_or_create_active_cart(buyer)
    item = (
        cart.items.filter(product=product, is_deleted=False)
        .select_related("product")
        .first()
    )
    if item is None:
        item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=quantity,
            unit_price=product.price,
            created_by=buyer,
        )
    else:
        new_qty = item.quantity + quantity
        if new_qty > product.quantity:
            raise ValidationError(
                _(
                    "Quantité demandée supérieure à la disponibilité du produit (%s).",
                )
                % product.quantity,
            )
        item.quantity = new_qty
        item.unit_price = product.price
        item.updated_by = buyer
        item.updated_at = timezone.now()
        item.save(update_fields=["quantity", "unit_price", "updated_by", "updated_at"])

    return item


@transaction.atomic
def update_cart_item_quantity(
    buyer: Any,
    cart_item_id: str | Any,
    quantity: int,
) -> CartItem:
    """Met à jour la quantité d'un article du panier sans toucher au stock réel."""
    if quantity <= 0:
        raise ValidationError(_("La quantité doit être supérieure à 0."))

    cart = get_or_create_active_cart(buyer)
    item = (
        cart.items.filter(pk=cart_item_id, is_deleted=False)
        .select_related("product")
        .first()
    )
    if item is None:
        raise ValidationError(_("Article introuvable dans votre panier."))
    if item.product.quantity < quantity:
        raise ValidationError(
            _("La quantité demandée dépasse la quantité disponible (%s).")
            % item.product.quantity,
        )

    item.quantity = quantity
    item.unit_price = item.product.price
    item.updated_by = buyer
    item.updated_at = timezone.now()
    item.save(update_fields=["quantity", "unit_price", "updated_by", "updated_at"])
    return item


@transaction.atomic
def remove_cart_item(buyer: Any, cart_item_id: str | Any) -> None:
    cart = get_or_create_active_cart(buyer)
    item = cart.items.filter(pk=cart_item_id, is_deleted=False).first()
    if item is None:
        raise ValidationError(_("Article introuvable dans votre panier."))
    item.is_deleted = True
    item.updated_by = buyer
    item.updated_at = timezone.now()
    item.save(update_fields=["is_deleted", "updated_by", "updated_at"])


@transaction.atomic
def clear_cart(buyer: Any) -> None:
    cart = get_or_create_active_cart(buyer)
    cart.items.filter(is_deleted=False).update(
        is_deleted=True,
        updated_by=buyer,
        updated_at=timezone.now(),
    )
    cart.status = CartStatus.EMPTY
    cart.updated_by = buyer
    cart.updated_at = timezone.now()
    cart.save(update_fields=["status", "updated_by", "updated_at"])


def cart_grouped_by_producer(cart: Cart):
    grouped = {}
    for item in get_cart_items_for_display(cart):
        producer = item.product.producer
        grouped.setdefault(
            producer.id,
            {
                "producer": producer,
                "items": [],
                "total": 0,
            },
        )
        grouped[producer.id]["items"].append(item)
        grouped[producer.id]["total"] += item.subtotal.amount
    return grouped.values()
