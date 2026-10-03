from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView
from djmoney.money import Money

from farmio.cart.services import add_product_to_cart
from farmio.cart.services import clear_cart
from farmio.cart.services import get_cart_items_for_display
from farmio.cart.services import get_or_create_active_cart
from farmio.cart.services import remove_cart_item
from farmio.cart.services import update_cart_item_quantity
from farmio.users.permissions import BuyerRequiredMixin


class CartDetailView(LoginRequiredMixin, BuyerRequiredMixin, TemplateView):
    """Vue publique du panier de l'acheteur, affiché par producteur."""

    template_name = "cart/cart_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cart = get_or_create_active_cart(self.request.user)
        items = list(get_cart_items_for_display(cart))

        grouped = {}
        total = Decimal("0")
        for item in items:
            producer_id = str(item.product.producer_id)
            grouped.setdefault(
                producer_id,
                {
                    "producer": item.product.producer,
                    "items": [],
                    "total": Money("0", settings.DEFAULT_CURRENCY),
                },
            )
            grouped[producer_id]["items"].append(item)
            grouped[producer_id]["total"] = (
                grouped[producer_id]["total"] + item.subtotal
            )
            total += item.subtotal.amount

        ctx["cart"] = cart
        ctx["items"] = items
        ctx["grouped_items"] = grouped.values()
        ctx["total"] = Money(str(total), settings.DEFAULT_CURRENCY)
        ctx["is_empty"] = not items
        return ctx


class AddToCartView(LoginRequiredMixin, BuyerRequiredMixin, View):
    """Ajoute un produit au panier."""

    def post(self, request, *args, **kwargs):
        try:
            product_id = request.POST.get("product_id")
            quantity = int(request.POST.get("quantity", 1) or 1)
            if not product_id:
                messages.error(request, _("Produit introuvable."))
                return redirect(request.POST.get("next") or "catalog:product-list")
            add_product_to_cart(request.user, product_id, quantity)
            messages.success(request, _("Produit ajouté au panier."))
        except (ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(request.POST.get("next") or "catalog:product-list")


class UpdateCartItemView(LoginRequiredMixin, BuyerRequiredMixin, View):
    """Met à jour la quantité d'un article du panier."""

    def post(self, request, *args, **kwargs):
        item_id = self.kwargs.get("item_id")
        try:
            quantity = int(request.POST.get("quantity", 1) or 1)
            update_cart_item_quantity(request.user, item_id, quantity)
            messages.success(request, _("Quantité mise à jour."))
        except (ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect("cart:detail")


class RemoveCartItemView(LoginRequiredMixin, BuyerRequiredMixin, View):
    """Supprime un article du panier."""

    def post(self, request, *args, **kwargs):
        item_id = self.kwargs.get("item_id")
        try:
            remove_cart_item(request.user, item_id)
            messages.success(request, _("Article supprimé du panier."))
        except ValidationError as exc:
            messages.error(request, str(exc))
        return redirect("cart:detail")


class ClearCartView(LoginRequiredMixin, BuyerRequiredMixin, View):
    """Vide le panier actif."""

    def post(self, request, *args, **kwargs):
        try:
            clear_cart(request.user)
            messages.success(request, _("Votre panier a été vidé."))
        except ValidationError as exc:
            messages.error(request, str(exc))
        return redirect("cart:detail")
