from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("buyer/", views.BuyerDashboardView.as_view(), name="buyer"),
    path("producer/", views.ProducerDashboardView.as_view(), name="producer"),
    path("admin/", views.AdminDashboardView.as_view(), name="admin"),
]
