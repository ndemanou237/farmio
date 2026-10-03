"""RBAC — mixins CBV + décorateurs FBV, basés sur les flags booléens de `User`."""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _


class BuyerRequiredMixin(AccessMixin):
    """Exige que l'utilisateur ait le flag `is_buyer`."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_buyer:
            raise PermissionDenied(str(_("Réservé aux acheteurs.")))
        return super().dispatch(request, *args, **kwargs)


class ProducerRequiredMixin(AccessMixin):
    """Exige `is_producer=True`, sans exiger l'approbation."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_producer:
            raise PermissionDenied(str(_("Réservé aux producteurs.")))
        return super().dispatch(request, *args, **kwargs)


class ApprovedProducerRequiredMixin(ProducerRequiredMixin):
    """Exige un producteur pleinement opérationnel fonctionnalités de vente."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_producer:
            raise PermissionDenied(str(_("Réservé aux producteurs.")))
        if not request.user.can_sell:
            return redirect("users:pending_approval")
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(AccessMixin):
    """Exige `is_admin` (is_staff ou is_superuser)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_admin:
            messages.error(request, str(_("Réservé aux administrateurs.")))
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def buyer_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("users:login")
        if not request.user.is_buyer:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


def approved_producer_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("users:login")
        if not request.user.is_producer:
            raise PermissionDenied
        if not request.user.can_sell:
            return redirect("users:pending_approval")
        return view_func(request, *args, **kwargs)

    return _wrapped


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("users:login")
        if not request.user.is_admin:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped
