from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class PaymentChoiceForm(forms.Form):
    method = forms.ChoiceField(
        label=_("Moyen de paiement"),
        choices=[
            ("stripe", _("Carte bancaire — Stripe (sandbox)")),
            ("mobile_money", _("Mobile Money — fournisseur non configuré")),
        ],
        widget=forms.RadioSelect,
    )
    mobile_provider = forms.ChoiceField(
        label=_("Fournisseur Mobile Money"),
        required=False,
        choices=[
            ("orange_money", _("Orange Money")),
            ("mtn_momo", _("MTN MoMo")),
            ("other", _("Autre fournisseur")),
        ],
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("method") == "mobile_money" and not cleaned_data.get(
            "mobile_provider",
        ):
            self.add_error("mobile_provider", _("Choisissez un fournisseur."))
        return cleaned_data
