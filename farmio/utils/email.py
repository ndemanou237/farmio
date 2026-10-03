from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import translation

logger = logging.getLogger(__name__)


class EmailUtil:
    """Utility helpers for sending emails through Django's email backend."""

    @staticmethod
    def _resolve_subject(subject: str | object) -> str:
        if isinstance(subject, str):
            return subject

        try:
            return str(subject)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to convert subject to string: %s", exc)
            return str(subject) if subject else ""

    @staticmethod
    def _translate_subject(subject: str | object, language: str) -> str:
        if not subject:
            return ""

        if isinstance(subject, str):
            if language:
                with translation.override(language):
                    return str(subject)
            return subject

        try:
            if language:
                with translation.override(language):
                    return str(subject)
            return str(subject)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to translate subject to %s: %s", language, exc)
            return str(subject)

    @staticmethod
    def _add_site_context(context: dict[str, Any]) -> dict[str, Any]:
        site_url = getattr(settings, "BASE_URL", "")
        if site_url and not site_url.startswith(("http://", "https://")):
            site_url = (
                f"https://{site_url}"
                if "localhost" not in site_url
                else f"http://{site_url}"
            )

        context["site_url"] = site_url
        context["site_name"] = getattr(settings, "SITE_NAME", "Farmio")

        static_url = getattr(settings, "STATIC_URL", "/static/")
        if static_url.startswith(("http://", "https://")):
            logo_url = f"{static_url}images/logo/Mboago.png"
        else:
            logo_url = f"{site_url.rstrip('/')}{static_url}images/logo/Mboago.png"

        context["logo_url"] = logo_url
        return context

    @staticmethod
    def send_generic_email(
        subject: str,
        to: list[str],
        _from: str | None = None,
        file_path: str | None = None,
        html_content: str | None = None,
        text_content: str | None = None,
    ) -> bool:
        if not isinstance(to, list):
            msg = "The 'to' parameter must be a list"
            raise TypeError(msg)
        if not to or None in to or any(not email for email in to):
            msg = "The 'to' list must contain valid email addresses"
            raise ValueError(msg)
        if not subject:
            msg = "Subject is required"
            raise ValueError(msg)
        if not text_content and not html_content:
            msg = "Content is required"
            raise ValueError(msg)

        is_debug = getattr(settings, "DEBUG", False)
        if is_debug:
            subject = f"[TEST] {subject}"

        default_from = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com")
        from_email = _from or default_from

        if getattr(settings, "TESTING", False):
            logger.info("*** TEST EMAIL MODE ***")
            return True

        return EmailUtil._send_django_email(
            subject,
            html_content or text_content,
            to,
            from_email,
            file_path,
        )

    @staticmethod
    def _send_django_email(
        subject: str,
        content: str,
        to: list[str],
        from_email: str,
        file_path: str | None,
    ) -> bool:
        try:
            email = EmailMessage(subject, content, from_email, [], bcc=to)
            email.content_subtype = "html"

            if file_path and Path.exists(file_path):
                email.attach_file(file_path)
            elif file_path:
                logger.warning("File not found at: %s", file_path)

            email.send()
        except Exception:
            logger.exception("Error sending email via Django backend")
            return False
        return True

    @staticmethod
    def send_email_with_template(
        template: str,
        context: dict[str, Any],
        receivers: list[str],
        subject: str | object,
        language: str | None = None,
    ) -> bool:
        context = EmailUtil._add_site_context(context)

        resolved_subject = subject
        if language:
            resolved_subject = EmailUtil._translate_subject(subject, language)
        else:
            resolved_subject = EmailUtil._resolve_subject(subject)

        context["subject"] = resolved_subject

        current_language = translation.get_language()
        try:
            if language:
                translation.activate(language)
                if subject != resolved_subject:
                    resolved_subject = EmailUtil._translate_subject(subject, language)
                    context["subject"] = resolved_subject

            body = render_to_string(template_name=template, context=context)
        except Exception:
            logger.exception("Error rendering email template %s", template)
            return False
        finally:
            translation.activate(current_language)

        try:
            return EmailUtil.send_generic_email(
                subject=resolved_subject,
                to=receivers,
                html_content=body,
            )
        except Exception:
            logger.exception("An error occurred while sending email with template")
            return False

    @staticmethod
    def send_email_with_template_batch(
        template: str,
        receivers_with_language: list[dict[str, Any]],
        subject: str | object,
    ) -> dict[str, Any]:
        success_count = 0
        failure_count = 0
        results: list[dict[str, Any]] = []

        for recipient in receivers_with_language:
            email = recipient.get("email")
            language = recipient.get("language")

            if not email:
                logger.warning("Skipping recipient with no email: %s", recipient)
                failure_count += 1
                continue

            lang = language or settings.LANGUAGE_CODE
            success = EmailUtil.send_email_with_template(
                template=template,
                context={"user": recipient.get("context", {})},
                receivers=[email],
                subject=subject,
                language=lang,
            )

            if success:
                success_count += 1
                results.append({"email": email, "language": lang, "success": True})
            else:
                failure_count += 1
                results.append({"email": email, "language": lang, "success": False})

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results,
        }
