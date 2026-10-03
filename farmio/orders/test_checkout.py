import pytest
from django.core.exceptions import PermissionDenied
from djmoney.money import Money

from farmio.cart.models import Cart
from farmio.cart.models import CartItem
from farmio.catalog.models import Category
from farmio.catalog.models import Product
from farmio.orders.models import Order
from farmio.orders.models import OrderLine
from farmio.orders.services import CartValidationError
from farmio.orders.services import CartValidationService
from farmio.users.tests.factories import UserFactory
from farmio.utils.enums import CartStatus
from farmio.utils.enums import ProductStatus


@pytest.fixture
def checkout_setup(db):
    buyer = UserFactory.create(is_buyer=True)
    producers = [
        UserFactory.create(is_buyer=False, is_producer=True, is_approved=True, is_email_verified=True),
        UserFactory.create(is_buyer=False, is_producer=True, is_approved=True, is_email_verified=True),
    ]
    category = Category.objects.create(name="Fruits")
    products = [
        Product.objects.create(
            producer=producers[0],
            category=category,
            name="Plantain",
            price=Money("1200", "XAF"),
            quantity=10,
            status=ProductStatus.AVAILABLE,
        ),
        Product.objects.create(
            producer=producers[0],
            category=category,
            name="Mango",
            price=Money("500", "XAF"),
            quantity=8,
            status=ProductStatus.AVAILABLE,
        ),
        Product.objects.create(
            producer=producers[1],
            category=category,
            name="Avocado",
            price=Money("700", "XAF"),
            quantity=5,
            status=ProductStatus.AVAILABLE,
        ),
    ]
    cart = Cart.objects.create(buyer=buyer, status=CartStatus.ACTIVE)
    items = [
        CartItem.objects.create(cart=cart, product=product, quantity=qty, unit_price=product.price)
        for product, qty in zip(products, [2, 3, 1], strict=True)
    ]
    return buyer, producers, products, cart, items


def test_multi_producer_checkout_creates_correct_orders_and_decrements_stock(checkout_setup):
    buyer, producers, products, cart, items = checkout_setup

    orders = CartValidationService(buyer).validate()

    assert len(orders) == 2
    by_producer = {order.producer_id: order for order in orders}
    first_order = by_producer[producers[0].pk]
    second_order = by_producer[producers[1].pk]
    assert set(first_order.lines.values_list("product_id", flat=True)) == {
        products[0].pk,
        products[1].pk,
    }
    assert list(second_order.lines.values_list("product_id", flat=True)) == [products[2].pk]
    assert first_order.total_amount == Money(3900, "XAF")
    assert second_order.total_amount == Money(700, "XAF")
    for product, expected_quantity in zip(products, [8, 5, 4], strict=True):
        product.refresh_from_db()
        assert product.quantity == expected_quantity
    cart.refresh_from_db()
    assert cart.status == CartStatus.VALIDATED
    assert not cart.items.filter(is_deleted=False).exists()
    assert all(item.is_deleted is False for item in items)


def test_empty_cart_does_not_create_orders(db):
    buyer = UserFactory.create(is_buyer=True)
    Cart.objects.create(buyer=buyer, status=CartStatus.ACTIVE)

    with pytest.raises(CartValidationError, match="vide"):
        CartValidationService(buyer).validate()

    assert not Order.objects.exists()


def test_insufficient_stock_preserves_cart_and_creates_no_orders(checkout_setup):
    buyer, _producers, products, cart, _items = checkout_setup
    products[0].quantity = 1
    products[0].save(update_fields=["quantity"])

    with pytest.raises(CartValidationError, match="insuffisant"):
        CartValidationService(buyer).validate()

    assert not Order.objects.exists()
    cart.refresh_from_db()
    assert cart.status == CartStatus.ACTIVE
    assert cart.items.filter(is_deleted=False).count() == 3


def test_unavailable_product_rolls_back_everything(checkout_setup):
    buyer, _producers, products, cart, _items = checkout_setup
    products[2].status = ProductStatus.UNAVAILABLE
    products[2].save(update_fields=["status"])

    with pytest.raises(CartValidationError, match="disponible"):
        CartValidationService(buyer).validate()

    assert not Order.objects.exists()
    for product, expected_quantity in zip(products, [10, 8, 5], strict=True):
        product.refresh_from_db()
        assert product.quantity == expected_quantity
    cart.refresh_from_db()
    assert cart.status == CartStatus.ACTIVE


def test_partial_order_creation_failure_rolls_back_stock_and_cart(
    checkout_setup,
    monkeypatch,
):
    buyer, _producers, products, cart, _items = checkout_setup
    line_create = OrderLine.objects.create
    calls = 0

    def fail_after_first_line(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("line persistence failed")
        return line_create(*args, **kwargs)

    monkeypatch.setattr(
        "farmio.orders.services.OrderLine.objects.create",
        fail_after_first_line,
    )
    with pytest.raises(RuntimeError, match="persistence"):
        CartValidationService(buyer).validate()

    assert not Order.objects.exists()
    for product, expected_quantity in zip(products, [10, 8, 5], strict=True):
        product.refresh_from_db()
        assert product.quantity == expected_quantity
    cart.refresh_from_db()
    assert cart.status == CartStatus.ACTIVE
    assert cart.items.filter(is_deleted=False).count() == 3


def test_own_product_in_cart_is_rejected(checkout_setup):
    buyer, _producers, products, cart, _items = checkout_setup
    products[0].producer = buyer
    products[0].save(update_fields=["producer"])

    with pytest.raises(PermissionDenied):
        CartValidationService(buyer).validate()

    assert not Order.objects.exists()
    cart.refresh_from_db()
    assert cart.status == CartStatus.ACTIVE


def test_order_amount_is_based_on_snapshotted_cart_price(checkout_setup):
    buyer, _producers, products, _cart, _items = checkout_setup
    products[0].price = Money("9999", "XAF")
    products[0].save(update_fields=["price"])
    CartValidationService(buyer).validate()

    order = Order.objects.get(producer=products[0].producer)
    assert order.total_amount == Money(3900, "XAF")
