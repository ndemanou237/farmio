from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from farmio.core.models import BaseModel


class Notification(BaseModel):
    """Alerte in-app liée à un événement """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("utilisateur"),
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(_("titre"), max_length=150)
    message = models.TextField(_("message"))
    is_read = models.BooleanField(_("lu"), default=False)

    class Meta:
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title
