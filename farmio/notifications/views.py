from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import ListView

from farmio.notifications.models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
	template_name = "notifications/notification_list.html"
	context_object_name = "notifications"
	paginate_by = 30

	def get_queryset(self):
		return Notification.objects.filter(user=self.request.user).order_by(
			"-created_at",
		)


class MarkNotificationReadView(LoginRequiredMixin, View):
	def post(self, request, pk, *args, **kwargs):
		notification = get_object_or_404(
			Notification,
			pk=pk,
			user=request.user,
		)
		if not notification.is_read:
			notification.is_read = True
			notification.updated_by = request.user
			notification.save(update_fields=["is_read", "updated_by", "updated_at"])
		return redirect("notifications:list")


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
	def post(self, request, *args, **kwargs):
		Notification.objects.filter(user=request.user, is_read=False).update(
			is_read=True,
		)
		return redirect("notifications:list")
# Create your views here.
