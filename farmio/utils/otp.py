"""Service de throttling OTP appuyé sur Redis (cache "otp").

Le code OTP lui-même reste stocké en base via le modèle `OtpCode` (source de
vérité, auditée). Redis sert uniquement de stockage *temporaire* et rapide
pour deux besoins qui ne doivent pas dépendre d'une requête DB à chaque
appel : le cooldown anti-spam sur le renvoi, et un verrou de sécurité
complémentaire.
"""

from __future__ import annotations

from django.core.cache import caches

otp_cache = caches["otp"]


class OtpService:
    """Espace de noms statique pour la gestion du cooldown OTP via Redis."""

    @staticmethod
    def _cooldown_key(user_id, purpose: str) -> str:
        return f"otp:cooldown:{purpose}:{user_id}"

    @classmethod
    def is_on_cooldown(cls, user_id, purpose: str) -> bool:
        """Renvoie True si un renvoi d'OTP est encore bloqué par le cooldown."""
        return otp_cache.get(cls._cooldown_key(user_id, purpose)) is not None

    @classmethod
    def remaining_cooldown_seconds(cls, user_id, purpose: str) -> int:
        """Temps restant avant de pouvoir redemander un code (0 si autorisé)."""
        ttl = otp_cache.ttl(cls._cooldown_key(user_id, purpose))
        return max(int(ttl or 0), 0)

    @classmethod
    def start_cooldown(cls, user_id, purpose: str, seconds: int) -> None:
        """Démarre le cooldown après l'envoi effectif d'un code."""
        otp_cache.set(cls._cooldown_key(user_id, purpose), value=True, timeout=seconds)

    @classmethod
    def clear_cooldown(cls, user_id, purpose: str) -> None:
        otp_cache.delete(cls._cooldown_key(user_id, purpose))
