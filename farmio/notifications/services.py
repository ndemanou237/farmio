from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction

from farmio.notifications.models import Notification

if TYPE_CHECKING:
    from farmio.users.models import User

logger = logging.getLogger(__name__)


def _enqueue_notification_email(notification_id: str, subject: str) -> None:
    try:
        from farmio.notifications.tasks import send_notification_email_task

        send_notification_email_task.delay(notification_id, subject)
    except Exception:
        logger.exception("Unable to enqueue notification email %s", notification_id)


def create_notification(
    user: User,
    title: str,
    message: str,
    *,
    email_subject: str | None = None,
) -> Notification:
    """Persist an in-app notification and optionally queue its email after commit."""
    notification = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        created_by=user,
    )
    if email_subject:
        transaction.on_commit(
            lambda notification_id=str(notification.pk), subject=str(email_subject): _enqueue_notification_email(
                notification_id,
                subject,
            ),
        )
    return notification
