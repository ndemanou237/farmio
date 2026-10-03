"""Database utility helpers for the Mboago.
This module provides reusable, model-agnostic utilities for:
- Secure random string generation.
- Unique slug generation (global uniqueness or scoped to a related object).
- PostgreSQL schema name normalisation and unique-name generation.
Usage
-----
    # Import the class and call its static methods directly
    # In a model's save() method:
    self.slug = DbFunctions.unique_slug_generator_by_name(self)
    # Or with an explicit field value:
    self.slug = DbFunctions.generate_unique_slug(self, self.title)
    # Scoped to a parent relation (e.g. ArticlePage.slug unique per Article):
    self.slug = DbFunctions.generate_unique_slug_for_related_object(
        self, self.title, related_field_name="article"
    )
"""

from __future__ import annotations

import logging
import re
import secrets
import string
from typing import Any

from django.utils.text import slugify

logger = logging.getLogger(__name__)


class DbFunctions:
    """Model-agnostic database utility functions.
    All methods are static — this class acts as a namespace, not a service
    object.  No instantiation is needed or intended.
    """

    # Number of random characters appended to resolve slug collisions.
    RANDOM_SUFFIX_LENGTH: int = 6
    # Character set for random suffixes: lowercase letters + digits.
    RANDOM_CHARS: str = string.ascii_lowercase + string.digits

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _get_slug_max_length(instance: Any) -> int:
        """Return the ``max_length`` of the ``slug`` field on *instance*'s model.
        Raises
        ------
        AttributeError
            If the model does not define a ``slug`` field.
        """
        klass = instance.__class__
        try:
            return klass._meta.get_field("slug").max_length  # type: ignore[return-value]  # noqa: SLF001
        except Exception as exc:
            logger.exception(
                "Error retrieving slug field metadata for %s",
                klass.__name__,
            )
            msg = f"Model {klass.__name__!r} must define a 'slug' field."
            raise AttributeError(
                msg,
            ) from exc

    # ── Public API ─────────────────────────────────────────────────────────────

    @staticmethod
    def random_string_generator(
        size: int = RANDOM_SUFFIX_LENGTH,
        chars: str = RANDOM_CHARS,
    ) -> str:
        """Return a cryptographically secure random string.
        Uses ``secrets.choice`` (not ``random``) to ensure the output is
        suitable for use in public-facing URLs without being predictable.
        Parameters
        ----------
        size:
            Length of the generated string (default: ``RANDOM_SUFFIX_LENGTH``).
        chars:
            Pool of characters to draw from (default: lowercase + digits).
        """
        return "".join(secrets.choice(chars) for _ in range(size))

    @staticmethod
    def generate_unique_slug(
        instance: Any,
        field_value: str,
        max_attempts: int = 100,
    ) -> str:
        """Return a globally unique slug for *instance* derived from *field_value*.
        Algorithm
        ---------
        1. Slugify *field_value* and truncate to the field's ``max_length``.
        2. If the slug is already taken, append a random 6-character suffix and
           retry.  Repeat up to *max_attempts* times.
        The loop is **iterative** (not recursive) to avoid hitting Python's
        recursion limit under high collision rates.
        Parameters
        ----------
        instance:
            The unsaved (or existing) model instance that will receive the slug.
        field_value:
            Raw string to slugify (e.g. ``self.name``, ``self.title``).
        max_attempts:
            Hard cap on retry iterations.  Raises ``ValueError`` if exceeded.
        Raises
        ------
        AttributeError
            If the model has no ``slug`` field.
        ValueError
            If a unique slug cannot be found within *max_attempts* iterations.
        """
        klass = instance.__class__
        max_length = DbFunctions._get_slug_max_length(instance)

        # Derive the base slug once; suffixed variants are generated in the loop.
        base_slug = slugify(field_value)[:max_length]
        candidate = base_slug

        for attempt in range(max_attempts):
            queryset = klass.objects.filter(slug=candidate)
            if instance.pk:
                queryset = queryset.exclude(pk=instance.pk)
            if not queryset.exists():
                logger.debug(
                    "Unique slug found for %s after %d attempt(s): %s",
                    klass.__name__,
                    attempt + 1,
                    candidate,
                )
                return candidate

            # Collision — append a fresh random suffix and retry.
            suffix = DbFunctions.random_string_generator(
                size=DbFunctions.RANDOM_SUFFIX_LENGTH,
            )
            # Reserve space for the hyphen separator + suffix.
            trim_to = max_length - DbFunctions.RANDOM_SUFFIX_LENGTH - 1
            candidate = f"{base_slug[:trim_to]}-{suffix}"
            logger.debug(
                "Slug collision for %s (attempt %d). Retrying with: %s",
                klass.__name__,
                attempt + 1,
                candidate,
            )

        error_msg = (f"Unable to generate a unique slug for {klass.__name__!r}"
                     f" after {max_attempts} attempts."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    @staticmethod
    def generate_unique_slug_for_related_object(
        instance: Any,
        field_value: str,
        related_field_name: str,
        max_attempts: int = 100,
    ) -> str:
        """Return a slug that is unique **within the scope of a related object**.
        Use this when the slug uniqueness constraint is per-parent rather than
        global (e.g. ``ArticlePage.slug`` must be unique per ``Article``).
        Parameters
        ----------
        instance:
            The model instance that will receive the slug.
        field_value:
            Raw string to slugify (e.g. ``self.title``).
        related_field_name:
            Name of the ForeignKey field pointing to the parent model
            (e.g. ``"article"``).
        max_attempts:
            Hard cap on retry iterations.
        Raises
        ------
        AttributeError
            If the model has no ``slug`` field, or *related_field_name* is not
            a valid attribute on *instance*.
        ValueError
            If a unique slug cannot be found within *max_attempts* iterations.
        Example
        -------
        ::
            slug = DbFunctions.generate_unique_slug_for_related_object(
                article_page, article_page.title, related_field_name="article"
            )
            article_page.slug = slug
        """
        klass = instance.__class__
        max_length = DbFunctions._get_slug_max_length(instance)

        # Resolve the related instance once — used as a filter value throughout.
        try:
            related_instance = getattr(instance, related_field_name)
        except AttributeError as exc:
            logger.exception(
                "Related field %r not found on %s",
                related_field_name,
                klass.__name__,
            )
            msg = (
                f"Model {klass.__name__!r} must have a"
                f"ForeignKey field {related_field_name!r}."
            )
            raise AttributeError(
                msg,
            ) from exc

        base_slug = slugify(field_value)[:max_length]
        candidate = base_slug

        for attempt in range(max_attempts):
            filter_kwargs: dict[str, Any] = {
                "slug": candidate,
                related_field_name: related_instance,
            }
            queryset = klass.objects.filter(**filter_kwargs)
            if instance.pk:
                queryset = queryset.exclude(pk=instance.pk)
            if not queryset.exists():
                logger.debug(
                    "Unique slug found for %s (scoped to %r) after %d attempt(s): %s",
                    klass.__name__,
                    related_field_name,
                    attempt + 1,
                    candidate,
                )
                return candidate

            suffix = DbFunctions.random_string_generator(
                size=DbFunctions.RANDOM_SUFFIX_LENGTH,
            )
            trim_to = max_length - DbFunctions.RANDOM_SUFFIX_LENGTH - 1
            candidate = f"{base_slug[:trim_to]}-{suffix}"
            logger.debug(
                "Slug collision for %s scoped to %r (attempt %d). Retrying with: %s",
                klass.__name__,
                related_field_name,
                attempt + 1,
                candidate,
            )

        error_msg = (
            f"Unable to generate a unique slug for {klass.__name__!r} "
            f"(scoped to {related_field_name!r}) after {max_attempts} attempts."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    @staticmethod
    def unique_slug_generator_by_name(instance: Any) -> str:
        """Return a globally unique slug derived from *instance*.name.
        Convenience wrapper around ``generate_unique_slug`` for models whose
        sluggable field is named ``name``.
        Parameters
        ----------
        instance:
            Model instance exposing a ``name`` attribute.
        Raises
        ------
        AttributeError
            If *instance* has no ``name`` attribute or no ``slug`` field.
        """
        if not hasattr(instance, "name"):
            msg = f"Model {instance.__class__.__name__!r} must have a 'name' attribute."
            raise AttributeError(
                msg,
            )
        return DbFunctions.generate_unique_slug(instance, instance.name)

    # ── Schema name helpers ────────────────────────────────────────────────────

    # Characters not allowed in a PostgreSQL identifier (keep only [a-z0-9_]).
    _SCHEMA_INVALID_RE: re.Pattern[str] = re.compile(r"[^a-z0-9_]")
    # Consecutive underscores collapse to one.
    _SCHEMA_MULTI_UNDER_RE: re.Pattern[str] = re.compile(r"_+")
    # PostgreSQL maximum identifier length.
    _PG_MAX_IDENTIFIER: int = 63

    @staticmethod
    def normalize_schema_name(value: str, max_length: int = 63) -> str:
        """Convert *value* into a valid, lowercase PostgreSQL schema identifier.
        Rules applied in order:
        1. Lowercase.
        2. Replace any character outside ``[a-z0-9_]`` with ``_``.
        3. If the first character is a digit, prepend ``t_``.
        4. Collapse consecutive underscores into one.
        5. Strip leading/trailing underscores.
        6. Truncate to *max_length* characters.
        7. Return ``"tenant"`` if the result is empty.
        Parameters
        ----------
        value:
            Raw input (e.g. a subdomain label such as ``"my-project"``).
        max_length:
            Maximum length of the returned identifier (default: ``63``).
        """
        name = value.lower()
        name = DbFunctions._SCHEMA_INVALID_RE.sub("_", name)
        if name and name[0].isdigit():
            name = f"t_{name}"
        name = DbFunctions._SCHEMA_MULTI_UNDER_RE.sub("_", name)
        name = name.strip("_")
        return name[:max_length] or "tenant"

    @staticmethod
    def unique_schema_name(value: str, max_attempts: int = 100) -> str:
        """Return a globally unique PostgreSQL schema name derived from *value*.
        Uses the same iterative collision-resolution strategy as
        ``generate_unique_slug``: the normalised base name is tried first;
        on collision a random 6-character suffix is appended and the check
        is retried up to *max_attempts* times.
        Parameters
        ----------
        value:
            Raw source string (e.g. the subdomain label entered by the user).
        max_attempts:
            Hard cap on retry iterations.
        Raises
        ------
        ValueError
            If a unique schema name cannot be found within *max_attempts*
            iterations.
        """
        from kpi_platform.main_app.models import Organization  # noqa: PLC0415

        max_len = DbFunctions._PG_MAX_IDENTIFIER
        base = DbFunctions.normalize_schema_name(value, max_length=max_len)
        candidate = base

        for attempt in range(max_attempts):
            if not Organization.objects.filter(schema_name=candidate).exists():
                logger.debug(
                    "Unique schema name found after %d attempt(s): %s",
                    attempt + 1,
                    candidate,
                )
                return candidate

            suffix = DbFunctions.random_string_generator(
                size=DbFunctions.RANDOM_SUFFIX_LENGTH,
            )
            trim_to = max_len - DbFunctions.RANDOM_SUFFIX_LENGTH - 1
            candidate = f"{base[:trim_to]}_{suffix}"
            logger.debug(
                "Schema name collision (attempt %d). Retrying with: %s",
                attempt + 1,
                candidate,
            )

        error_msg = (
            f"Unable to generate a unique schema name for {value!r}"
            f"after {max_attempts} attempts."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
