from django.urls import path

from farmio.notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("read-all/", views.MarkAllNotificationsReadView.as_view(), name="read-all"),
    path("<uuid:pk>/read/", views.MarkNotificationReadView.as_view(), name="read"),
]
