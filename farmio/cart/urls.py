from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.CartDetailView.as_view(), name="detail"),
    path("add/", views.AddToCartView.as_view(), name="add"),
    path(
        "update/<uuid:item_id>/",
        views.UpdateCartItemView.as_view(),
        name="update-item",
    ),
    path(
        "remove/<uuid:item_id>/",
        views.RemoveCartItemView.as_view(),
        name="remove-item",
    ),
    path("clear/", views.ClearCartView.as_view(), name="clear"),
]
