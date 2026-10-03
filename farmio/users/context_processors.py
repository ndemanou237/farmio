from django.conf import settings

from farmio.cart.models import Cart
from farmio.utils.enums import CartStatus


def allauth_settings(request):
    """Expose some settings from django-allauth in templates."""
    return {
        "ACCOUNT_ALLOW_REGISTRATION": settings.ACCOUNT_ALLOW_REGISTRATION,
    }


def cart_status(request):
    """Expose le nombre d'articles du panier actif pour la navigation."""
    cart_count = 0
    if request.user.is_authenticated and getattr(request.user, "is_buyer", False):
        cart = Cart.objects.filter(
            buyer=request.user,
            status=CartStatus.ACTIVE,
            is_deleted=False,
        ).first()
        if cart is not None:
            cart_count = cart.items.filter(is_deleted=False).count()
    return {"cart_count": cart_count}
