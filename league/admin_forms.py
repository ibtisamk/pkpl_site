from django import forms

class GroupGenerationForm(forms.Form):
    num_groups = forms.IntegerField(
        label="Number of Groups",
        min_value=1,
        max_value=16,
        initial=4
    )
    random_draw = forms.BooleanField(
        label="Random Draw",
        required=False,
        initial=True
    )
    use_seeds = forms.BooleanField(
        label="Use Seed Rankings",
        required=False,
        initial=True
    )
