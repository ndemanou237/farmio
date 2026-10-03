from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.OrderListView.as_view(), name="list"),
    path("validate/", views.ValidateCartOrderView.as_view(), name="validate-cart"),
    path("<uuid:pk>/", views.OrderDetailView.as_view(), name="detail"),
    path("<uuid:pk>/confirm/", views.OrderConfirmView.as_view(), name="confirm"),
    path("<uuid:pk>/refuse/", views.OrderRefuseView.as_view(), name="refuse"),
    path(
        "<uuid:pk>/confirm-receipt/",
        views.OrderReceiptConfirmView.as_view(),
        name="confirm-receipt",
    ),
]
