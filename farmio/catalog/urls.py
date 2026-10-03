from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    # Gestion producteur (Routes spécifiques à placer AVANT le slug)
    path("products/mine/", views.MyProductListView.as_view(), name="product-list-mine"),
    path("products/create/", views.ProductCreateView.as_view(), name="product-create"),
    # Consultation publique
    path("products/", views.ProductListView.as_view(), name="product-list"),
    # Consultation détail (Route dynamique en dernier)
    path(
        "products/<slug:slug>/",
        views.ProductDetailView.as_view(),
        name="product-detail",
    ),
    path(
        "products/<slug:slug>/edit/",
        views.ProductUpdateView.as_view(),
        name="product-update",
    ),
    path(
        "products/<slug:slug>/delete/",
        views.ProductDeleteView.as_view(),
        name="product-delete",
    ),
    path(
        "products/<slug:slug>/stock/",
        views.ProductStockUpdateView.as_view(),
        name="product-stock-update",
    ),
    # Gestion des images
    path(
        "products/<slug:slug>/images/<uuid:image_id>/delete/",
        views.ProductImageDeleteView.as_view(),
        name="product-image-delete",
    ),
    path(
        "products/<slug:slug>/images/<uuid:image_id>/set-main/",
        views.ProductImageSetMainView.as_view(),
        name="product-image-set-main",
    ),
]
