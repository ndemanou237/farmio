from django.urls import path

from farmio.reviews import views

app_name = "reviews"

urlpatterns = [
    path(
        "orders/<uuid:order_id>/submit/",
        views.ReviewSubmitView.as_view(),
        name="submit",
    ),
    path("admin/", views.ReviewModerationListView.as_view(), name="moderation-list"),
    path(
        "admin/<uuid:pk>/moderate/",
        views.ReviewModerationActionView.as_view(),
        name="moderate",
    ),
]
