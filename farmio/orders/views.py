from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView
from django.views.generic import ListView

from farmio.catalog.models import Product
from farmio.notifications.services import create_notification
from farmio.orders.models import Order
from farmio.orders.services import CartValidationError
from farmio.orders.services import CartValidationService
from farmio.payments.models import PaymentTransaction
from farmio.reviews.forms import ReviewForm
from farmio.reviews.models import Review
from farmio.users.permissions import ApprovedProducerRequiredMixin
from farmio.users.permissions import BuyerRequiredMixin
from farmio.utils.enums import OrderStatus


class OrderListView(LoginRequiredMixin, ListView):
    """Liste des commandes de l'utilisateur selon son rôle."""

    model = Order
    template_name = "orders/order_list.html"
    context_object_name = "orders"
    paginate_by = 12

    def get_queryset(self):
        qs = (
            Order.objects.select_related("buyer", "producer")
            .prefetch_related("lines__product")
        )
        if self.request.user.is_buyer and self.request.user.is_producer:
            return qs.filter(
                Q(buyer=self.request.user) | Q(producer=self.request.user),
            ).order_by("-created_at")
        if self.request.user.is_buyer:
            return qs.filter(buyer=self.request.user).order_by("-created_at")
        if self.request.user.is_producer:
            return qs.filter(producer=self.request.user).order_by("-created_at")
        return qs.none()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["order_statuses"] = OrderStatus.choices
        return ctx


class OrderDetailView(LoginRequiredMixin, DetailView):
    """Détail d'une commande avec vérification du propriétaire."""

    model = Order
    template_name = "orders/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return Order.objects.select_related(
            "buyer",
            "producer",
            "buyer__buyer_profile",
            "producer__producer_profile",
        ).prefetch_related("lines__product")

    def dispatch(self, request, *args, **kwargs):
        order = self.get_object()
        if request.user.pk not in {order.buyer_id, order.producer_id}:
            raise PermissionDenied(
                _("Vous n'êtes pas autorisé à consulter cette commande."),
            )
        self.object = order
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_start_order"] = (
            self.request.user.pk == self.object.producer_id
            and self.object.status == OrderStatus.CONFIRMED
            and PaymentTransaction.objects.filter(
                order=self.object,
                status="success",
                transaction_type="charge",
            ).exists()
        )
        if self.request.user.pk == self.object.buyer_id:
            context["existing_review"] = Review.objects.filter(
                order=self.object,
                buyer=self.request.user,
            ).select_related("moderation").first()
            context["review_form"] = ReviewForm()
        return context


class ValidateCartOrderView(LoginRequiredMixin, BuyerRequiredMixin, View):
    """Valide le panier actif et crée une commande par producteur."""

    def post(self, request, *args, **kwargs):
        try:
            service = CartValidationService(request.user)
            orders = service.validate()
            messages.success(
                request,
                _("Votre panier a été validé. %s commande(s) créée(s).") % len(orders),
            )
        except (CartValidationError, ValueError) as exc:
            messages.error(request, str(exc))
            return redirect("cart:detail")
        return redirect("orders:list")


class OrderConfirmView(LoginRequiredMixin, ApprovedProducerRequiredMixin, View):
    """Confirme une commande en attente pour le producteur."""

    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            order = Order.objects.select_for_update().select_related(
                "producer",
                "buyer",
            ).get(pk=self.kwargs["pk"])
        if order.producer_id != request.user.pk:
            raise PermissionDenied(
                _("Vous ne pouvez confirmer que vos propres commandes."),
            )
        if order.status != OrderStatus.PENDING:
            messages.error(request, _("Cette commande n'est plus en attente."))
            return redirect("orders:detail", pk=order.pk)
        with transaction.atomic():
            order = Order.objects.select_for_update().select_related("buyer").get(
                pk=order.pk,
            )
            if order.status != OrderStatus.PENDING:
                messages.error(request, _("Cette commande n'est plus en attente."))
                return redirect("orders:detail", pk=order.pk)
            if PaymentTransaction.objects.filter(
                order=order,
                status="success",
                transaction_type="charge",
            ).exists():
                messages.error(
                    request,
                    _("Une commande payée ne peut pas être refusée ici."),
                )
                return redirect("orders:detail", pk=order.pk)
            order.status = OrderStatus.CONFIRMED
            order.confirmed_at = timezone.now()
            order.updated_by = request.user
            order.save(
                update_fields=["status", "confirmed_at", "updated_by", "updated_at"],
            )
            create_notification(
                order.buyer,
                _("Commande confirmée"),
                _("Le producteur a confirmé la commande %(reference)s.")
                % {"reference": order.reference},
                email_subject=_("Votre commande Farmio est confirmée"),
            )
        messages.success(request, _("Commande confirmée."))
        return redirect("orders:detail", pk=order.pk)


