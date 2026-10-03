from django.urls import path

from farmio.messaging import views

app_name = "messaging"

urlpatterns = [
    path("", views.ConversationListView.as_view(), name="list"),
    path("from-order/<uuid:order_id>/", views.StartConversationView.as_view(), name="start"),
    path("<uuid:pk>/", views.ConversationDetailView.as_view(), name="detail"),
    path("<uuid:pk>/poll/", views.ConversationPollView.as_view(), name="poll"),
    path("<uuid:pk>/send/", views.SendMessageView.as_view(), name="send"),
]
