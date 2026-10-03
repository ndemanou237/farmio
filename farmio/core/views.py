from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.views.generic import TemplateView

from farmio.catalog.models import Category
from farmio.catalog.models import Product
from farmio.utils.enums import ProductStatus

User = get_user_model()


def csrf_failure(request, reason="", exception=None):
    """Vue affichée quand la validation CSRF échoue."""
    del exception
    return render(request, "errors/403_csrf.html", {"reason": reason}, status=403)


class HomeView(TemplateView):
    """Page d'accueil publique de la plateforme."""

    template_name = "common/pages/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["featured_products"] = (
            Product.objects.filter(
                is_deleted=False,
                status=ProductStatus.AVAILABLE,
            )
            .select_related("producer", "category", "producer__location")
            .prefetch_related("images")[:8]
        )
        ctx["categories"] = (
            Category.objects.filter(is_deleted=False)
            .order_by("name")[:8]
        )
        # Correction : Retrait du champ is_deleted sur User
        ctx["featured_producers"] = (
            User.objects.filter(
                is_producer=True,
                is_active=True,
                is_email_verified=True,
                is_approved=True,
            )
            .select_related("location", "producer_profile")[:6]
        )
        ctx["products_count"] = Product.objects.filter(is_deleted=False).count()
        ctx["suppliers_count"] = User.objects.filter(
            is_producer=True,
            is_approved=True,
            is_active=True,
        ).count()
        return ctx
