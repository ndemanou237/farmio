"""Vues des tableaux de bord — une vue dédiée par rôle (Acheteur, Producteur,
Administrateur), chacune protégée par les mixins RBAC de l'app users.
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Exists
from django.db.models import OuterRef
from django.views.generic import TemplateView

from farmio.cart.models import Cart
from farmio.dashboard.services import build_admin_dashboard_data
from farmio.orders.models import Order
from farmio.payments.models import PaymentTransaction
from farmio.users.permissions import AdminRequiredMixin
from farmio.users.permissions import ApprovedProducerRequiredMixin
from farmio.users.permissions import BuyerRequiredMixin
from farmio.utils.enums import CartStatus
from farmio.utils.enums import OrderStatus


class BuyerDashboardView(LoginRequiredMixin, BuyerRequiredMixin, TemplateView):
    """Tableau de bord Acheteur — vue d'ensemble de son activité sur la plateforme."""

    template_name = "dashboard/pages/buyer.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["buyer_profile"] = getattr(self.request.user, "buyer_profile", None)
        ctx["orders_count"] = Order.objects.filter(buyer=self.request.user).count()
        active_cart = Cart.objects.filter(
            buyer=self.request.user,
            status=CartStatus.ACTIVE,
            is_deleted=False,
        ).first()
        ctx["active_cart_count"] = (
            active_cart.items.filter(is_deleted=False).count() if active_cart else 0
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
        successful_charge = PaymentTransaction.objects.filter(
            order_id=OuterRef("pk"),
            status="success",
            transaction_type="charge",
        )
        ctx["orders_ready_to_start"] = Order.objects.filter(
            producer=self.request.user,
            status=OrderStatus.CONFIRMED,
            is_deleted=False,
        ).annotate(has_successful_charge=Exists(successful_charge)).filter(
            has_successful_charge=True,
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
        ctx.update(build_admin_dashboard_data())
        return ctx
