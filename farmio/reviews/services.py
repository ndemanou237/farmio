from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from farmio.orders.models import Order
from farmio.reviews.models import Review
from farmio.reviews.models import ReviewModeration
from farmio.utils.enums import OrderStatus


class ReviewSubmissionError(ValueError):
    """A review cannot be submitted for this order."""


def submit_order_review(order_id, buyer, *, rating: int, comment: str) -> Review:
    """Create one producer-level review for the buyer's completed order."""
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(
                pk=order_id,
                buyer=buyer,
                is_deleted=False,
            )
        except (Order.DoesNotExist, ValueError) as exc:
            raise PermissionDenied(_("Cette commande ne vous appartient pas.")) from exc
        if order.status != OrderStatus.COMPLETED:
            raise ReviewSubmissionError(
                _("Un avis est possible uniquement après la réception de la commande."),
            )
        if not order.lines.filter(is_deleted=False).exists():
            raise ReviewSubmissionError(
                _("Cette commande ne contient aucun produit à évaluer."),
            )
        if Review.objects.filter(order=order, buyer=buyer).exists():
            raise ReviewSubmissionError(
                _("Vous avez déjà donné votre avis pour cette commande."),
            )

        review = Review.objects.create(
            buyer=buyer,
            producer=order.producer,
            order=order,
            rating=rating,
            comment=comment,
            created_by=buyer,
            updated_by=buyer,
        )
        ReviewModeration.objects.create(
            review=review,
            created_by=buyer,
            updated_by=buyer,
        )
        return review
