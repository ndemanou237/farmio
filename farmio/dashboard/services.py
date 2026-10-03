from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg
from django.db.models import Count
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from farmio.catalog.models import Product
from farmio.orders.models import Order
from farmio.payments.models import PaymentTransaction
from farmio.reviews.models import Review
from farmio.reviews.models import ReviewModeration
from farmio.reviews.models import ReviewModerationStatus
from farmio.users.models import ProducerProfile
from farmio.utils.enums import OrderStatus
from farmio.utils.enums import PaymentTransactionStatus
from farmio.utils.enums import PaymentTransactionType

User = get_user_model()


def build_admin_dashboard_data() -> dict:
    """Return database-aggregated admin cards and chart series."""
    now = timezone.now()
    active_reviews = Review.objects.filter(
        is_deleted=False,
        moderation__status=ReviewModerationStatus.APPROVED,
    )
    month_start = (now - timedelta(days=365)).replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    orders_by_month = list(
        Order.objects.filter(created_at__gte=month_start)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total=Count("pk"))
        .order_by("month"),
    )
    ratings = list(
        active_reviews.values("rating").annotate(total=Count("pk")).order_by("rating"),
    )
    product_statuses = list(
        Product.objects.filter(is_deleted=False)
        .values("status")
        .annotate(total=Count("pk"))
        .order_by("status"),
    )
    revenue_by_currency = list(
        PaymentTransaction.objects.filter(
            status=PaymentTransactionStatus.SUCCESS,
            transaction_type=PaymentTransactionType.CHARGE,
        )
        .values("amount_currency")
        .annotate(total=Sum("amount"), payments=Count("pk"))
        .order_by("amount_currency"),
    )
    review_summary = active_reviews.aggregate(average=Avg("rating"), total=Count("pk"))

    return {
        "pending_producers_count": ProducerProfile.objects.filter(
            user__is_producer=True,
            user__is_email_verified=True,
            user__is_approved=False,
            user__is_active=True,
        ).count(),
        "buyers_count": User.objects.filter(
            is_buyer=True,
            is_active=True,
        ).count(),
        "producers_count": User.objects.filter(
            is_producer=True,
            is_active=True,
        ).count(),
        "users_count": User.objects.filter(is_active=True).count(),
        "orders_count": Order.objects.filter(is_deleted=False).count(),
        "orders_today_count": Order.objects.filter(
            created_at__date=timezone.localdate(),
        ).count(),
        "completed_orders_count": Order.objects.filter(
            status=OrderStatus.COMPLETED,
            is_deleted=False,
        ).count(),
        "products_count": Product.objects.filter(
            is_deleted=False,
        ).count(),
        "reviews_count": review_summary["total"],
        "reviews_pending_count": ReviewModeration.objects.filter(
            status=ReviewModerationStatus.PENDING,
            review__is_deleted=False,
        ).count(),
        "reviews_average": review_summary["average"],
        "revenue_by_currency": revenue_by_currency,
        "recent_orders": Order.objects.filter(is_deleted=False)
        .select_related("buyer", "producer")[:20],
        "chart_data": {
            "orders": {
                "labels": [row["month"].strftime("%b %Y") for row in orders_by_month],
                "values": [row["total"] for row in orders_by_month],
            },
            "ratings": {
                "labels": [row["rating"] for row in ratings],
                "values": [row["total"] for row in ratings],
            },
            "products": {
                "labels": [row["status"] for row in product_statuses],
                "values": [row["total"] for row in product_statuses],
            },
        },
        "generated_at": now,
    }
