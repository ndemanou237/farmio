from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from farmio.messaging.models import Conversation
from farmio.messaging.models import Message
from farmio.notifications.services import create_notification
from farmio.orders.models import Order
from farmio.utils.enums import OrderStatus

CONVERSATION_ORDER_STATUSES = (
    OrderStatus.CONFIRMED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.COMPLETED,
)


def _conversation_has_eligible_order(conversation: Conversation) -> bool:
    return Order.objects.filter(
        buyer_id=conversation.buyer_id,
        producer_id=conversation.producer_id,
        status__in=CONVERSATION_ORDER_STATUSES,
        is_deleted=False,
    ).exists()


def ensure_conversation_access(conversation: Conversation, user) -> None:
    if user.pk not in {conversation.buyer_id, conversation.producer_id}:
        raise PermissionDenied(_("Cette conversation ne vous appartient pas."))
    if not _conversation_has_eligible_order(conversation):
        raise PermissionDenied(
            _("La messagerie est disponible après confirmation d'une commande."),
        )


def get_or_create_conversation_for_order(order: Order, user) -> Conversation:
    if user.pk not in {order.buyer_id, order.producer_id}:
        raise PermissionDenied(_("Cette commande ne vous appartient pas."))
    if order.status not in CONVERSATION_ORDER_STATUSES:
        raise PermissionDenied(
            _("La messagerie est disponible après confirmation d'une commande."),
        )
    conversation, _created = Conversation.objects.get_or_create(
        buyer_id=order.buyer_id,
        producer_id=order.producer_id,
        defaults={"created_by": user, "updated_by": user},
    )
    return conversation


@transaction.atomic
def send_message(conversation: Conversation, author, content: str) -> Message:
    ensure_conversation_access(conversation, author)
    cleaned_content = content.strip()
    if not cleaned_content:
        raise ValueError(_("Le message ne peut pas être vide."))
    if len(cleaned_content) > 4000:
        raise ValueError(_("Le message dépasse la longueur maximale."))

    message = Message.objects.create(
        conversation=conversation,
        author=author,
        content=cleaned_content,
        created_by=author,
    )
    conversation.updated_by = author
    conversation.save(update_fields=["last_activity_at", "updated_by", "updated_at"])

    recipient = (
        conversation.producer if author.pk == conversation.buyer_id else conversation.buyer
    )
    create_notification(
        recipient,
        _("Nouveau message"),
        _("Vous avez reçu un nouveau message de %(sender)s.")
        % {"sender": author.get_full_name()},
        email_subject=_("Nouveau message Farmio"),
    )
    return message


def get_messages_after(conversation: Conversation, user, after_id: str | None = None):
    ensure_conversation_access(conversation, user)
    queryset = conversation.messages.select_related("author").order_by("created_at", "pk")
    if after_id:
        try:
            marker = queryset.get(pk=after_id)
        except (Message.DoesNotExist, ValueError):
            raise ValueError(_("Repère de message invalide.")) from None
        queryset = queryset.filter(created_at__gte=marker.created_at)
        messages = [
            message
            for message in queryset[:101]
            if (message.created_at, message.pk) > (marker.created_at, marker.pk)
        ][:100]
    else:
        messages = list(queryset.order_by("-created_at", "-pk")[:50])
        messages.reverse()

    conversation.messages.filter(is_read=False).exclude(author=user).update(is_read=True)
    return messages
