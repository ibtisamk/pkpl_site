from django.contrib import admin
from django.contrib import messages
from django.shortcuts import render
from django.urls import resolve
from django.db.models import Q
from django.db import transaction

from .admin_forms import (
    GroupGenerationForm,
    KnockoutGenerationForm,
    FinalGenerationForm,
)

from .services import (
    generate_groups_for_season,
    generate_group_fixtures,
    generate_knockouts_for_season,
)

from .models import (
    Club,
    Player,
    Season,
    Fixture,
    GroupMatch,
    PlayerMatchStats,
    PlayerSeasonStats,
    TeamSeasonStats,
    SeasonAwards,
    Group,
    GroupMembership,
    KnockoutRound,
    KnockoutMatch,
    TeamRegistration,
    TeamRegistrationPlayer,
    PlayerRegistration,
    REGIONS,
)


# -----------------------------
# Group fixture generation actions (apply only to custom league.models.Group)
# -----------------------------
@admin.action(description="Generate Group Fixtures (1x each pair)")
def action_generate_group_fixtures_1x(modeladmin, request, queryset):
    total = 0
    for group in queryset:
        total += generate_group_fixtures(group, repeats=1)
    modeladmin.message_user(request, f"Created {total} fixtures.")


@admin.action(description="Generate Group Fixtures (2x each pair)")
def action_generate_group_fixtures_2x(modeladmin, request, queryset):
    total = 0
    for group in queryset:
        total += generate_group_fixtures(group, repeats=2)
    modeladmin.message_user(request, f"Created {total} fixtures.")


@admin.action(description="Generate Group Fixtures (3x each pair)")
def action_generate_group_fixtures_3x(modeladmin, request, queryset):
    total = 0
    for group in queryset:
        total += generate_group_fixtures(group, repeats=3)
    modeladmin.message_user(request, f"Created {total} fixtures.")


@admin.action(description="Generate Group Fixtures (4x each pair)")
def action_generate_group_fixtures_4x(modeladmin, request, queryset):
    total = 0
    for group in queryset:
        total += generate_group_fixtures(group, repeats=4)
    modeladmin.message_user(request, f"Created {total} fixtures.")


# ============================================================
# TEAM REGISTRATION
# ============================================================

class TeamRegistrationPlayerInline(admin.TabularInline):
    model = TeamRegistrationPlayer
    extra = 0


# -----------------------------
# Team Registration Approval Action
# -----------------------------
@admin.action(description="Approve selected registrations and create Clubs/Players")
def approve_registration(modeladmin, request, queryset):
    """
    Approve team registrations by creating Club and Player objects.
    Skips registrations that are already approved to prevent duplicates.
    """
    approved_count = 0
    skipped_count = 0
    error_count = 0

    for registration in queryset:
        # Skip if already approved
        if registration.approved:
            skipped_count += 1
            continue

        try:
            with transaction.atomic():
                # Create the Club
                club, club_created = Club.objects.get_or_create(
                    name=registration.team_name,
                    defaults={
                        'founded': int(registration.founded) if registration.founded and registration.founded.isdigit() else None,
                        'stadium': registration.stadium,
                        'short_name': registration.team_name[:20] if registration.team_name else None,
                    }
                )

                # If club already existed, update fields anyway
                if not club_created:
                    if registration.founded and registration.founded.isdigit():
                        club.founded = int(registration.founded)
                    if registration.stadium:
                        club.stadium = registration.stadium
                    club.save()

                # Create the captain as a Player
                captain_player = Player.objects.create(
                    gamertag=registration.captain_name,
                    platform=registration.platform or 'PS5',
                    club=club,
                    position=registration.captain_position,
                    location=dict(REGIONS).get(registration.region, '') if registration.region else None,
                )

                # Create Player objects for all registered players
                players_created = 0
                for player_registration in registration.players.all():
                    Player.objects.create(
                        gamertag=player_registration.name,
                        platform=registration.platform or 'PS5',
                        club=club,
                        position=player_registration.position,
                        location=dict(REGIONS).get(registration.region, '') if registration.region else None,
                    )
                    players_created += 1

                # Mark registration as approved
                registration.approved = True
                registration.save()

                approved_count += 1

        except Exception as e:
            error_count += 1
            messages.error(request, f"Error approving {registration.team_name}: {str(e)}")
            continue

    # Display success message
    if approved_count > 0:
        messages.success(
            request,
            f"Successfully approved {approved_count} registration(s) and created clubs/players."
        )
    if skipped_count > 0:
        messages.info(request, f"Skipped {skipped_count} already approved registration(s).")
    if error_count > 0:
        messages.warning(request, f"Failed to approve {error_count} registration(s).")


