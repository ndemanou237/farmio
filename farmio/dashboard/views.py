"""Vues des tableaux de bord — une vue dédiée par rôle (Acheteur, Producteur,
Administrateur), chacune protégée par les mixins RBAC de l'app users.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView

from farmio.cart.models import Cart
from farmio.catalog.models import Product
from farmio.orders.models import Order
from farmio.users.models import ProducerProfile
from farmio.users.permissions import AdminRequiredMixin
from farmio.users.permissions import ApprovedProducerRequiredMixin
from farmio.users.permissions import BuyerRequiredMixin
from farmio.utils.enums import CartStatus
from farmio.utils.enums import OrderStatus

User = get_user_model()


class BuyerDashboardView(LoginRequiredMixin, BuyerRequiredMixin, TemplateView):
    """Tableau de bord Acheteur — vue d'ensemble de son activité sur la plateforme."""

    template_name = "dashboard/pages/buyer.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["buyer_profile"] = getattr(self.request.user, "buyer_profile", None)
        ctx["orders_count"] = Order.objects.filter(buyer=self.request.user).count()
        ctx["active_cart_count"] = (
            Cart.objects.filter(
                buyer=self.request.user,
                status=CartStatus.ACTIVE,
                is_deleted=False,
            )
            .first()
            .items.filter(is_deleted=False).count()
            if Cart.objects.filter(
                buyer=self.request.user,
                status=CartStatus.ACTIVE,
                is_deleted=False,
            ).exists()
            else 0
        )
        ctx["recent_orders"] = Order.objects.filter(
            buyer=self.request.user,
        ).select_related("producer")[:3]
        return ctx


class ProducerDashboardView(
    LoginRequiredMixin,
    ApprovedProducerRequiredMixin,
    TemplateView,
):
    """Tableau de bord Producteur — accessible uniquement aux producteurs approuvés."""

    template_name = "dashboard/pages/producer_overview.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["producer_profile"] = getattr(self.request.user, "producer_profile", None)
        ctx["products_count"] = self.request.user.products.filter(
            is_deleted=False,
        ).count()
        ctx["pending_orders_count"] = Order.objects.filter(
            producer=self.request.user,
            status__in=[
                OrderStatus.PENDING,
                OrderStatus.CONFIRMED,
                OrderStatus.IN_PROGRESS,
            ],
        ).count()
        ctx["recent_orders"] = Order.objects.filter(
            producer=self.request.user,
        ).select_related("buyer")[:3]
        return ctx


class AdminDashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Tableau de bord Administrateur — supervision globale de la plateforme."""

    template_name = "dashboard/pages/admin.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pending_producers_count"] = ProducerProfile.objects.filter(
            user__is_producer=True,
            user__is_email_verified=True,
            user__is_approved=False,
        ).count()
        ctx["buyers_count"] = self.request.user.__class__.objects.filter(
            is_buyer=True,
            is_active=True,
        ).count()
        ctx["producers_count"] = self.request.user.__class__.objects.filter(
            is_producer=True,
            is_active=True,
        ).count()
        ctx["users_count"] = User.objects.filter(is_active=True).count()
        ctx["orders_today_count"] = Order.objects.filter(
            created_at__date=timezone.localdate(),
        ).count()
        ctx["products_count"] = Product.objects.filter(is_deleted=False).count()
        return ctx
