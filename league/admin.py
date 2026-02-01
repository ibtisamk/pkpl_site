from django.contrib import admin
from django.urls import resolve
from django.contrib import messages
from .models import TeamRegistration, TeamRegistrationPlayer, PlayerRegistration
from django.shortcuts import render
from .admin_forms import GroupGenerationForm
from .services import generate_groups_for_season



from .models import (
    Club,
    Player,
    Season,
    Fixture,
    Match,
    PlayerMatchStats,
    PlayerSeasonStats,
    TeamSeasonStats,
    SeasonAwards,
    Group,
    GroupMembership,
)

# Backend services for generating groups, fixtures, knockouts
from .services import (
    generate_groups_for_season,
    generate_group_fixtures,
    generate_knockouts_for_season,
)

class TeamRegistrationPlayerInline(admin.TabularInline):
    model = TeamRegistrationPlayer
    extra = 0

@admin.register(TeamRegistration)
class TeamRegistrationAdmin(admin.ModelAdmin):
    list_display = ("team_name", "captain_name", "approved", "timestamp")
    list_filter = ("approved",)
    inlines = [TeamRegistrationPlayerInline]

@admin.register(PlayerRegistration)
class PlayerRegistrationAdmin(admin.ModelAdmin):
    list_display = ("name", "position", "preferred_club", "approved", "timestamp")
    list_filter = ("approved",)

# -----------------------------------
# PLAYER ADMIN
# -----------------------------------
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('gamertag', 'platform', 'club', 'position', 'location', 'age')
    list_filter = ('platform', 'club', 'position', 'location')
    search_fields = ('gamertag',)


# -----------------------------------
# INLINE: PlayerMatchStats inside Match
# -----------------------------------
class PlayerMatchStatsInline(admin.TabularInline):
    model = PlayerMatchStats
    extra = 0

    # Filter players to only home/away team players
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "player":
            match_id = None

            # Editing existing match
            if request.resolver_match.kwargs.get("object_id"):
                match_id = request.resolver_match.kwargs.get("object_id")

            # Adding PlayerMatchStats directly with ?match=<id>
            if request.GET.get("match"):
                match_id = request.GET.get("match")

            if match_id:
                try:
                    match = Match.objects.get(id=match_id)
                    home_players = Player.objects.filter(club=match.fixture.home_club)
                    away_players = Player.objects.filter(club=match.fixture.away_club)
                    kwargs["queryset"] = home_players.union(away_players)
                except Match.DoesNotExist:
                    pass

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# -----------------------------------
# MATCH ADMIN
# -----------------------------------
class MatchAdmin(admin.ModelAdmin):
    list_display = ('fixture', 'home_goals', 'away_goals', 'is_played')
    list_filter = ('fixture__season', 'is_played')
    inlines = [PlayerMatchStatsInline]


# -----------------------------------
# FIXTURE ADMIN
# -----------------------------------
class FixtureAdmin(admin.ModelAdmin):
    list_display = ('season', 'home_club', 'away_club', 'date', 'week_number', 'group')
    list_filter = ('season', 'week_number', 'group')
    search_fields = ('home_club__name', 'away_club__name')


# -----------------------------------
# PLAYER SEASON STATS ADMIN
# -----------------------------------
class PlayerSeasonStatsAdmin(admin.ModelAdmin):
    list_display = ('player', 'season', 'club', 'goals', 'assists', 'appearances', 'clean_sheets', 'manual')
    list_filter = ('season', 'club', 'manual')
    search_fields = ('player__gamertag',)


# -----------------------------------
# TEAM SEASON STATS ADMIN
# -----------------------------------
class TeamSeasonStatsAdmin(admin.ModelAdmin):
    list_display = ('team', 'season', 'played', 'wins', 'draws', 'losses', 'points', 'goals_for', 'goals_against')
    list_filter = ('season', 'team')
    search_fields = ('team__name',)


# -----------------------------------
# SEASON ADMIN (WITH GENERATION BUTTONS)
# -----------------------------------
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'is_active')
    actions = [
        'action_generate_groups',
        'action_generate_group_fixtures',
        'action_generate_knockouts',
    ]

    def response_action(self, request, queryset):
        print(">>> response_action triggered")
        response = super().response_action(request, queryset)
        print(">>> response from super:", response)
        if response is None:
            print(">>> response is None, calling action:", request.POST.get('action'))
            return getattr(self, request.POST.get('action'))(request, queryset)
        return response

    def action_generate_groups(self, request, queryset):
        print(">>> ADMIN ACTION CALLED")

        if request.method == "POST":
            print(">>> POST received")

            form = GroupGenerationForm(request.POST)
            print(">>> form valid:", form.is_valid())

            if form.is_valid():
                print(">>> FORM IS VALID, calling generator")

                num_groups = form.cleaned_data["num_groups"]
                random_draw = form.cleaned_data["random_draw"]
                use_seeds = form.cleaned_data["use_seeds"]

                for season in queryset:
                    print(">>> generating for season:", season)
                    generate_groups_for_season(
                        season=season,
                        num_groups=num_groups,
                        random_draw=random_draw,
                        use_seeds=use_seeds,
                    )

                print(">>> DONE generating")
                self.message_user(request, "Groups generated successfully.")
                return None
        else:
            print(">>> GET request, showing form")
            form = GroupGenerationForm()

        return render(request, "admin/generate_groups_form.html", {
            "form": form,
            "seasons": queryset,
            "action": "action_generate_groups",
        })

    action_generate_groups.short_description = "Generate Groups"

    # Generate Group Fixtures
    def action_generate_group_fixtures(self, request, queryset):
        for season in queryset:
            generate_group_fixtures(
                season=season,
                double_round_robin=False,
                auto_week_numbers=True,
            )
        messages.success(request, "Group fixtures generated successfully.")

    action_generate_group_fixtures.short_description = "Generate Group Fixtures"

    # Generate Knockouts
    def action_generate_knockouts(self, request, queryset):
        for season in queryset:
            generate_knockouts_for_season(
                season=season,
                qualifiers_per_group=2,
                random_bracket=False,
                seeded_bracket=True,
            )
        messages.success(request, "Knockout bracket generated successfully.")

    action_generate_knockouts.short_description = "Generate Knockout Bracket"

    # -----------------------------------
# SEASON AWARDS ADMIN
# -----------------------------------
class SeasonAwardsAdmin(admin.ModelAdmin):
    list_display = (
        'season',
        'mvp',
        'top_scorer',
        'top_assister',
        'best_defender',
        'best_midfielder'
    )
    list_filter = ('season',)
    search_fields = ('season__name',)



# -----------------------------------
# REGISTER MODELS
# -----------------------------------
admin.site.register(Club)
admin.site.register(Player, PlayerAdmin)
admin.site.register(Season, SeasonAdmin)
admin.site.register(Fixture, FixtureAdmin)
admin.site.register(Match, MatchAdmin)
admin.site.register(PlayerMatchStats)
admin.site.register(PlayerSeasonStats, PlayerSeasonStatsAdmin)
admin.site.register(TeamSeasonStats, TeamSeasonStatsAdmin)
admin.site.register(SeasonAwards, SeasonAwardsAdmin)
admin.site.register(Group)
admin.site.register(GroupMembership)
