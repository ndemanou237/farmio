from django.urls import path

from farmio.payments import views

app_name = "payments"

urlpatterns = [
    path("orders/<uuid:pk>/pay/", views.PaymentStartView.as_view(), name="start"),
    path(
        "orders/<uuid:pk>/payment/success/",
        views.PaymentResultView.as_view(),
        {"result": "success"},
        name="success",
    ),
    path(
        "orders/<uuid:pk>/payment/cancelled/",
        views.PaymentResultView.as_view(),
        {"result": "cancelled"},
        name="cancelled",
    ),
    path(
        "orders/<uuid:pk>/payment/<uuid:payment_id>/",
        views.PaymentResultView.as_view(),
        name="result",
    ),
    path(
        "orders/<uuid:pk>/payment/<uuid:payment_id>/cancel/",
        views.CancelPaymentView.as_view(),
        name="cancel",
    ),
]