class OrderRefuseView(LoginRequiredMixin, ApprovedProducerRequiredMixin, View):
    """Refuse une commande en attente pour le producteur."""

    def post(self, request, *args, **kwargs):
        order = Order.objects.select_related("producer", "buyer").get(
            pk=self.kwargs["pk"],
        )
        if order.producer_id != request.user.pk:
            raise PermissionDenied(
                _("Vous ne pouvez refuser que vos propres commandes."),
            )
        if order.status != OrderStatus.PENDING:
            messages.error(request, _("Cette commande n'est plus en attente."))
            return redirect("orders:detail", pk=order.pk)

        with transaction.atomic():
            order = Order.objects.select_for_update().select_related("buyer").get(
                pk=order.pk,
            )
            if order.status != OrderStatus.PENDING:
                messages.error(request, _("Cette commande n'est plus en attente."))
                return redirect("orders:detail", pk=order.pk)
            for line in order.lines.select_related("product").order_by("product_id"):
                product = Product.objects.select_for_update().get(pk=line.product_id)
                product.quantity = product.quantity + line.quantity
                product.updated_by = request.user
                product.save(update_fields=["quantity", "updated_by", "updated_at"])

            order.status = OrderStatus.REFUSED
            order.updated_by = request.user
            order.save(update_fields=["status", "updated_by", "updated_at"])
            create_notification(
                order.buyer,
                _("Commande refusée"),
                _("Le producteur a refusé la commande %(reference)s.")
                % {"reference": order.reference},
                email_subject=_("Mise à jour de votre commande Farmio"),
            )
        messages.success(request, _("Commande refusée."))
        return redirect("orders:detail", pk=order.pk)


class OrderStartView(LoginRequiredMixin, ApprovedProducerRequiredMixin, View):
    """Mark a confirmed, paid order as in progress for its producer."""

    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().select_related("buyer").get(
                    pk=self.kwargs["pk"],
                    is_deleted=False,
                )
            except Order.DoesNotExist as exc:
                raise Http404 from exc
            if order.producer_id != request.user.pk:
                raise PermissionDenied(
                    _("Vous ne pouvez traiter que vos propres commandes."),
                )
            if order.status != OrderStatus.CONFIRMED:
                messages.error(
                    request,
                    _("Cette commande ne peut pas passer en préparation."),
                )
                return redirect("orders:detail", pk=order.pk)
            is_paid = PaymentTransaction.objects.filter(
                order=order,
                status="success",
                transaction_type="charge",
            ).exists()
            if not is_paid:
                messages.error(
                    request,
                    _("Le paiement confirmé est requis avant la préparation."),
                )
                return redirect("orders:detail", pk=order.pk)
            order.status = OrderStatus.IN_PROGRESS
            order.updated_by = request.user
            order.save(update_fields=["status", "updated_by", "updated_at"])
            create_notification(
                order.buyer,
                _("Commande en préparation"),
                _("La commande %(reference)s est en cours de préparation.")
                % {"reference": order.reference},
                email_subject=_("Mise à jour de votre commande Farmio"),
            )
        messages.success(request, _("La commande est maintenant en préparation."))
        return redirect("orders:detail", pk=order.pk)


class OrderReceiptConfirmView(LoginRequiredMixin, BuyerRequiredMixin, View):
    """Confirm that the buyer received an order currently in progress."""

    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            order = Order.objects.select_for_update().select_related("producer").get(
                pk=self.kwargs["pk"],
                buyer=request.user,
            )
            if order.status != OrderStatus.IN_PROGRESS:
                messages.error(request, _("Cette commande ne peut pas être confirmée."))
                return redirect("orders:detail", pk=order.pk)
            order.status = OrderStatus.COMPLETED
            order.updated_by = request.user
            order.save(update_fields=["status", "updated_by", "updated_at"])
            create_notification(
                order.producer,
                _("Réception confirmée"),
                _("L'acheteur a confirmé la réception de la commande %(reference)s.")
                % {"reference": order.reference},
                email_subject=_("Réception de commande confirmée sur Farmio"),
            )
        messages.success(request, _("Réception de la commande confirmée."))
        return redirect("orders:detail", pk=order.pk)
