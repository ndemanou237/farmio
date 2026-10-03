import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from djmoney.money import Money

from farmio.messaging.models import Conversation
from farmio.messaging.models import Message
from farmio.messaging.services import get_or_create_conversation_for_order
from farmio.messaging.services import send_message
from farmio.orders.models import Order
from farmio.users.tests.factories import UserFactory
from farmio.utils.enums import OrderStatus


@pytest.fixture
def confirmed_order(db):
    buyer = UserFactory.create(is_buyer=True)
    producer = UserFactory.create(is_buyer=False, is_producer=True)
    order = Order.objects.create(
        buyer=buyer,
        producer=producer,
        status=OrderStatus.CONFIRMED,
        total_amount=Money("800", "XAF"),
    )
    return buyer, producer, order


def test_conversation_created_from_confirmed_order_and_message_sent(confirmed_order):
    buyer, producer, order = confirmed_order

    conversation = get_or_create_conversation_for_order(order, buyer)
    message = send_message(conversation, buyer, "Bonjour producteur")

    assert message.author == buyer
    assert conversation.messages.count() == 1
    assert producer.notifications.count() == 1


def test_unrelated_user_cannot_open_or_write_conversation(confirmed_order):
    buyer, _producer, order = confirmed_order
    stranger = UserFactory.create(is_buyer=True)
    conversation = get_or_create_conversation_for_order(order, buyer)

    with pytest.raises(PermissionDenied):
        send_message(conversation, stranger, "Tentative")


def test_conversation_is_unavailable_while_order_pending(db):
    buyer = UserFactory.create(is_buyer=True)
    producer = UserFactory.create(is_buyer=False, is_producer=True)
    order = Order.objects.create(
        buyer=buyer,
        producer=producer,
        status=OrderStatus.PENDING,
        total_amount=Money("100", "XAF"),
    )

    with pytest.raises(PermissionDenied, match="confirmation"):
        get_or_create_conversation_for_order(order, buyer)


def test_poll_endpoint_only_returns_participant_messages(client, confirmed_order):
    buyer, producer, order = confirmed_order
    conversation = get_or_create_conversation_for_order(order, buyer)
    first = Message.objects.create(
        conversation=conversation,
        author=producer,
        content="Commande prête",
    )
    client.force_login(buyer)

    response = client.get(reverse("messaging:poll", kwargs={"pk": conversation.pk}))

    assert response.status_code == 200
    assert response.json()["messages"][0]["id"] == str(first.pk)
    first.refresh_from_db()
    assert first.is_read


def test_nonparticipant_cannot_access_poll_or_conversation(client, confirmed_order):
    buyer, _producer, order = confirmed_order
    conversation = get_or_create_conversation_for_order(order, buyer)
    stranger = UserFactory.create(is_buyer=True)
    client.force_login(stranger)

    response = client.get(reverse("messaging:poll", kwargs={"pk": conversation.pk}))

    assert response.status_code == 403
    assert Conversation.objects.filter(pk=conversation.pk).exists()
