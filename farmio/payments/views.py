from __future__ import annotations

import logging

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from farmio.orders.models import Order
from farmio.payments.forms import PaymentChoiceForm
from farmio.payments.models import PaymentTransaction
from farmio.payments.services import PaymentError
from farmio.payments.services import cancel_pending_payment
from farmio.payments.services import process_stripe_event
from farmio.payments.services import start_mobile_money_intent
from farmio.payments.services import start_stripe_checkout
from farmio.users.permissions import BuyerRequiredMixin

logger = logging.getLogger(__name__)


class PaymentStartView(LoginRequiredMixin, BuyerRequiredMixin, View):
    template_name = "payments/payment_start.html"

    def get_order(self):
        return get_object_or_404(
            Order.objects.select_related("buyer", "producer").prefetch_related(
                "lines__product",
            ),
            pk=self.kwargs["pk"],
            buyer=self.request.user,
            is_deleted=False,
        )

    def get(self, request, *args, **kwargs):
        order = self.get_order()
        context = {
            "order": order,
            "form": PaymentChoiceForm(),
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "latest_payment": order.payment_transactions.first(),
        }
        return self.render(context)

    def post(self, request, *args, **kwargs):
        order = self.get_order()
        form = PaymentChoiceForm(request.POST)
        if not form.is_valid():
            return self.render(
                {
                    "order": order,
                    "form": form,
                    "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
                    "latest_payment": order.payment_transactions.first(),
                },
            )

        try:
            if form.cleaned_data["method"] == "stripe":
                success_url = (
                    request.build_absolute_uri(
                        reverse("payments:success", kwargs={"pk": order.pk}),
                    )
                    + "?session_id={CHECKOUT_SESSION_ID}"
                )
                cancel_url = request.build_absolute_uri(
                    reverse("payments:cancelled", kwargs={"pk": order.pk}),
                )
                _payment, checkout_url = start_stripe_checkout(
                    order.pk,
                    request.user,
                    success_url=success_url,
                    cancel_url=cancel_url,
                )
                return redirect(checkout_url)

            payment = start_mobile_money_intent(
                order.pk,
                request.user,
                form.cleaned_data["mobile_provider"],
            )
            return redirect(
                "payments:result",
                pk=order.pk,
                payment_id=payment.pk,
            )
        except PermissionDenied:
            raise
        except PaymentError as exc:
            messages.error(request, str(exc))
            return redirect("payments:start", pk=order.pk)

    def render(self, context):
        from django.shortcuts import render

        return render(self.request, self.template_name, context)


class PaymentResultView(LoginRequiredMixin, BuyerRequiredMixin, TemplateView):
	template_name = "payments/payment_result.html"

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		order = get_object_or_404(
			Order.objects.select_related("buyer", "producer").prefetch_related(
				"lines__product",
			),
			pk=self.kwargs["pk"],
			buyer=self.request.user,
			is_deleted=False,
		)
		payment_id = self.kwargs.get("payment_id") or self.request.GET.get("payment_id")
		payments = PaymentTransaction.objects.filter(order=order)
		if payment_id:
			payment = get_object_or_404(payments, pk=payment_id)
		else:
			payment = payments.first()
		session_id = self.request.GET.get("session_id")
		if session_id and payment and payment.provider_reference != session_id:
			raise PermissionDenied(_("Cette session de paiement ne correspond pas."))
		if (
			self.kwargs.get("result") == "cancelled"
			and payment
			and payment.provider == "stripe"
		):
			payment = cancel_pending_payment(payment.pk, self.request.user)
		context.update(
			{
				"order": order,
				"payment": payment,
				"is_success_return": self.kwargs.get("result") == "success",
			},
		)
		return context


class CancelPaymentView(LoginRequiredMixin, BuyerRequiredMixin, View):
	def post(self, request, pk, payment_id, *args, **kwargs):
		order = get_object_or_404(Order, pk=pk, buyer=request.user, is_deleted=False)
		get_object_or_404(PaymentTransaction, pk=payment_id, order=order)
		try:
			cancel_pending_payment(payment_id, request.user)
		except PermissionDenied:
			raise
		except PaymentError as exc:
			messages.error(request, str(exc))
		else:
			messages.info(request, _("La tentative de paiement a été annulée."))
		return redirect("orders:detail", pk=order.pk)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        signature = request.headers.get("Stripe-Signature", "")
        if not webhook_secret or not signature:
            return HttpResponseBadRequest("Missing Stripe signature configuration")
        try:
            event = stripe.Webhook.construct_event(
                request.body,
                signature,
                webhook_secret,
            )
        except (ValueError, stripe.SignatureVerificationError):
            logger.warning("Rejected Stripe webhook with invalid payload/signature")
            return HttpResponseBadRequest("Invalid webhook")
        try:
            process_stripe_event(event)
        except Exception:
            logger.exception("Stripe webhook processing failed")
            return HttpResponse(status=500)
        return HttpResponse(status=200)
