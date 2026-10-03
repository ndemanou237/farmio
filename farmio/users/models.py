from __future__ import annotations

import secrets
from datetime import timedelta
from typing import ClassVar

from django.conf import settings
from django.conf import settings as dj_settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from farmio.core.models import BaseModel
from farmio.utils.enums import OtpPurpose
from farmio.utils.phone import normalize_phone_number
from farmio.utils.phone import validate_phone_number
from farmio.utils.slugs import DbFunctions

from .managers import UserManager


class Location(BaseModel):
    """Représente l'emplacement géographique d'un utilisateur ou d'une exploitation."""

    country = CountryField(_("pays"), default="CM")
    region = models.CharField(_("région"), max_length=100)
    city = models.CharField(_("ville"), max_length=100)

    class Meta:
        verbose_name = _("localisation")
        verbose_name_plural = _("localisations")
        unique_together = ("country", "region", "city")

    def __str__(self) -> str:
        return f"{self.city}, {self.region} ({self.country.name})"


class User(AbstractUser):
    """Modèle utilisateur personnalisé avec gestion multi-rôles et statuts booléens."""

    name = models.CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    email = models.EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]

    phone_number = models.CharField(
        _("numéro de téléphone"),
        max_length=20,
        blank=True,
        validators=[validate_phone_number],
    )

    is_producer = models.BooleanField(_("est producteur"), default=False)
    is_buyer = models.BooleanField(_("est acheteur"), default=True)
    is_email_verified = models.BooleanField(_("email vérifié"), default=False)
    is_approved = models.BooleanField(
        _("approuvé par l'admin"),
        default=False,
        help_text=_(
            "Requis pour que les producteurs puissent vendre sur la plateforme.",
        ),
    )

    location = models.ForeignKey(
        Location,
        verbose_name=_("localisation"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    stripe_customer_id = models.CharField(
        _("ID client Stripe"),
        max_length=255,
        blank=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()

    def save(self, *args, **kwargs):
        if self.phone_number:
            self.phone_number = normalize_phone_number(self.phone_number)
        super().save(*args, **kwargs)

    def get_full_name(self) -> str:
        """Retourne le nom affiché fiable pour les comptes sans first_name/last_name"""
        full_name = (self.name or "").strip()
        return full_name or self.email

    def get_short_name(self) -> str:
        """Nom court utilisé dans les petits espaces UI"""
        short_name = (self.name or "").strip()
        if short_name:
            return short_name
        return self.email.split("@", 1)[0] if self.email else "Utilisateur"

    def get_absolute_url(self) -> str:
        return reverse("users:detail", kwargs={"pk": self.id})

    def __str__(self) -> str:
        roles = []
        if self.is_producer:
            roles.append("Producteur")
        if self.is_buyer:
            roles.append("Acheteur")
        roles_str = ", ".join(roles) if roles else "Utilisateur"
        return f"{self.name or self.email} ({roles_str})"

    # --- Permissions et redirection ---
    @property
    def is_admin(self) -> bool:
        return self.is_staff or self.is_superuser

    @property
    def is_approved_producer(self) -> bool:
        return self.is_producer and self.is_approved and self.is_email_verified

    @property
    def can_sell(self) -> bool:
        return (
            self.is_producer
            and self.is_email_verified
            and self.is_approved
            and self.is_active
        )

    def get_post_login_redirect_url(self) -> str:
        """Redirection après authentification, selon rôles/statuts."""
        if self.is_admin:
            return "dashboard:admin"
        if not self.is_active:
            return "users:account_blocked"
        if self.is_producer and not self.is_approved:
            return "users:pending_approval"
        if self.is_producer:
            return "dashboard:producer"
        return "dashboard:buyer"


class ProducerProfile(BaseModel):
    """Informations professionnelles et état de validation des producteurs agricoles."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="producer_profile",
        limit_choices_to={"is_producer": True},
    )
    company_name = models.CharField(_("nom de l'entreprise"), max_length=150)
    slug = models.SlugField(_("slug"), max_length=170, unique=True, blank=True)
    business_registration_number = models.CharField(
        _("numéro d'immatriculation (RCCM/NIU)"),
        max_length=50,
        blank=True,
    )
    identity_number = models.CharField(
        _("numéro de pièce d'identité"),
        max_length=50,
        blank=True,
        help_text=_("Numéro de CNI, Passeport ou Récépissé."),
    )
    identity_document = models.FileField(
        _("document d'identité"),
        upload_to="producers/identity_documents/",
        blank=True,
        null=True,
        help_text=_("Scan ou photo de la pièce d'identité (PDF, JPG, PNG)."),
    )
    description = models.TextField(_("présentation de l'activité"), blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("examiné par"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_producers",
        limit_choices_to={"is_staff": True},
    )
    reviewed_at = models.DateTimeField(_("date d'examen"), null=True, blank=True)
    rejection_reason = models.TextField(_("motif de rejet"), blank=True)

    class Meta:
        verbose_name = _("profil producteur")
        verbose_name_plural = _("profils producteurs")

    def __str__(self) -> str:
        return self.company_name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = DbFunctions.generate_unique_slug(self, self.company_name)
        super().save(*args, **kwargs)


class BuyerProfile(BaseModel):
    """Correspond à `Acheteur` — OneToOne avec User."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buyer_profile",
        limit_choices_to={"is_buyer": True},
    )
    organization_name = models.CharField(
        _("nom de la structure (optionnel)"),
        max_length=150,
        blank=True,
    )

    class Meta:
        verbose_name = _("profil acheteur")
        verbose_name_plural = _("profils acheteurs")

    def __str__(self) -> str:
        return self.organization_name or str(self.user)


class OtpCode(BaseModel):
    """la gestion de l'otp d'un utilisateur"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("utilisateur"),
        on_delete=models.CASCADE,
        related_name="otp_codes",
    )
    code = models.CharField(_("code"), max_length=128)
    purpose = models.CharField(
        _("objectif"),
        max_length=20,
        choices=OtpPurpose.choices,
        default=OtpPurpose.EMAIL_VERIFICATION,
    )
    expires_at = models.DateTimeField(_("date d'expiration"))
    is_used = models.BooleanField(_("utilisé"), default=False)
    attempts = models.PositiveSmallIntegerField(_("tentatives"), default=0)

    class Meta:
        verbose_name = _("code OTP")
        verbose_name_plural = _("codes OTP")
        indexes = [models.Index(fields=["user", "purpose", "is_used"])]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"OTP — {self.user.email}"

    @classmethod
    def generate_for(
        cls,
        user,
        purpose: str = OtpPurpose.EMAIL_VERIFICATION,
    ) -> OtpCode:

        length = getattr(dj_settings, "OTP_CODE_LENGTH", 6)
        validity = getattr(dj_settings, "OTP_VALIDITY_MINUTES", 10)

        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(
            is_used=True,
        )

        code = "".join(secrets.choice("0123456789") for _ in range(length))
        otp = cls.objects.create(
            user=user,
            code=make_password(code),
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=validity),
        )
        otp.plaintext_code = code
        return otp

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def max_attempts_reached(self) -> bool:
        return self.attempts >= getattr(dj_settings, "OTP_MAX_ATTEMPTS", 5)

    def verify(self, submitted_code: str) -> tuple[bool, str]:
        with transaction.atomic():
            otp = type(self).objects.select_for_update().get(pk=self.pk)
            if otp.is_used:
                return False, str(_("Ce code a déjà été utilisé."))
            if otp.is_expired:
                return False, str(
                    _("Ce code a expiré, veuillez en demander un nouveau."),
                )
            if otp.max_attempts_reached:
                return False, str(_("Nombre maximal de tentatives atteint."))

            otp.attempts += 1
            if not check_password(submitted_code, otp.code):
                otp.save(update_fields=["attempts"])
                return False, str(_("Code incorrect."))

            otp.is_used = True
            otp.save(update_fields=["attempts", "is_used"])
            self.attempts = otp.attempts
            self.is_used = otp.is_used
            return True, ""
