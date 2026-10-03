from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Category
from .models import Product
from .models import ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ["image", "is_main"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name"]
    prepopulated_fields = {}  # le slug est généré automatiquement dans save()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "producer",
        "category",
        "price",
        "quantity",
        "unit",
        "status",
        "created_at",
    ]
    list_filter = ["status", "category", "unit"]
    search_fields = ["name", "producer__email", "producer__name"]
    autocomplete_fields = ["producer", "category"]
    inlines = [ProductImageInline]

    actions = ["mark_available", "mark_unavailable"]

    @admin.action(description=_("Marquer comme disponible"))
    def mark_available(self, request, queryset):
        queryset.update(status="AVAILABLE")

    @admin.action(description=_("Marquer comme indisponible"))
    def mark_unavailable(self, request, queryset):
        queryset.update(status="UNAVAILABLE")
