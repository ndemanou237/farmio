from __future__ import annotations

from http import HTTPStatus

import pytest
from django.urls import reverse
from djmoney.money import Money

from farmio.orders.models import Order
from farmio.payments.models import PaymentTransaction
from farmio.users.tests.factories import UserFactory
from farmio.utils.enums import OrderStatus
from farmio.utils.enums import PaymentMethod
from farmio.utils.enums import PaymentProvider
from farmio.utils.enums import PaymentTransactionStatus
from farmio.utils.enums import PaymentTransactionType


@pytest.mark.django_db
def test_producer_can_start_only_a_confirmed_paid_order(client):
    buyer = UserFactory.create(is_buyer=True)
    producer = UserFactory.create(
        is_buyer=False,
        is_producer=True,
        is_email_verified=True,
        is_approved=True,
    )
    order = Order.objects.create(
        buyer=buyer,
        producer=producer,
        status=OrderStatus.CONFIRMED,
        total_amount=Money("1200", "XAF"),
    )
    client.force_login(producer)
    url = reverse("orders:start", kwargs={"pk": order.pk})

    unpaid_response = client.post(url)
    order.refresh_from_db()
    assert unpaid_response.status_code == HTTPStatus.FOUND
    assert order.status == OrderStatus.CONFIRMED

    PaymentTransaction.objects.create(
        order=order,
        transaction_type=PaymentTransactionType.CHARGE,
        status=PaymentTransactionStatus.SUCCESS,
        amount=order.total_amount,
        refunded_amount=Money("0", "XAF"),
        method=PaymentMethod.CARD,
        provider=PaymentProvider.STRIPE,
    )
    paid_response = client.post(url)
    order.refresh_from_db()

    assert paid_response.status_code == HTTPStatus.FOUND
    assert order.status == OrderStatus.IN_PROGRESS


@pytest.mark.django_db
def test_other_producer_cannot_start_order(client):
    buyer = UserFactory.create(is_buyer=True)
    owner = UserFactory.create(
        is_buyer=False,
        is_producer=True,
        is_email_verified=True,
        is_approved=True,
    )
    other_producer = UserFactory.create(
        is_buyer=False,
        is_producer=True,
        is_email_verified=True,
        is_approved=True,
    )
    order = Order.objects.create(
        buyer=buyer,
        producer=owner,
        status=OrderStatus.CONFIRMED,
        total_amount=Money("1200", "XAF"),
    )
    client.force_login(other_producer)

    response = client.post(reverse("orders:start", kwargs={"pk": order.pk}))

    assert response.status_code == HTTPStatus.FORBIDDEN
