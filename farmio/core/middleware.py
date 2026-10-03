"""Middleware transverse lié au cycle de vie du compte."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class AccountStatusMiddleware:
    """Déconnecte immédiatement un utilisateur dont le compte vient d'être désactivé.

    Utile quand un administrateur suspend un compte pendant que l'utilisateur
    a encore une session active : sans ce middleware, la session resterait
    valide jusqu'à expiration naturelle.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not user.is_active:
            logout(request)
            messages.error(
                request,
                _("Votre compte a été désactivé. Contactez le support."),
            )
            return redirect(reverse("users:login"))
        return self.get_response(request)
