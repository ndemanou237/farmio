from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    """Rôles applicatifs — RBAC (acteur du diagramme de classe)."""

    ADMIN = "ADMIN", _("Administrateur")
    PRODUCER = "PRODUCER", _("Producteur")
    BUYER = "BUYER", _("Acheteur")


class AccountStatus(models.TextChoices):
    """Cycle de vie du compte — inscription, OTP, approbation."""

    PENDING_EMAIL = "PENDING_EMAIL", _("En attente de vérification de l'email")
    PENDING_APPROVAL = "PENDING_APPROVAL", _("En attente d'approbation")
    APPROVED = "APPROVED", _("Approuvé")
    REJECTED = "REJECTED", _("Rejeté")
    SUSPENDED = "SUSPENDED", _("Suspendu")


class OtpPurpose(models.TextChoices):
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION", _("Vérification de l'email")
    PASSWORD_RESET = "PASSWORD_RESET", _("Réinitialisation du mot de passe")


class ProductStatus(models.TextChoices):
    AVAILABLE = "AVAILABLE", _("Disponible")
    OUT_OF_STOCK = "OUT_OF_STOCK", _("Épuisé")
    UNAVAILABLE = "UNAVAILABLE", _("Indisponible")


class ProductUnit(models.TextChoices):
    KG = "KG", _("Kilogramme")
    SAC = "SAC", _("Sac")
    LITRE = "LITRE", _("Litre")
    UNITE = "UNITE", _("Unité")
    CAGEOT = "CAGEOT", _("Cageot")
    TONNE = "TONNE", _("Tonne")


class CartStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Actif")
    VALIDATED = "VALIDATED", _("Validé")
    EMPTY = "EMPTY", _("Vide")


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", _("En attente")
    CONFIRMED = "CONFIRMED", _("Confirmée")
    REFUSED = "REFUSED", _("Refusée")
    IN_PROGRESS = "IN_PROGRESS", _("En cours")
    COMPLETED = "COMPLETED", _("Terminée")
    CANCELLED = "CANCELLED", _("Annulée")


# ── Payments ──────────────────────────────────────────────────────────────────


class PaymentTransactionType(models.TextChoices):
    """Type of financial operation — replaces the old TransactionType."""

    CHARGE = "charge", _("Charge")
    REFUND = "refund", _("Refund")
    PARTIAL_REFUND = "partial_refund", _("Partial Refund")


class PaymentTransactionStatus(models.TextChoices):
    """Status unifié pour une transaction de paiement"""

    PENDING = "pending", _("Pending")
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")
    CANCELLED = "cancelled", _("Cancelled")
    REFUNDED = "refunded", _("Refunded")
    PARTIALLY_REFUNDED = "partially_refunded", _("Partially Refunded")
    FRAUD = "fraud", _("Fraud")


class PaymentMethod(models.TextChoices):
    MOBILE_MONEY = "mobile_money", _("Mobile Money")
    CARD = "card", _("Bank Card")


class PaymentProvider(models.TextChoices):
    """Payment service providers for checkout."""

    STRIPE = "stripe", _("Stripe (Card)")
    FLUTTERWAVE_MOBILE_MONEY = "flutterwave_mobile_money", _("Flutterwave Mobile Money")
    MOBILE_MONEY_MANUAL = "mobile_money_manual", _("Mobile Money (non configuré)")


class SecurityEventType(models.TextChoices):
    """Types d'événements journalisés pour l'audit de sécurité."""

    LOGIN_SUCCESS = "LOGIN_SUCCESS", _("Connexion réussie")
    LOGIN_FAILED = "LOGIN_FAILED", _("Échec de connexion")
    LOGIN_LOCKED = "LOGIN_LOCKED", _("Compte temporairement bloqué (brute-force)")
    LOGOUT = "LOGOUT", _("Déconnexion")
    PASSWORD_CHANGED = "PASSWORD_CHANGED", _("Mot de passe modifié")
    PASSWORD_RESET_REQUESTED = (
        "PASSWORD_RESET_REQUESTED",
        _("Réinitialisation demandée"),
    )
    PASSWORD_RESET_COMPLETED = (
        "PASSWORD_RESET_COMPLETED",
        _("Réinitialisation effectuée"),
    )
    OTP_REQUESTED = "OTP_REQUESTED", _("Code OTP demandé")
    OTP_VERIFIED = "OTP_VERIFIED", _("Code OTP vérifié")
    OTP_FAILED = "OTP_FAILED", _("Échec de vérification OTP")
    OTP_RATE_LIMITED = "OTP_RATE_LIMITED", _("Demande OTP bloquée (anti-spam)")
    SIGNUP = "SIGNUP", _("Inscription")
    PRODUCER_APPROVED = "PRODUCER_APPROVED", _("Compte producteur approuvé")
    PRODUCER_REJECTED = "PRODUCER_REJECTED", _("Compte producteur rejeté")
    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED", _("Compte suspendu")
    ACCOUNT_REACTIVATED = "ACCOUNT_REACTIVATED", _("Compte réactivé")
