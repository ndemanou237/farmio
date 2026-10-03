from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.urls import reverse
from djmoney.money import Money

from farmio.orders.models import Order
from farmio.payments.models import PaymentTransaction
from farmio.payments.services import PaymentError
from farmio.payments.services import process_stripe_event
from farmio.payments.services import start_mobile_money_intent
from farmio.payments.services import start_stripe_checkout
from farmio.users.tests.factories import UserFactory
from farmio.utils.enums import OrderStatus
from farmio.utils.enums import PaymentProvider
from farmio.utils.enums import PaymentTransactionStatus
from farmio.utils.enums import PaymentTransactionType


@pytest.fixture
def order_pair(db):
    buyer = UserFactory.create(is_buyer=True)
    producer = UserFactory.create(is_buyer=False, is_producer=True)
    order = Order.objects.create(
        buyer=buyer,
        producer=producer,
        status=OrderStatus.CONFIRMED,
        total_amount=Money("1200", "XAF"),
    )
    return buyer, producer, order


def test_start_stripe_checkout_creates_pending_transaction(order_pair, monkeypatch):
    buyer, _producer, order = order_pair
    checkout = Mock(id="cs_test_123", url="https://checkout.stripe.test/session")
    stripe_create = Mock(return_value=checkout)
    monkeypatch.setattr(
        "farmio.payments.services.stripe.checkout.Session.create",
        stripe_create,
    )

    with override_settings(STRIPE_SECRET_KEY="sk_test_local", STRIPE_TEST_MODE=True):
        payment, url = start_stripe_checkout(
            order.pk,
            buyer,
            success_url="https://farmio.test/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://farmio.test/cancel",
        )

    assert url == checkout.url
    assert payment.order_id == order.pk
    assert payment.status == PaymentTransactionStatus.PENDING
    assert payment.provider_reference == checkout.id
    assert stripe_create.call_args.kwargs["idempotency_key"] == f"farmio-payment-{payment.pk}"


def test_stripe_requires_test_key(order_pair):
    buyer, _producer, order = order_pair
    with override_settings(STRIPE_SECRET_KEY="sk_live_not_allowed", STRIPE_TEST_MODE=True):
        with pytest.raises(PaymentError, match="test"):
            start_stripe_checkout(
                order.pk,
                buyer,
                success_url="https://farmio.test/success",
                cancel_url="https://farmio.test/cancel",
            )


def test_payment_requires_order_owner(order_pair):
    _buyer, _producer, order = order_pair
    stranger = UserFactory.create(is_buyer=True)

    with pytest.raises(PermissionDenied):
        start_mobile_money_intent(order.pk, stranger, "orange_money")


def test_mobile_money_intent_does_not_claim_payment(order_pair):
    buyer, _producer, order = order_pair

    payment = start_mobile_money_intent(order.pk, buyer, "orange_money")

    assert payment.status == PaymentTransactionStatus.PENDING
    assert payment.provider == PaymentProvider.MOBILE_MONEY_MANUAL
    assert payment.metadata["integration_configured"] is False
    assert payment.metadata["notice"].startswith("No payment request")


def test_paid_stripe_event_is_idempotent_and_notifies_both_participants(order_pair):
    buyer, producer, order = order_pair
    payment = PaymentTransaction.objects.create(
        order=order,
        transaction_type=PaymentTransactionType.CHARGE,
        status=PaymentTransactionStatus.PENDING,
        amount=order.total_amount,
        refunded_amount=Money(0, "XAF"),
        method="card",
        provider=PaymentProvider.STRIPE,
        provider_reference="cs_test_paid",
    )
    session = SimpleNamespace(
        metadata={"payment_transaction_id": str(payment.pk)},
        id="cs_test_paid",
        payment_status="paid",
        amount_total=1200,
        currency="xaf",
        payment_intent="pi_test_paid",
    )
    event = SimpleNamespace(
        type="checkout.session.completed",
        id="evt_test_1",
        data=SimpleNamespace(object=session),
    )

    assert process_stripe_event(event) is True
    assert process_stripe_event(event) is True
    payment.refresh_from_db()
    assert payment.status == PaymentTransactionStatus.SUCCESS
    assert payment.provider_transaction_id == "pi_test_paid"
    assert buyer.notifications.count() == 1
    assert producer.notifications.count() == 1


def test_stripe_event_with_wrong_amount_fails_transaction(order_pair):
    _buyer, _producer, order = order_pair
    payment = PaymentTransaction.objects.create(
        order=order,
        transaction_type=PaymentTransactionType.CHARGE,
        status=PaymentTransactionStatus.PENDING,
        amount=order.total_amount,
        refunded_amount=Money(0, "XAF"),
        method="card",
        provider=PaymentProvider.STRIPE,
        provider_reference="cs_test_wrong",
    )
    event = SimpleNamespace(
        type="checkout.session.completed",
        id="evt_wrong_amount",
        data=SimpleNamespace(
            object=SimpleNamespace(
                metadata={"payment_transaction_id": str(payment.pk)},
                id="cs_test_wrong",
                payment_status="paid",
                amount_total=100,
                currency="xaf",
                payment_intent="pi_wrong",
            ),
        ),
    )

    assert process_stripe_event(event) is True
    payment.refresh_from_db()
    assert payment.status == PaymentTransactionStatus.FAILED
    assert "did not match" in payment.failure_reason


def test_already_paid_order_rejects_new_payment(order_pair):
    buyer, _producer, order = order_pair
    PaymentTransaction.objects.create(
        order=order,
        transaction_type=PaymentTransactionType.CHARGE,
        status=PaymentTransactionStatus.SUCCESS,
        amount=order.total_amount,
        refunded_amount=Money(0, "XAF"),
        method="card",
        provider=PaymentProvider.STRIPE,
        provider_transaction_id="pi_already_paid",
    )

    with pytest.raises(PaymentError, match="déjà été payée"):
        start_mobile_money_intent(order.pk, buyer, "orange_money")


@pytest.mark.django_db
def test_stripe_webhook_rejects_missing_signature(client, settings):
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test_only"

    response = client.post(
        reverse("stripe-webhook"),
        data=b"{}",
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_stripe_webhook_uses_verified_event(client, settings, monkeypatch):
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test_only"
    event = SimpleNamespace(id="evt_verified", type="checkout.session.expired", data=None)
    construct_event = Mock(return_value=event)
    process_event = Mock(return_value=True)
    monkeypatch.setattr(
        "farmio.payments.views.stripe.Webhook.construct_event",
        construct_event,
    )
    monkeypatch.setattr("farmio.payments.views.process_stripe_event", process_event)

    response = client.post(
        reverse("stripe-webhook"),
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=123,v1=valid",
    )

    assert response.status_code == 200
    construct_event.assert_called_once()
    process_event.assert_called_once_with(event)
