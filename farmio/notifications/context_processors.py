from __future__ import annotations

from typing import Any

from farmio.notifications.models import Notification


def unread_notification_count(request) -> dict[str, Any]:
    count = 0
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
    return {"unread_notification_count": count}
