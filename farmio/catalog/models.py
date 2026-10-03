from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from farmio.core.models import BaseModel
from farmio.utils.enums import ProductStatus
from farmio.utils.enums import ProductUnit
from farmio.utils.slugs import DbFunctions


class Category(BaseModel):
    """Catégorie de produits agricoles (ex : Légumes, Céréales, Fruits...)."""

    name = models.CharField(_("nom"), max_length=100)
    slug = models.SlugField(_("slug"), max_length=120, blank=True)
    description = models.TextField(_("description"), blank=True)

    class Meta:
        verbose_name = _("catégorie")
        verbose_name_plural = _("catégories")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(is_deleted=False),
                name="uniq_category_name_active",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(is_deleted=False),
                name="uniq_category_slug_active",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = DbFunctions.generate_unique_slug(self, self.name)
        super().save(*args, **kwargs)


class Product(BaseModel):
    """Produit agricole publié par un producteur"""

    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("producteur"),
        on_delete=models.CASCADE,
        related_name="products",
        limit_choices_to={"is_producer": True},
    )
    category = models.ForeignKey(
        Category,
        verbose_name=_("catégorie"),
        on_delete=models.PROTECT,
        related_name="products",
    )
    name = models.CharField(_("nom"), max_length=150)
    slug = models.SlugField(_("slug"), max_length=170, blank=True)
    description = models.TextField(_("description"), blank=True)
    price = MoneyField(
        _("prix unitaire"),
        max_digits=12,
        decimal_places=2,
        default_currency=settings.DEFAULT_CURRENCY,
    )
    quantity = models.PositiveIntegerField(_("quantité disponible"), default=0)
    unit = models.CharField(
        _("unité"),
        max_length=20,
        choices=ProductUnit.choices,
        default=ProductUnit.KG,
    )
    status = models.CharField(
        _("statut"),
        max_length=20,
        choices=ProductStatus.choices,
        default=ProductStatus.AVAILABLE,
    )

    class Meta:
        verbose_name = _("produit")
        verbose_name_plural = _("produits")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "status"]),
            models.Index(fields=["producer", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(is_deleted=False),
                name="uniq_product_slug_active",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} — {self.producer}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = DbFunctions.generate_unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("catalog:product-detail", kwargs={"slug": self.slug})

    @property
    def main_image(self):
        return self.images.filter(is_main=True).first() or self.images.first()


class ProductImage(BaseModel):
    """les images associé au produit que ça soit primaire ou secondaire"""

    product = models.ForeignKey(
        Product,
        verbose_name=_("produit"),
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(_("image"), upload_to="products/images/")
    is_main = models.BooleanField(_("image principale"), default=False)

    class Meta:
        verbose_name = _("image produit")
        verbose_name_plural = _("images produit")
        ordering = ["-is_main", "created_at"]

    def __str__(self) -> str:
        return f"Image de {self.product.name}"
