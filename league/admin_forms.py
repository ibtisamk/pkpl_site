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


class KnockoutGenerationForm(forms.Form):
    TOTAL_CHOICES = [
        (2, '2 teams'),
        (4, '4 teams'),
        (8, '8 teams (QF -> SF -> F)'),
        (16, '16 teams (R16 -> QF -> SF -> F)'),
    ]

    total_qualified = forms.ChoiceField(
        choices=TOTAL_CHOICES,
        label="Total teams in knockout stage",
        initial=8,
    )

    two_leg_rounds = forms.BooleanField(
        label="Two-leg ties for knockout rounds (home & away)",
        required=False,
        initial=True,
    )

    seeded_bracket = forms.BooleanField(
        label="Seed bracket based on standings",
        required=False,
        initial=True,
    )

    random_bracket = forms.BooleanField(
        label="Randomize bracket",
        required=False,
        initial=False,
    )


class FinalGenerationForm(forms.Form):
    FORMAT_CHOICES = [
        ("single", "Single match"),
        ("two_leg", "Home & Away (two legs)"),
        ("best_of_three", "Best of three"),
    ]

    match_format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        label="Final format",
        initial="single",
    )

    start_date = forms.DateTimeField(
        label="Start date (optional)",
        required=False,
        help_text="If provided, fixtures will be scheduled starting from this date."
    )