@admin.register(TeamRegistration)
class TeamRegistrationAdmin(admin.ModelAdmin):
    list_display = ("team_name", "captain_name", "approved", "timestamp")
    list_filter = ("approved",)
    inlines = [TeamRegistrationPlayerInline]
    actions = [approve_registration]


@admin.register(PlayerRegistration)
class PlayerRegistrationAdmin(admin.ModelAdmin):
    list_display = ("name", "position", "preferred_club", "approved", "timestamp")
    list_filter = ("approved",)


# ============================================================
# PLAYER ADMIN
# ============================================================

class PlayerAdmin(admin.ModelAdmin):
    list_display = ('gamertag', 'platform', 'club', 'position', 'location', 'age')
    list_filter = ('platform', 'club', 'position', 'location')
    search_fields = ('gamertag',)


# ============================================================
# PLAYER MATCH STATS INLINE
# ============================================================

class PlayerMatchStatsGroupInline(admin.TabularInline):
    model = PlayerMatchStats
    fk_name = 'group_match'
    extra = 0
    fields = ('player', 'goals', 'assists', 'minutes_played', 'rating')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "player":
            match_id = None

            if request.resolver_match.kwargs.get("object_id"):
                match_id = request.resolver_match.kwargs.get("object_id")

            if request.GET.get("group_match"):
                match_id = request.GET.get("group_match")

            if match_id:
                try:
                    gm = GroupMatch.objects.get(id=match_id)
                    home_players = Player.objects.filter(club=gm.fixture.home_club)
                    away_players = Player.objects.filter(club=gm.fixture.away_club)
                    kwargs["queryset"] = (home_players | away_players).distinct()
                except GroupMatch.DoesNotExist:
                    pass

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class PlayerMatchStatsKnockoutInline(admin.TabularInline):
    model = PlayerMatchStats
    fk_name = 'knockout_match'
    extra = 0
    fields = ('player', 'goals', 'assists', 'minutes_played', 'rating')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "player":
            match_id = None

            if request.resolver_match.kwargs.get("object_id"):
                match_id = request.resolver_match.kwargs.get("object_id")

            if request.GET.get("knockout_match"):
                match_id = request.GET.get("knockout_match")

            if match_id:
                try:
                    km = KnockoutMatch.objects.get(id=match_id)
                    home_players = Player.objects.filter(club=km.home_club)
                    away_players = Player.objects.filter(club=km.away_club)
                    kwargs["queryset"] = (home_players | away_players).distinct()
                except KnockoutMatch.DoesNotExist:
                    pass

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ============================================================
# GROUP MATCH ADMIN (RENAMED FROM MatchAdmin)
# ============================================================

