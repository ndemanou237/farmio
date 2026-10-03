from __future__ import annotations

import logging

from celery import shared_task

from farmio.notifications.models import Notification
from farmio.utils.email import EmailUtil

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_notification_email_task(self, notification_id: str, subject: str) -> bool:
    try:
        notification = Notification.objects.select_related("user").get(
            pk=notification_id,
        )
    except Notification.DoesNotExist:
        logger.info("Notification %s disappeared before email delivery", notification_id)
        return False

    sent = EmailUtil.send_email_with_template(
        template="emails/notification_email.html",
        context={
            "full_name": notification.user.get_full_name(),
            "title": notification.title,
            "message": notification.message,
            "notification_url": "",
        },
        receivers=[notification.user.email],
        subject=subject,
    )
    if not sent:
        raise self.retry(exc=RuntimeError("Échec d'envoi de la notification email"))
    return True
