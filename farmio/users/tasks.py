from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from farmio.utils.email import EmailUtil
from farmio.utils.enums import OtpPurpose

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_otp_email_task(self, user_id, code, purpose, validity_minutes):
    User = get_user_model()  # noqa: N806

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_otp_email_task : utilisateur %s introuvable",
            user_id,
        )
        return False

    subject = (
        _("Réinitialisation de votre mot de passe Farmio")
        if purpose == OtpPurpose.PASSWORD_RESET
        else _("Votre code de vérification Farmio")
    )

    success = EmailUtil.send_email_with_template(
        template="emails/otp_email.html",
        context={
            "full_name": user.name or user.email,
            "code": code,
            "minutes": validity_minutes,
        },
        receivers=[user.email],
        subject=subject,
    )

    if not success:
        raise self.retry(
            exc=RuntimeError("Échec d'envoi de l'email OTP"),
        )

    return success


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_producer_decision_email_task(self, user_id, approved, reason=""):
    User = get_user_model()  # noqa: N806

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_producer_decision_email_task : utilisateur %s introuvable",
            user_id,
        )
        return False

    template = (
        "emails/producer_approved_email.html"
        if approved
        else "emails/producer_rejected_email.html"
    )

    subject = (
        _("Votre compte producteur Farmio a été approuvé")
        if approved
        else _("Votre compte producteur Farmio n'a pas été approuvé")
    )

    success = EmailUtil.send_email_with_template(
        template=template,
        context={
            "full_name": user.name or user.email,
            "reason": reason,
        },
        receivers=[user.email],
        subject=subject,
    )

    if not success:
        raise self.retry(
            exc=RuntimeError(
                "Échec d'envoi de l'email de décision producteur",
            ),
        )

    return success


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_password_changed_notice_task(self, user_id):
    User = get_user_model()  # noqa: N806

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_password_changed_notice_task : utilisateur %s introuvable",
            user_id,
        )
        return False

    success = EmailUtil.send_email_with_template(
        template="emails/password_changed_email.html",
        context={
            "full_name": user.name or user.email,
        },
        receivers=[user.email],
        subject=_("Votre mot de passe Farmio a été modifié"),
    )

    if not success:
        raise self.retry(
            exc=RuntimeError(
                "Échec d'envoi de la notification de changement de mot de passe",
            ),
        )

    return success


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_account_locked_email_task(self, email, ip_address):
    """Alerte l'utilisateur d'un verrouillage pour tentatives suspectes."""
    User = get_user_model()  # noqa: N806

    user = User.objects.filter(email__iexact=email).first()

    if user is None:
        return False

    success = EmailUtil.send_email_with_template(
        template="emails/account_locked_email.html",
        context={
            "full_name": user.name or user.email,
            "ip_address": ip_address,
        },
        receivers=[user.email],
        subject=_(
            "Alerte de sécurité : votre compte Farmio a été temporairement bloqué",
        ),
    )

    if not success:
        raise self.retry(
            exc=RuntimeError(
                "Échec d'envoi de l'email de verrouillage",
            ),
        )

    return success


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_welcome_email_task(self, user_id, dashboard_url):
    User = get_user_model()  # noqa: N806

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_welcome_email_task : utilisateur %s introuvable",
            user_id,
        )
        return False

    success = EmailUtil.send_email_with_template(
        template="emails/welcome_email.html",
        context={
            "full_name": user.name or user.email.split("@")[0],
            "user_email": user.email,
            "dashboard_url": dashboard_url,
        },
        receivers=[user.email],
        subject=_("Bienvenue sur Farmio !"),
    )

    if not success:
        raise self.retry(
            exc=RuntimeError(
                "Échec d'envoi de l'email de bienvenue",
            ),
        )

    return success


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_password_reset_email_task(self, user_id, reset_url):
    User = get_user_model()  # noqa: N806

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "send_password_reset_email_task : utilisateur %s introuvable",
            user_id,
        )
        return False

    success = EmailUtil.send_email_with_template(
        template="emails/password_reset_email.html",
        context={
            "full_name": user.name or user.email,
            "reset_url": reset_url,
        },
        receivers=[user.email],
        subject=_("Réinitialisez votre mot de passe Farmio"),
    )

    if not success:
        raise self.retry(
            exc=RuntimeError(
                "Échec d'envoi de l'email de réinitialisation du mot de passe",
            ),
        )

    return success
