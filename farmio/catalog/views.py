"""Vues du catalogue """

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView

from farmio.catalog.permissions import ProductOwnerMixin
from farmio.users.permissions import ApprovedProducerRequiredMixin
from farmio.utils.enums import ProductStatus

from .forms import ProductForm
from .forms import ProductImageUploadForm
from .forms import ProductStockForm
from .models import Category
from .models import Product
from .models import ProductImage


# ==============================================================================
# CONSULTATION PUBLIQUE
# ==============================================================================
class ProductListView(ListView):
    """Catalogue public — produits recherchables et filtrables."""

    model = Product
    template_name = "catalog/pages/product_list.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        qs = (
            Product.objects.filter(is_deleted=False)
            .select_related("producer", "category", "producer__location")
            .prefetch_related("images")
        )

        query = self.request.GET.get("q", "").strip()
        category = self.request.GET.get("category")
        region = self.request.GET.get("region")
        min_price = self.request.GET.get("min_price")
        max_price = self.request.GET.get("max_price")
        availability = self.request.GET.get("availability")

        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(category__name__icontains=query)
                | Q(producer__name__icontains=query)
                | Q(producer__email__icontains=query),
            )

        if category:
            qs = qs.filter(category_id=category)

        if region:
            qs = qs.filter(producer__location__region__icontains=region)

        if min_price:
            qs = qs.filter(price__gte=min_price)

        if max_price:
            qs = qs.filter(price__lte=max_price)

        if availability:
            qs = qs.filter(status=availability)
        else:
            qs = qs.filter(status=ProductStatus.AVAILABLE)

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.filter(is_deleted=False).order_by("name")
        ctx["regions"] = (
            Product.objects.filter(is_deleted=False)
            .exclude(producer__location__region="")
            .exclude(producer__location__region__isnull=True)
            .values_list("producer__location__region", flat=True)
            .distinct()
            .order_by("producer__location__region")
        )
        ctx["selected_category"] = self.request.GET.get("category", "")
        ctx["selected_region"] = self.request.GET.get("region", "")
        ctx["selected_q"] = self.request.GET.get("q", "")
        ctx["selected_min_price"] = self.request.GET.get("min_price", "")
        ctx["selected_max_price"] = self.request.GET.get("max_price", "")
        ctx["selected_availability"] = self.request.GET.get("availability", "")
        ctx["active_filters"] = any(
            [
                ctx["selected_q"],
                ctx["selected_category"],
                ctx["selected_region"],
                ctx["selected_min_price"],
                ctx["selected_max_price"],
                ctx["selected_availability"],
            ],
        )
        return ctx


class ProductDetailView(DetailView):
    """Fiche produit publique, accessible via son slug."""

    model = Product
    template_name = "catalog/pages/product_detail.html"
    context_object_name = "product"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Product.objects.select_related("producer", "category").prefetch_related(
            "images",
        )


# ==============================================================================
# GESTION PRODUCTEUR
# ==============================================================================
class MyProductListView(LoginRequiredMixin, ApprovedProducerRequiredMixin, ListView):
    """Liste des produits du producteur connecté (accessible depuis le dashboard)."""

    template_name = "catalog/pages/product_list_mine.html"
    context_object_name = "products"
    paginate_by = 20

    def get_queryset(self):
        return (
            Product.objects.filter(producer=self.request.user)
            .select_related("category")
            .prefetch_related(
                "images",
            )
        )


class ProductCreateView(LoginRequiredMixin, ApprovedProducerRequiredMixin, CreateView):
    """Publication d'un nouveau produit, avec upload de plusieurs images en une fois."""

    model = Product
    form_class = ProductForm
    template_name = "catalog/pages/product_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("image_form", ProductImageUploadForm())
        ctx["is_update"] = False
        return ctx

    def form_valid(self, form):
        image_form = ProductImageUploadForm(self.request.POST, self.request.FILES)
        if not image_form.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, image_form=image_form),
            )

        # Rattache le produit au producteur connecté .
        form.instance.producer = self.request.user
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)

        _save_uploaded_images(self.object, image_form)
        messages.success(self.request, _("Produit publié avec succès."))
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


