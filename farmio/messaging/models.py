from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from farmio.core.models import BaseModel


class Conversation(BaseModel):
    """Échange entre un acheteur et un producteur"""

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("acheteur"),
        on_delete=models.CASCADE,
        related_name="conversations_as_buyer",
        limit_choices_to={"is_buyer": True},
    )
    producer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("producteur"),
        on_delete=models.CASCADE,
        related_name="conversations_as_producer",
        limit_choices_to={"is_producer": True},
    )
    last_activity_at = models.DateTimeField(_("dernière activité"), auto_now=True)

    class Meta:
        verbose_name = _("conversation")
        verbose_name_plural = _("conversations")
        ordering = ["-last_activity_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["buyer", "producer"],
                condition=Q(is_deleted=False),
                name="uniq_conversation_pair_active",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.buyer} ↔ {self.producer}"


class Message(BaseModel):
    """Message échangé au sein d'une conversation."""

    conversation = models.ForeignKey(
        Conversation,
        verbose_name=_("conversation"),
        on_delete=models.CASCADE,
        related_name="messages",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("auteur"),
        on_delete=models.CASCADE,
        related_name="messages_sent",
    )
    content = models.TextField(_("contenu"))
    is_read = models.BooleanField(_("lu"), default=False)

    class Meta:
        verbose_name = _("message")
        verbose_name_plural = _("messages")
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Message de {self.author} — {self.created_at:%d/%m/%Y %H:%M}"
