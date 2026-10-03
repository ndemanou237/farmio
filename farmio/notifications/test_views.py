import pytest
from django.urls import reverse

from farmio.notifications.models import Notification
from farmio.users.tests.factories import UserFactory


@pytest.mark.django_db
def test_notifications_list_count_and_mark_read(client):
    user = UserFactory.create(is_buyer=True)
    notification = Notification.objects.create(user=user, title="Commande", message="Créée")
    client.force_login(user)

    response = client.get(reverse("notifications:list"))

    assert response.status_code == 200
    assert response.context["unread_notification_count"] == 1
    assert notification in response.context["notifications"]
    response = client.post(reverse("notifications:read", kwargs={"pk": notification.pk}))
    assert response.status_code == 302
    notification.refresh_from_db()
    assert notification.is_read


@pytest.mark.django_db
def test_notification_cannot_be_read_by_another_user(client):
    owner = UserFactory.create(is_buyer=True)
    stranger = UserFactory.create(is_buyer=True)
    notification = Notification.objects.create(user=owner, title="Privée", message="Texte")
    client.force_login(stranger)

    response = client.post(reverse("notifications:read", kwargs={"pk": notification.pk}))

    assert response.status_code == 404
    notification.refresh_from_db()
    assert not notification.is_read


@pytest.mark.django_db
def test_mark_all_notifications_read_is_scoped_to_user(client):
    owner = UserFactory.create(is_buyer=True)
    other_user = UserFactory.create(is_buyer=True)
    own_notification = Notification.objects.create(user=owner, title="A", message="A")
    other_notification = Notification.objects.create(user=other_user, title="B", message="B")
    client.force_login(owner)

    client.post(reverse("notifications:read-all"))

    own_notification.refresh_from_db()
    other_notification.refresh_from_db()
    assert own_notification.is_read
    assert not other_notification.is_read
