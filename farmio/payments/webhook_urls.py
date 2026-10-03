from django.urls import path

from farmio.payments.views import StripeWebhookView

urlpatterns = [path("", StripeWebhookView.as_view(), name="stripe-webhook")]
