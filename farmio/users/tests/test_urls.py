from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import resolve
from django.urls import reverse

if TYPE_CHECKING:
    from farmio.users.models import User


def test_detail(user: User):
    assert reverse("users:detail", kwargs={"pk": user.pk}) == f"/accounts/{user.pk}/"
    assert resolve(f"/accounts/{user.pk}/").view_name == "users:detail"


def test_update():
    assert reverse("users:update") == "/accounts/~update/"
    assert resolve("/accounts/~update/").view_name == "users:update"


def test_redirect():
    assert reverse("users:redirect") == "/accounts/~redirect/"
    assert resolve("/accounts/~redirect/").view_name == "users:redirect"
