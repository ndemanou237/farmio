from __future__ import annotations

from http import HTTPStatus

import pytest
from django.urls import reverse
from djmoney.money import Money

from farmio.catalog.models import Category
from farmio.catalog.models import Product
from farmio.orders.models import Order
from farmio.orders.models import OrderLine
from farmio.payments.models import PaymentTransaction
from farmio.reviews.models import Review
from farmio.reviews.models import ReviewModeration
from farmio.reviews.models import ReviewModerationStatus
from farmio.users.tests.factories import UserFactory
from farmio.utils.enums import OrderStatus
from farmio.utils.enums import PaymentMethod
from farmio.utils.enums import PaymentProvider
from farmio.utils.enums import PaymentTransactionStatus
from farmio.utils.enums import PaymentTransactionType

MAX_REVIEW_RATING = 5
EXPECTED_AGGREGATE_RATING = 4
EXPECTED_REVENUE_XAF = 1200


@pytest.fixture
def completed_order(db):
    buyer = UserFactory.create(is_buyer=True)
    producer = UserFactory.create(is_buyer=False, is_producer=True)
    order = Order.objects.create(
        buyer=buyer,
        producer=producer,
        status=OrderStatus.COMPLETED,
        total_amount=Money("1200", "XAF"),
    )
    category = Category.objects.create(name="Test category", slug="test-category")
    product = Product.objects.create(
        producer=producer,
        category=category,
        name="Test product",
        slug=f"test-product-{order.pk.hex[:8]}",
        price=Money("1200", "XAF"),
        quantity=2,
    )
    OrderLine.objects.create(
        order=order,
        product=product,
        quantity=1,
        unit_price=Money("1200", "XAF"),
    )
    return buyer, producer, order


@pytest.mark.django_db
def test_buyer_can_review_the_producer_after_completed_order(client, completed_order):
    buyer, producer, order = completed_order
    client.force_login(buyer)

    response = client.post(
        reverse("reviews:submit", kwargs={"order_id": order.pk}),
        {"rating": "5", "comment": "Produits de qualité."},
    )

    assert response.status_code == HTTPStatus.FOUND
    review = Review.objects.get(order=order)
    assert review.buyer == buyer
    assert review.producer == producer
    assert review.rating == MAX_REVIEW_RATING
    assert review.moderation.status == ReviewModerationStatus.PENDING


@pytest.mark.django_db
def test_review_requires_completed_order(client, completed_order):
    buyer, _producer, order = completed_order
    order.status = OrderStatus.IN_PROGRESS
    order.save(update_fields=["status"])
    client.force_login(buyer)

    response = client.post(
        reverse("reviews:submit", kwargs={"order_id": order.pk}),
        {"rating": "4", "comment": "Bon service."},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert not Review.objects.filter(order=order).exists()


@pytest.mark.django_db
def test_review_rejects_order_owned_by_another_buyer(client, completed_order):
    _buyer, _producer, order = completed_order
    other_buyer = UserFactory.create(is_buyer=True)
    client.force_login(other_buyer)

    response = client.post(
        reverse("reviews:submit", kwargs={"order_id": order.pk}),
        {"rating": "4", "comment": "Fraudulent attempt."},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not Review.objects.filter(order=order).exists()


@pytest.mark.django_db
def test_review_rejects_invalid_rating(client, completed_order):
    buyer, _producer, order = completed_order
    client.force_login(buyer)

    response = client.post(
        reverse("reviews:submit", kwargs={"order_id": order.pk}),
        {"rating": "6", "comment": "Note invalide."},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not Review.objects.filter(order=order).exists()


@pytest.mark.django_db
def test_review_requires_login(client, completed_order):
    _buyer, _producer, order = completed_order

    response = client.post(
        reverse("reviews:submit", kwargs={"order_id": order.pk}),
        {"rating": "5"},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert "login" in response.url


@pytest.mark.django_db
def test_buyer_cannot_submit_a_second_review(client, completed_order):
    buyer, producer, order = completed_order
    review = Review.objects.create(
        buyer=buyer,
        producer=producer,
        order=order,
        rating=3,
    )
    ReviewModeration.objects.create(review=review)
    client.force_login(buyer)

    response = client.post(
        reverse("reviews:submit", kwargs={"order_id": order.pk}),
        {"rating": "5", "comment": "Second review."},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert Review.objects.filter(order=order).count() == 1


@pytest.mark.django_db
def test_normal_user_cannot_access_review_moderation(client):
    client.force_login(UserFactory.create(is_buyer=True))

    response = client.get(reverse("reviews:moderation-list"))

    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.django_db
def test_admin_can_approve_and_hide_reviews(client, completed_order):
    buyer, producer, order = completed_order
    admin = UserFactory.create(is_staff=True)
    review = Review.objects.create(
        buyer=buyer,
        producer=producer,
        order=order,
        rating=5,
    )
    moderation = ReviewModeration.objects.create(review=review)
    client.force_login(admin)

    list_response = client.get(reverse("reviews:moderation-list"))
    approve_response = client.post(
        reverse("reviews:moderate", kwargs={"pk": review.pk}),
        {"decision": "approve"},
    )

    review.refresh_from_db()
    moderation.refresh_from_db()
    assert list_response.status_code == HTTPStatus.OK
    assert approve_response.status_code == HTTPStatus.FOUND
    assert moderation.status == ReviewModerationStatus.APPROVED
    assert review.is_deleted is False

    client.post(
        reverse("reviews:moderate", kwargs={"pk": review.pk}),
        {"decision": "hide"},
    )
    review.refresh_from_db()
    moderation.refresh_from_db()
    assert review.is_deleted is True
    assert moderation.status == ReviewModerationStatus.HIDDEN


@pytest.mark.django_db
def test_review_moderation_actions_require_post(client, completed_order):
    buyer, producer, order = completed_order
    review = Review.objects.create(
        buyer=buyer,
        producer=producer,
        order=order,
        rating=4,
    )
    ReviewModeration.objects.create(review=review)
    client.force_login(UserFactory.create(is_staff=True))

    response = client.get(reverse("reviews:moderate", kwargs={"pk": review.pk}))

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_admin_dashboard_and_empty_aggregations(client):
    admin = UserFactory.create(is_staff=True)
    client.force_login(admin)

    response = client.get(reverse("dashboard:admin"))

    assert response.status_code == HTTPStatus.OK
    assert response.context["orders_count"] == 0
    assert response.context["reviews_count"] == 0
    assert response.context["reviews_average"] is None
    assert response.context["chart_data"]["orders"] == {"labels": [], "values": []}


@pytest.mark.django_db
def test_admin_dashboard_aggregates_real_review_and_payment_data(
    client,
    completed_order,
):
    buyer, producer, order = completed_order
    review = Review.objects.create(
        buyer=buyer,
        producer=producer,
        order=order,
        rating=4,
    )
    ReviewModeration.objects.create(
        review=review,
        status=ReviewModerationStatus.APPROVED,
    )
    PaymentTransaction.objects.create(
        order=order,
        transaction_type=PaymentTransactionType.CHARGE,
        status=PaymentTransactionStatus.SUCCESS,
        amount=Money("1200", "XAF"),
        refunded_amount=Money("0", "XAF"),
        method=PaymentMethod.CARD,
        provider=PaymentProvider.STRIPE,
    )
    client.force_login(UserFactory.create(is_staff=True))

    response = client.get(reverse("dashboard:admin"))

    assert response.context["orders_count"] == 1
    assert response.context["completed_orders_count"] == 1
    assert response.context["products_count"] == 1
    assert response.context["reviews_count"] == 1
    assert response.context["reviews_pending_count"] == 0
    assert response.context["reviews_average"] == EXPECTED_AGGREGATE_RATING
    assert response.context["revenue_by_currency"][0]["amount_currency"] == "XAF"
    assert response.context["revenue_by_currency"][0]["total"] == EXPECTED_REVENUE_XAF


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("route_name", "content_type", "signature"),
    [
        ("dashboard:report-pdf", "application/pdf", b"%PDF-"),
        (
            "dashboard:report-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            b"PK\x03\x04",
        ),
    ],
)
def test_admin_report_exports_are_generated(
    client,
    route_name,
    content_type,
    signature,
):
    client.force_login(UserFactory.create(is_staff=True))

    response = client.get(reverse(route_name))

    assert response.status_code == HTTPStatus.OK
    assert response["Content-Type"] == content_type
    assert response.content.startswith(signature)


@pytest.mark.django_db
def test_report_exports_are_forbidden_to_regular_users(client):
    client.force_login(UserFactory.create(is_buyer=True))

    response = client.get(reverse("dashboard:report-excel"))

    assert response.status_code == HTTPStatus.FORBIDDEN
