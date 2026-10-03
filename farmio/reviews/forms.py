from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class ReviewForm(forms.Form):
    rating = forms.ChoiceField(
        label=_("Votre note"),
        choices=[
            (str(value), _("%(rating)s sur 5") % {"rating": value})
            for value in range(1, 6)
        ],
        widget=forms.RadioSelect,
        error_messages={"required": _("Choisissez une note de 1 à 5.")},
    )
    comment = forms.CharField(
        label=_("Votre commentaire"),
        required=False,
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "maxlength": 2000,
                "placeholder": _("Partagez votre expérience…"),
                "class": "w-full rounded-xl border border-slate-300 px-3 py-2 text-sm",
            },
        ),
    )
