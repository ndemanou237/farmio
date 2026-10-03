from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from farmio.core.managers import AllObjectsManager
from farmio.core.managers import SoftDeleteManager
from farmio.utils.enums import SecurityEventType

if TYPE_CHECKING:
    from farmio.users.models import User


class BaseModel(models.Model):
    """Modèle de base abstrait fournissant un ID UUID, l'horodatage,

    l'audit d'auteur et la suppression logique (soft-delete).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name=_("Date de création"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        verbose_name=_("Créé par"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        verbose_name=_("Dernière modification"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
        verbose_name=_("Modifié par"),
    )
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_("Supprimé ?"),
        help_text=_(
            "Indique si l'enregistrement est désactivé sans être supprimé de la BDD.",
        ),
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.__class__.__name__} ({self.pk})"

    def soft_delete(self, user: User | None = None) -> None:
        self.is_deleted = True
        self.updated_by = user
        self.save(update_fields=["is_deleted", "updated_by", "updated_at"])

    def restore(self, user: User | None = None) -> None:
        self.is_deleted = False
        self.updated_by = user
        self.save(update_fields=["is_deleted", "updated_by", "updated_at"])


class SecurityEventLog(BaseModel):
    """Table d'audit des événements de sécurité (connexions, OTP, mots de passe...)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("utilisateur"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
        help_text=_(
            "Vide pour les événements pré-authentification (ex: échec de connexion).",
        ),
    )
    email = models.EmailField(_("email concerné"), blank=True)
    event_type = models.CharField(
        _("type d'événement"),
        max_length=40,
        choices=SecurityEventType.choices,
    )
    ip_address = models.GenericIPAddressField(_("adresse IP"), null=True, blank=True)
    user_agent = models.CharField(_("user agent"), max_length=255, blank=True)
    metadata = models.JSONField(_("métadonnées"), default=dict, blank=True)

    class Meta:
        verbose_name = _("événement de sécurité")
        verbose_name_plural = _("événements de sécurité")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["event_type", "created_at"])]

    def __str__(self) -> str:
        return f"{self.get_event_type_display()} — {self.email or self.user}"