@admin.register(GroupMatch)
class GroupMatchAdmin(admin.ModelAdmin):
    list_display = ('fixture', 'home_goals', 'away_goals', 'is_played')
    list_filter = ('fixture__season', 'is_played')
    inlines = [PlayerMatchStatsGroupInline]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        # limit home_players/away_players to players from the fixture's clubs
        obj_id = request.resolver_match.kwargs.get('object_id')
        if obj_id:
            try:
                gm = GroupMatch.objects.select_related('fixture__home_club', 'fixture__away_club').get(pk=obj_id)
                if db_field.name == 'home_players' and gm.fixture and gm.fixture.home_club:
                    kwargs['queryset'] = Player.objects.filter(club=gm.fixture.home_club)
                if db_field.name == 'away_players' and gm.fixture and gm.fixture.away_club:
                    kwargs['queryset'] = Player.objects.filter(club=gm.fixture.away_club)
            except GroupMatch.DoesNotExist:
                pass

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                'players-for-fixture/',
                self.admin_site.admin_view(self.players_for_fixture_view),
                name='league_groupmatch_players_for_fixture',
            ),
        ]
        return custom_urls + urls

    def players_for_fixture_view(self, request):
        from django.http import JsonResponse

        fixture_id = request.GET.get('fixture_id')
        data = {'home': [], 'away': []}

        if fixture_id:
            try:
                fixture = Fixture.objects.select_related('home_club', 'away_club').get(pk=fixture_id)
                data['home'] = list(Player.objects.filter(club=fixture.home_club).values('id', 'gamertag'))
                data['away'] = list(Player.objects.filter(club=fixture.away_club).values('id', 'gamertag'))
            except Fixture.DoesNotExist:
                pass

        return JsonResponse(data)

    # Removed formfield_for_manytomany override; not needed for custom Group model

    class Media:
        js = ('league/match_admin.js',)


# ============================================================
# FIXTURE ADMIN
# ============================================================

class FixtureAdmin(admin.ModelAdmin):
    list_display = ('season', 'home_club', 'away_club', 'date', 'week_number', 'group')
    list_filter = ('season', 'week_number', 'group')
    search_fields = ('home_club__name', 'away_club__name')


# ============================================================
# PLAYER SEASON STATS ADMIN
# ============================================================

class PlayerSeasonStatsAdmin(admin.ModelAdmin):
    def amr(self, obj):
        """Average Match Rating (AMR) shown in admin.

        NOTE: `PlayerSeasonStats.rating` stores the average rating value.
        If you later change to store summed ratings, update this method to divide
        by `obj.appearances` where appropriate.
        """
        try:
            return round(obj.rating, 2) if obj.rating is not None else None
        except Exception:
            return None

    amr.short_description = 'AMR'
    amr.admin_order_field = 'rating'

    list_display = ('player', 'season', 'club', 'goals', 'assists', 'appearances', 'clean_sheets', 'amr', 'manual')
    list_filter = ('season', 'club', 'manual')
    search_fields = ('player__gamertag',)
    readonly_fields = ('amr',)


# ============================================================
# TEAM SEASON STATS ADMIN
# ============================================================

class TeamSeasonStatsAdmin(admin.ModelAdmin):
    list_display = ('team', 'season', 'played', 'wins', 'draws', 'losses', 'points', 'goals_for', 'goals_against')
    list_filter = ('season', 'team')
    search_fields = ('team__name',)


# ============================================================
# SEASON ADMIN
# ============================================================

class SeasonAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'is_active')
    actions = [
        'action_generate_groups',
        'action_generate_group_fixtures',
        'action_generate_knockouts',
        'action_generate_final',
    ]

    # -----------------------------
    # GROUP GENERATION
    # -----------------------------
    def action_generate_groups(self, request, queryset):
        if request.method == "POST":
            form = GroupGenerationForm(request.POST)
            if form.is_valid():
                num_groups = form.cleaned_data["num_groups"]
                random_draw = form.cleaned_data["random_draw"]
                use_seeds = form.cleaned_data["use_seeds"]

                for season in queryset:
                    generate_groups_for_season(
                        season=season,
                        num_groups=num_groups,
                        random_draw=random_draw,
                        use_seeds=use_seeds,
                    )

                messages.success(request, "Groups generated successfully.")
                return None
        else:
            form = GroupGenerationForm()

        return render(request, "admin/generate_groups_form.html", {
            "form": form,
            "seasons": queryset,
            "action": "action_generate_groups",
        })

    action_generate_groups.short_description = "Generate Groups"

    # -----------------------------
    # GROUP FIXTURES
    # -----------------------------
    def action_generate_group_fixtures(self, request, queryset):
        for season in queryset:
            generate_group_fixtures(
                season=season,
                double_round_robin=False,
                auto_week_numbers=True,
            )
        messages.success(request, "Group fixtures generated successfully.")

    action_generate_group_fixtures.short_description = "Generate Group Fixtures"

    # -----------------------------
    # KNOCKOUT GENERATION
    # -----------------------------
    @transaction.atomic
    def action_generate_knockouts(self, request, queryset):
        if request.method == "POST":
            form = KnockoutGenerationForm(request.POST)
            if form.is_valid():
                total_qualified = int(form.cleaned_data["total_qualified"])
                two_leg_rounds = form.cleaned_data.get("two_leg_rounds", False)
                seeded_bracket = form.cleaned_data.get("seeded_bracket", True)
                random_bracket = form.cleaned_data.get("random_bracket", False)

                for season in queryset:
                    groups = list(season.groups.all())
                    if not groups:
                        messages.error(request, f"Season {season} has no groups defined.")
                        continue

                    if total_qualified % len(groups) != 0:
                        messages.error(request, "Total qualified is not divisible by number of groups.")
                        continue

                    qualifiers_per_group = total_qualified // len(groups)

                    generate_knockouts_for_season(
                        season=season,
                        qualifiers_per_group=qualifiers_per_group,
                        random_bracket=random_bracket,
                        seeded_bracket=seeded_bracket,
                        two_leg_rounds=two_leg_rounds,
                        create_fixtures=True,
                    )

                messages.success(request, "Knockout bracket generated successfully.")
                return None
        else:
            form = KnockoutGenerationForm()

        return render(request, "admin/generate_knockouts_form.html", {
            "form": form,
            "seasons": queryset,
            "action": "action_generate_knockouts",
        })

    action_generate_knockouts.short_description = "Generate Knockout Bracket"

    # -----------------------------
    # FINAL GENERATION
    # -----------------------------
    @transaction.atomic
    def action_generate_final(self, request, queryset):
    
        from django.utils import timezone
        from datetime import timedelta

        if request.method == "POST":
            form = FinalGenerationForm(request.POST)
            if form.is_valid():
                fmt = form.cleaned_data["match_format"]
                start_date = form.cleaned_data.get("start_date") or timezone.now()

                for season in queryset:
                    sf = KnockoutRound.objects.filter(season=season, round_type='SF').first()
                    if not sf:
                        messages.error(request, f"Season {season} has no semifinals defined.")
                        continue

                    winners = []

                    for km in sf.matches.all():
                        winner = None

                        if km.is_played:
                            if km.home_goals > km.away_goals:
                                winner = km.home_club
                            elif km.away_goals > km.home_goals:
                                winner = km.away_club
                            else:
                                messages.error(request, f"Semi {km} is a draw; cannot decide winner.")

                        else:
                            fixtures = Fixture.objects.filter(
                                season=season,
                                group__isnull=True,
                                home_club__in=[km.home_club, km.away_club],
                                away_club__in=[km.home_club, km.away_club],
                            )

                            if fixtures.exists():
                                total_home = 0
                                total_away = 0
                                home_team = km.home_club
                                away_team = km.away_club

                                for f in fixtures:
                                    if hasattr(f, 'group_match') and f.group_match.is_played:
                                        if f.home_club_id == home_team.id:
                                            total_home += f.group_match.home_goals
                                            total_away += f.group_match.away_goals
                                        else:
                                            total_home += f.group_match.away_goals
                                            total_away += f.group_match.home_goals

                                if total_home > total_away:
                                    winner = home_team
                                elif total_away > total_home:
                                    winner = away_team
                                else:
                                    messages.error(request, f"Aggregate tie in semi: cannot decide winner for {km}.")
                            else:
                                messages.error(request, f"Semi {km} has no played fixtures or results.")

                        if winner:
                            winners.append(winner)

                    if len(winners) < 2:
                        messages.error(request, f"Not enough semi winners to create a final for {season}.")
                        continue

                    final_round, created = KnockoutRound.objects.get_or_create(
                        season=season,
                        round_type='F'
                    )

                    home = winners[0]
                    away = winners[1]

                    already_exists = final_round.matches.filter(
                        Q(home_club=home, away_club=away) |
                        Q(home_club=away, away_club=home)
                    ).exists()

                    if already_exists:
                        messages.info(request, f"Final already exists for {season}.")
                        continue

                    final_km = KnockoutMatch.objects.create(
                        round=final_round,
                        home_club=home,
                        away_club=away
                    )

                    created_fixtures = []

                    if fmt == 'single':
                        f = Fixture(
                            season=season,
                            home_club=home,
                            away_club=away,
                            date=start_date,
                            week_number=None,
                            group=None
                        )
                        f.save(create_match=False)
                        created_fixtures.append(f)

                    elif fmt == 'two_leg':
                        f1 = Fixture(season=season, home_club=home, away_club=away, date=start_date)
                        f1.save(create_match=False)
                        created_fixtures.append(f1)

                        f2 = Fixture(season=season, home_club=away, away_club=home, date=start_date + timedelta(days=7))
                        f2.save(create_match=False)
                        created_fixtures.append(f2)

                    elif fmt == 'best_of_three':
                        f1 = Fixture(season=season, home_club=home, away_club=away, date=start_date)
                        f1.save(create_match=False)
                        created_fixtures.append(f1)

                        f2 = Fixture(season=season, home_club=away, away_club=home, date=start_date + timedelta(days=7))
                        f2.save(create_match=False)
                        created_fixtures.append(f2)

                        f3 = Fixture(season=season, home_club=home, away_club=away, date=start_date + timedelta(days=14))
                        f3.save(create_match=False)
                        created_fixtures.append(f3)

                    messages.success(request, f"Final fixtures created for {season}: {len(created_fixtures)} fixture(s).")

                return None

        else:
            form = FinalGenerationForm()

        return render(request, "admin/generate_knockouts_form.html", {
            "form": form,
            "seasons": queryset,
            "action": "action_generate_final",
        })

    action_generate_final.short_description = "Generate Final from Semifinals"


