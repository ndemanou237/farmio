from django.contrib import admin

from farmio.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = ("title", "user", "is_read", "created_at")
	list_filter = ("is_read", "created_at")
	search_fields = ("title", "message", "user__email")
	readonly_fields = ("created_at", "updated_at")