class ProductUpdateView(
    LoginRequiredMixin,
    ApprovedProducerRequiredMixin,
    ProductOwnerMixin,
    UpdateView,
):
    """Modification d'un produit existant"""

    model = Product
    form_class = ProductForm
    template_name = "catalog/pages/product_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("image_form", ProductImageUploadForm())
        ctx["is_update"] = True
        ctx["existing_images"] = self.object.images.all()
        return ctx

    def form_valid(self, form):
        image_form = ProductImageUploadForm(self.request.POST, self.request.FILES)
        if not image_form.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, image_form=image_form),
            )

        form.instance.updated_by = self.request.user
        response = super().form_valid(form)

        _save_uploaded_images(self.object, image_form, set_as_main_if_none=False)
        messages.success(self.request, _("Produit mis à jour."))
        return response

    def get_success_url(self):
        return self.object.get_absolute_url()


class ProductDeleteView(
    LoginRequiredMixin,
    ApprovedProducerRequiredMixin,
    ProductOwnerMixin,
    DeleteView,
):
    """Suppression d'un produit — suppression logique (soft-delete) via BaseModel."""

    model = Product
    template_name = "catalog/pages/product_confirm_delete.html"
    success_url = reverse_lazy("catalog:product-list-mine")

    def form_valid(self, form):
        # On n'appelle pas super().form_valid() (qui ferait un DELETE SQL réel) :
        # on utilise le soft-delete hérité de BaseModel pour garder l'historique.
        self.object = self.get_object()
        self.object.soft_delete(user=self.request.user)
        messages.success(self.request, _("Produit supprimé."))
        return HttpResponseRedirect(self.get_success_url())


class ProductStockUpdateView(
    LoginRequiredMixin,
    ApprovedProducerRequiredMixin,
    ProductOwnerMixin,
    UpdateView,
):
    """Mise à jour rapide de la quantité et du statut"""

    model = Product
    form_class = ProductStockForm
    template_name = "catalog/pages/product_stock_form.html"

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, _("Stock mis à jour."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("catalog:product-detail", kwargs={"slug": self.object.slug})


# ==============================================================================
# GESTION DES IMAGES (après publication)
# ==============================================================================
class ProductImageDeleteView(LoginRequiredMixin, ApprovedProducerRequiredMixin, View):
    """Supprime une image spécifique d'un produit — vérifie la propriété du produit."""

    def post(self, request, slug, image_id, *args, **kwargs):
        product = get_object_or_404(Product, slug=slug)
        if product.producer_id != request.user.pk:
            raise PermissionDenied

        image = get_object_or_404(ProductImage, pk=image_id, product=product)
        was_main = image.is_main
        image.soft_delete(user=request.user)

        # designation automatique d'une autre image principale
        if was_main:
            next_image = product.images.first()
            if next_image:
                next_image.is_main = True
                next_image.save(update_fields=["is_main"])

        messages.success(request, _("Image supprimée."))
        return redirect("catalog:product-update", slug=product.slug)


class ProductImageSetMainView(LoginRequiredMixin, ApprovedProducerRequiredMixin, View):
    """Définit une image existante comme image principale du produit."""

    def post(self, request, slug, image_id, *args, **kwargs):
        product = get_object_or_404(Product, slug=slug)
        if product.producer_id != request.user.pk:
            raise PermissionDenied

        product.images.update(is_main=False)
        image = get_object_or_404(ProductImage, pk=image_id, product=product)
        image.is_main = True
        image.save(update_fields=["is_main"])

        messages.success(request, _("Image principale mise à jour."))
        return redirect("catalog:product-update", slug=product.slug)


# ==============================================================================
# Fonction utilitaire interne — factorise l'enregistrement des images uploadées
# ==============================================================================
def _save_uploaded_images(
    product: Product,
    image_form: ProductImageUploadForm,
    *,
    set_as_main_if_none: bool = True,
) -> None:
    """Enregistre les fichiers reçus comme ProductImage, sans aucune compression.

    Le fichier dont l'index correspond à `main_image_index` devient l'image
    principale ; si aucun index n'est fourni et qu'il s'agit de la toute
    première image du produit, on la définit comme principale par défaut.
    """
    images = image_form.cleaned_data.get("images") or []
    main_index = image_form.cleaned_data.get("main_image_index")
    has_existing_main = product.images.filter(is_main=True).exists()

    for index, uploaded_file in enumerate(images):
        is_main = (index == main_index) if main_index is not None else False
        if (
            not has_existing_main
            and set_as_main_if_none
            and index == 0
            and main_index is None
        ):
            is_main = True

        ProductImage.objects.create(
            product=product,
            image=uploaded_file,
            is_main=is_main,
            created_by=product.updated_by,
            updated_by=product.updated_by,
        )
        if is_main:
            has_existing_main = True