# ============================================================
# SEASON AWARDS ADMIN
# ============================================================

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


# ============================================================
# REGISTER MODELS
# ============================================================


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('season', 'name')
    list_filter = ('season',)
    search_fields = ('name',)
    actions = [
        action_generate_group_fixtures_1x,
        action_generate_group_fixtures_2x,
        action_generate_group_fixtures_3x,
        action_generate_group_fixtures_4x,
    ]


admin.site.register(Club)
admin.site.register(Player, PlayerAdmin)
admin.site.register(Season, SeasonAdmin)
admin.site.register(Fixture, FixtureAdmin)
admin.site.register(PlayerMatchStats)
admin.site.register(PlayerSeasonStats, PlayerSeasonStatsAdmin)
admin.site.register(TeamSeasonStats, TeamSeasonStatsAdmin)
admin.site.register(SeasonAwards, SeasonAwardsAdmin)
@admin.register(KnockoutRound)
class KnockoutRoundAdmin(admin.ModelAdmin):
    list_display = ('season', 'round_type')
    list_filter = ('season', 'round_type')


@admin.register(KnockoutMatch)
class KnockoutMatchAdmin(admin.ModelAdmin):
    list_display = ('round', 'home_club', 'away_club', 'home_goals', 'away_goals', 'is_played')
    list_filter = ('round__season', 'is_played')
    inlines = [PlayerMatchStatsKnockoutInline]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        # limit home_players/away_players to players from the match's clubs
        obj_id = request.resolver_match.kwargs.get('object_id')
        if obj_id:
            try:
                km = KnockoutMatch.objects.select_related('home_club', 'away_club').get(pk=obj_id)
                if db_field.name == 'home_players' and km.home_club:
                    kwargs['queryset'] = Player.objects.filter(club=km.home_club)
                if db_field.name == 'away_players' and km.away_club:
                    kwargs['queryset'] = Player.objects.filter(club=km.away_club)
            except KnockoutMatch.DoesNotExist:
                pass

        return super().formfield_for_manytomany(db_field, request, **kwargs)
