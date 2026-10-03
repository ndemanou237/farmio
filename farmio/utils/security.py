"""Protection anti-brute-force (connexion) + journalisation des événements
de sécurité.

Le compteur de tentatives est stocké dans Redis (cache "security") : léger,
auto-expirant, et partagé entre plusieurs workers/instances de l'app.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import caches

if TYPE_CHECKING:
    from django.http import HttpRequest

from farmio.core.models import SecurityEventLog

security_cache = caches["security"]
security_logger = logging.getLogger("security")


def get_client_ip(request: HttpRequest) -> str:
    """Récupère l'adresse IP réelle du client, en tenant compte d'un éventuel proxy."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class LoginThrottle:
    """Verrouille temporairement les tentatives de connexion après trop d'échecs."""

    @staticmethod
    def _key(identifier: str, ip_address: str = "") -> str:
        normalized_identifier = identifier.strip().casefold()
        normalized_ip = ip_address.strip()
        return f"login:attempts:{normalized_ip}:{normalized_identifier}"

    @classmethod
    def is_locked(cls, identifier: str, ip_address: str = "") -> bool:
        attempts = security_cache.get(cls._key(identifier, ip_address), 0)
        return attempts >= settings.LOGIN_MAX_ATTEMPTS

    @classmethod
    def remaining_lockout_seconds(cls, identifier: str, ip_address: str = "") -> int:
        ttl = security_cache.ttl(cls._key(identifier, ip_address))
        return max(int(ttl or 0), 0)

    @classmethod
    def register_failure(cls, identifier: str, ip_address: str = "") -> int:
        """Incrémente le compteur d'échecs et (ré)initialise son expiration."""
        key = cls._key(identifier, ip_address)
        attempts = security_cache.get(key, 0) + 1
        security_cache.set(key, attempts, timeout=settings.LOGIN_LOCKOUT_MINUTES * 60)
        return attempts

    @classmethod
    def reset(cls, identifier: str, ip_address: str = "") -> None:
        security_cache.delete(cls._key(identifier, ip_address))


def log_security_event(
    request: HttpRequest | None,
    event_type: str,
    *,
    user=None,
    email: str = "",
    metadata: dict | None = None,
) -> None:
    """Journalise un événement de sécurité : fichier de logs + table d'audit."""

    ip_address = get_client_ip(request) if request else ""
    user_agent = request.META.get("HTTP_USER_AGENT", "") if request else ""

    security_logger.info(
        "event=%s user=%s email=%s ip=%s",
        event_type,
        user,
        email,
        ip_address,
    )

    SecurityEventLog.objects.create(
        user=user if user and user.is_authenticated else None,
        email=email or (user.email if user and hasattr(user, "email") else ""),
        event_type=event_type,
        ip_address=ip_address or None,
        user_agent=user_agent,
        metadata=metadata or {},
    )
