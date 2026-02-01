from django import forms
from django.forms import formset_factory
from .models import TeamRegistration, TeamRegistrationPlayer, PlayerRegistration, POSITIONS
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field


class TeamRegistrationForm(forms.ModelForm):
    class Meta:
        model = TeamRegistration
        fields = [
            "team_name", "founded", "stadium",
            "platform", "region",
            "captain_name", "captain_whatsapp", "captain_position",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_show_labels = True

        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({
                "class": "bg-slate-800 text-white border border-slate-500 rounded-lg p-2 w-full"
            })


class PlayerRegistrationForm(forms.ModelForm):
    class Meta:
        model = PlayerRegistration
        fields = [
            "name", "contact", "preferred_club",
            "position", "region", "platform",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_show_labels = True

        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({
                "class": "bg-slate-800 text-white border border-slate-500 rounded-lg p-2 w-full"
            })


