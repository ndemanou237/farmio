import phonenumbers
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def normalize_phone_number(value: str) -> str:
    if not value:
        return value
    try:
        parsed = phonenumbers.parse(value, "CM")  # Cameroun par défaut si non préfixé
        if not phonenumbers.is_valid_number(parsed):
            raise ValidationError(_("Numéro de téléphone international invalide."))
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException as e:
        raise ValidationError(_("Numéro de téléphone international invalide.")) from e


def validate_phone_number(value: str) -> None:
    if value:
        normalize_phone_number(value)
