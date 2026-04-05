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
    TeamOfTheWeek,
    TeamOfTheWeekSelection,
    REGIONS,
    MATCH_POSITIONS,
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
    Shows a form to upload team logo before approval.
    Skips registrations that are already approved to prevent duplicates.
    """
    from django import forms
    from django.core.files.storage import default_storage
    
    # If POST with logo files, process approvals
    if request.method == 'POST' and 'confirm_approval' in request.POST:
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

                    # Handle logo upload
                    logo_field_name = f'logo_{registration.id}'
                    if logo_field_name in request.FILES:
                        club.logo = request.FILES[logo_field_name]
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
        
        return None
    
    # Show logo upload form
    context = {
        'registrations': queryset.filter(approved=False),
        'action_name': 'approve_registration',
        'title': 'Upload Team Logos for Approval',
    }
    return render(request, 'admin/approve_registration_form.html', context)


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
    search_fields = ('gamertag', 'club__name')


# ============================================================
# PLAYER MATCH STATS INLINE
# ============================================================

class PlayerMatchStatsGroupInline(admin.TabularInline):
    model = PlayerMatchStats
    fk_name = 'group_match'
    extra = 0
    fields = ('player', 'position_played', 'goals', 'assists', 'minutes_played', 'rating', 'man_of_the_match')
    autocomplete_fields = ['player']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('player', 'player__club')

class PlayerMatchStatsKnockoutInline(admin.TabularInline):
    model = PlayerMatchStats
    fk_name = 'knockout_match'
    extra = 0
    fields = ('player', 'position_played', 'goals', 'assists', 'minutes_played', 'rating', 'man_of_the_match')
    autocomplete_fields = ['player']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('player', 'player__club')


# ============================================================
# GROUP MATCH ADMIN (RENAMED FROM MatchAdmin)
# ============================================================

@admin.register(GroupMatch)
class GroupMatchAdmin(admin.ModelAdmin):
    list_display = ('fixture', 'home_goals', 'away_goals', 'is_played')
    list_filter = (
        'fixture__season',
        'is_played',
        'fixture__home_club',
        'fixture__away_club',
        'fixture__week_number',
        'fixture__group',
        'fixture__date',
    )
    inlines = [PlayerMatchStatsGroupInline]
    autocomplete_fields = ['home_players', 'away_players']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "fixture":
            kwargs["queryset"] = Fixture.objects.select_related(
                'season', 'home_club', 'away_club', 'group'
            ).order_by('-date')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'fixture',
            'fixture__season',
            'fixture__home_club',
            'fixture__away_club',
            'fixture__group'
        )

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

    def save_related(self, request, form, formsets, change):
        """
        Skip signal during formset save to prevent timeout, then trigger signal once.
        """
        from league.signals import get_skip_rebuild_matches
        
        obj = form.instance
        skip_matches = get_skip_rebuild_matches()
        skip_matches.add(('group', obj.id))
        
        try:
            super().save_related(request, form, formsets, change)
        finally:
            skip_matches.discard(('group', obj.id))
            # Trigger the signal manually once after everything is saved
            # This avoids multiple signal fires during inline saves
            from league.signals import update_team_stats
            update_team_stats(sender=GroupMatch, instance=obj)
    
    def save_model(self, request, obj, form, change):
        """Save the match and skip signal during the save itself."""
        from league.signals import get_skip_rebuild_matches
        skip_matches = get_skip_rebuild_matches()
        if obj.id:
            skip_matches.add(('group', obj.id))
        
        try:
            super().save_model(request, obj, form, change)
        finally:
            if obj.id:
                skip_matches.discard(('group', obj.id))

    # Removed formfield_for_manytomany override; not needed for custom Group model

    class Media:
        js = ('league/match_admin.js',)


# ============================================================
# FIXTURE ADMIN
# ============================================================

class FixtureAdmin(admin.ModelAdmin):
    list_display = ('season_display', 'home_club_display', 'away_club_display', 'date', 'week_number', 'group_display')
    list_filter = ('season', 'week_number', 'group')
    search_fields = ('home_club__name', 'away_club__name')
    list_select_related = ('season', 'home_club', 'away_club', 'group')

    def season_display(self, obj):
        if not obj.season_id:
            return '-'
        try:
            return obj.season
        except Season.DoesNotExist:
            return f'Missing Season ({obj.season_id})'
    season_display.short_description = 'season'
    season_display.admin_order_field = 'season'

    def home_club_display(self, obj):
        if not obj.home_club_id:
            return '-'
        try:
            return obj.home_club
        except Club.DoesNotExist:
            return f'Missing Club ({obj.home_club_id})'
    home_club_display.short_description = 'home club'
    home_club_display.admin_order_field = 'home_club'

    def away_club_display(self, obj):
        if not obj.away_club_id:
            return '-'
        try:
            return obj.away_club
        except Club.DoesNotExist:
            return f'Missing Club ({obj.away_club_id})'
    away_club_display.short_description = 'away club'
    away_club_display.admin_order_field = 'away_club'

    def group_display(self, obj):
        if not obj.group_id:
            return '-'
        try:
            return obj.group
        except Group.DoesNotExist:
            return f'Missing Group ({obj.group_id})'
    group_display.short_description = 'group'
    group_display.admin_order_field = 'group'


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
    
    def get_queryset(self, request):
        from django.db.utils import ProgrammingError
        qs = super().get_queryset(request)
        try:
            # Try to access queryset normally
            list(qs[:1])
            return qs
        except ProgrammingError:
            # skill_rating column doesn't exist yet
            return qs.defer('skill_rating')


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
class GroupWithMembersAdmin(admin.ModelAdmin):
    list_display = ('season', 'name')
    list_filter = ('season',)
    search_fields = ('name',)
    actions = [
        action_generate_group_fixtures_1x,
        action_generate_group_fixtures_2x,
        action_generate_group_fixtures_3x,
        action_generate_group_fixtures_4x,
    ]


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 1
    autocomplete_fields = ['club']


class GroupWithMembersAdmin(admin.ModelAdmin):
    list_display = ('season', 'name', 'get_member_count')
    list_filter = ('season',)
    search_fields = ('name',)
    inlines = [GroupMembershipInline]
    actions = [
        action_generate_group_fixtures_1x,
        action_generate_group_fixtures_2x,
        action_generate_group_fixtures_3x,
        action_generate_group_fixtures_4x,
    ]
    
    def get_member_count(self, obj):
        return obj.members.count()
    get_member_count.short_description = 'Teams'


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

    def save_related(self, request, form, formsets, change):
        """
        Skip signal during formset save to prevent timeout.
        """
        from league.signals import get_skip_rebuild_matches
        obj = form.instance
        skip_matches = get_skip_rebuild_matches()
        skip_matches.add(('knockout', obj.id))
        
        try:
            super().save_related(request, form, formsets, change)
        finally:
            skip_matches.discard(('knockout', obj.id))
    
    def save_model(self, request, obj, form, change):
        """Save the match and skip signal."""
        from league.signals import get_skip_rebuild_matches
        skip_matches = get_skip_rebuild_matches()
        if obj.id:
            skip_matches.add(('knockout', obj.id))
        
        try:
            super().save_model(request, obj, form, change)
        finally:
            if obj.id:
                skip_matches.discard(('knockout', obj.id))


# ============================================================
# TEAM OF THE WEEK
# ============================================================

class TeamOfTheWeekSelectionInline(admin.TabularInline):
    model = TeamOfTheWeekSelection
    extra = 1
    fields = ('position', 'player', 'lineup_position', 'games_played', 'goals', 'assists', 'clean_sheets', 'avg_rating', 'skill_rating')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "player":
            # This will be enhanced by JavaScript to filter based on position
            # For now, show all season players by skill rating (no hard cap)
            from .models import PlayerSeasonStats, Season
            
            active_season = Season.objects.filter(is_active=True).first()
            if active_season:
                # Get all players ranked by skill rating
                top_stats = PlayerSeasonStats.objects.filter(
                    season=active_season,
                    appearances__gte=1
                ).select_related('player', 'player__club').order_by('-skill_rating')
                
                # Create choices with rank numbers
                from django.forms import ModelChoiceField
                
                class RankedPlayerChoiceField(ModelChoiceField):
                    def label_from_instance(self, obj):
                        # Find rank in the stats
                        rank = None
                        for idx, stat in enumerate(top_stats, 1):
                            if stat.player_id == obj.id:
                                rank = idx
                                break
                        
                        if rank:
                            return f"#{rank} - {obj.gamertag} ({obj.position}) - {obj.club.short_name or obj.club.name}"
                        return f"{obj.gamertag} ({obj.position}) - {obj.club.short_name or obj.club.name}"
                
                player_ids = [stat.player_id for stat in top_stats]
                kwargs["queryset"] = Player.objects.filter(id__in=player_ids)
                kwargs["widget"] = kwargs.get("widget", None)
                
                field = RankedPlayerChoiceField(**kwargs)
                return field
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.action(description="Generate TOTW automatically")
def action_generate_totw(modeladmin, request, queryset):
    """Auto-generate Team of the Week selections based on player performance"""
    from django.db.models import Avg, Sum, Count, Q
    from datetime import datetime
    
    for totw in queryset:
        if totw.selections.exists():
            messages.warning(request, f"{totw} already has selections. Skipping.")
            continue
        
        # Get all matches in the date range
        matches_q = Q(fixture__season=totw.season, is_played=True)
        if totw.start_date and totw.end_date:
            matches_q &= Q(fixture__date__range=[totw.start_date, totw.end_date])
        
        group_matches = GroupMatch.objects.filter(matches_q).select_related('fixture')
        
        # Also check knockout matches if applicable
        ko_matches_q = Q(round__season=totw.season, is_played=True)
        if totw.week_type == 'KO':
            knockout_matches = KnockoutMatch.objects.filter(ko_matches_q)
        else:
            knockout_matches = KnockoutMatch.objects.none()
        
        # Get all player stats from these matches
        match_stats_qs = PlayerMatchStats.objects.filter(
            Q(group_match__in=group_matches) | Q(knockout_match__in=knockout_matches)
        ).filter(
            position_played__isnull=False  # Only include players with position recorded
        )
        
        # Aggregate stats by player and position
        player_stats = match_stats_qs.values('player_id', 'position_played').annotate(
            games=Count('id'),
            avg_rating=Avg('rating'),
            total_goals=Sum('goals'),
            total_assists=Sum('assists'),
            motm_count=Count('id', filter=Q(man_of_the_match=True))
        ).filter(
            games__gte=2  # Minimum 2 games played in period
        )
        
        # Position quotas
        position_quotas = {
            'GK': 1,
            'DEF': 4,
            'MID': 3,
            'ATT': 3,
        }
        
        selections_created = 0
        lineup_pos = 1
        
        for position, quota in position_quotas.items():
            # Get top players for this position
            top_players = player_stats.filter(
                position_played=position
            ).order_by('-avg_rating', '-total_goals', '-total_assists')[:quota]
            
            for stat in top_players:
                try:
                    player = Player.objects.get(id=stat['player_id'])
                    
                    TeamOfTheWeekSelection.objects.create(
                        totw=totw,
                        player=player,
                        position=position,
                        games_played=stat['games'],
                        goals=stat['total_goals'] or 0,
                        assists=stat['total_assists'] or 0,
                        avg_rating=round(stat['avg_rating'], 2),
                        lineup_position=lineup_pos
                    )
                    selections_created += 1
                    lineup_pos += 1
                except Player.DoesNotExist:
                    continue
        
        messages.success(request, f"Generated {selections_created} selections for {totw}")


@admin.register(TeamOfTheWeek)
class TeamOfTheWeekAdmin(admin.ModelAdmin):
    list_display = ('title', 'season', 'totw_number', 'gameweek_range', 'week_type', 'is_published', 'date_range')
    list_filter = ('season', 'week_type', 'is_published')
    search_fields = ('season__name',)
    inlines = [TeamOfTheWeekSelectionInline]
    actions = [action_generate_totw, 'action_publish_totw']
    
    class Media:
        js = ('league/totw_admin.js',)
    
    def action_publish_totw(self, request, queryset):
        """Publish TOTW after showing formation confirmation"""
        from django.db.models import Count
        
        for totw in queryset:
            # Count positions
            position_counts = totw.selections.values('position').annotate(count=Count('id'))
            counts = {pc['position']: pc['count'] for pc in position_counts}
            
            gk_count = counts.get('GK', 0)
            def_count = counts.get('DEF', 0)
            mid_count = counts.get('MID', 0)
            att_count = counts.get('ATT', 0)
            total = gk_count + def_count + mid_count + att_count
            
            # Validate formation
            if total != 11:
                self.message_user(request, f"TOTW #{totw.totw_number} has {total} players. Need exactly 11!", level='ERROR')
                continue
            
            if gk_count != 1:
                self.message_user(request, f"TOTW #{totw.totw_number} has {gk_count} goalkeepers. Need exactly 1!", level='ERROR')
                continue
            
            # Publish
            totw.is_published = True
            totw.save()
            
            formation = f"{def_count}-{mid_count}-{att_count}"
            self.message_user(request, f"Published TOTW #{totw.totw_number} with formation {formation} (GK: {gk_count}, DEF: {def_count}, MID: {mid_count}, ATT: {att_count})")
    
    action_publish_totw.short_description = "Publish selected TOTWs (with formation check)"
    
    def gameweek_range(self, obj):
        if obj.start_gameweek and obj.end_gameweek:
            if obj.start_gameweek == obj.end_gameweek:
                return f"Week {obj.start_gameweek}"
            return f"Weeks {obj.start_gameweek}-{obj.end_gameweek}"
        return "-"
    gameweek_range.short_description = "Gameweeks"
    
    def date_range(self, obj):
        if obj.start_date and obj.end_date:
            return f"{obj.start_date.strftime('%m/%d')} - {obj.end_date.strftime('%m/%d')}"
        return "-"
    date_range.short_description = "Date Range"
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('season', 'totw_number', 'week_type')
        }),
        ('Gameweek Coverage', {
            'fields': ('start_gameweek', 'end_gameweek'),
            'description': 'Specify which gameweeks are covered by this TOTW (e.g., 1-3, 4-5, etc.)'
        }),
        ('Date Range (for match filtering)', {
            'fields': ('start_date', 'end_date'),
            'description': 'Matches between these dates will be included in TOTW generation'
        }),
        ('Publishing', {
            'fields': ('is_published',)
        }),
    )


@admin.register(TeamOfTheWeekSelection)
class TeamOfTheWeekSelectionAdmin(admin.ModelAdmin):
    list_display = ('player', 'totw', 'position', 'lineup_position', 'games_played', 'goals', 'assists', 'avg_rating', 'skill_rating')
    list_filter = ('totw__season', 'totw__week_type', 'position')
    search_fields = ('player__gamertag', 'totw__season__name')
    autocomplete_fields = ['totw']
    fields = ('totw', 'position', 'player', 'lineup_position', 'games_played', 'goals', 'assists', 'clean_sheets', 'avg_rating', 'skill_rating')
    
    class Media:
        js = ('league/totw_admin.js',)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('player', 'player__club', 'totw', 'totw__season')
    
    def save_model(self, request, obj, form, change):
        """Auto-populate stats from PlayerSeasonStats when player is selected"""
        if obj.player and obj.totw:
            from .models import PlayerSeasonStats
            
            try:
                season_stats = PlayerSeasonStats.objects.get(
                    player=obj.player,
                    season=obj.totw.season
                )
                
                # Auto-populate all stats from current season
                obj.games_played = season_stats.appearances
                obj.goals = season_stats.goals
                obj.assists = season_stats.assists
                obj.clean_sheets = season_stats.clean_sheets
                obj.avg_rating = season_stats.rating
                obj.skill_rating = season_stats.skill_rating
                
            except PlayerSeasonStats.DoesNotExist:
                pass
        
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "player":
            from .models import PlayerSeasonStats, Season
            from django.forms import ModelChoiceField
            from django.db.models import Case, When
            
            active_season = Season.objects.filter(is_active=True).first()
            if not active_season:
                return super().formfield_for_foreignkey(db_field, request, **kwargs)
            
            # Show all players with at least one appearance.
            # Avoid hard per-position caps so weekly high performers are selectable.
            all_stats = list(
                PlayerSeasonStats.objects.filter(
                    season=active_season,
                    appearances__gte=1
                ).select_related('player', 'player__club').order_by('-skill_rating')
            )
            
            if not all_stats:
                return super().formfield_for_foreignkey(db_field, request, **kwargs)
            
            # Sort all stats by skill_rating for overall ranking
            all_stats.sort(key=lambda x: x.skill_rating, reverse=True)
            
            class RankedPlayerChoiceField(ModelChoiceField):
                def __init__(self, *args, stats_dict=None, **kwargs):
                    self.stats_dict = stats_dict or {}
                    super().__init__(*args, **kwargs)
                
                def label_from_instance(self, obj):
                    # Get rank and skill rating from dict
                    if obj.id in self.stats_dict:
                        rank, skill_rating = self.stats_dict[obj.id]
                        return f"#{rank} - {obj.gamertag} ({obj.position}) - Skill: {round(skill_rating, 2)}"
                    return f"{obj.gamertag} ({obj.position})"
            
            # Create dict mapping player_id to (rank, skill_rating)
            stats_dict = {}
            player_ids = []
            for idx, stat in enumerate(all_stats, 1):
                stats_dict[stat.player_id] = (idx, stat.skill_rating)
                player_ids.append(stat.player_id)
            
            # Preserve order using Case/When
            preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(player_ids)])
            queryset = Player.objects.filter(id__in=player_ids).select_related('club').order_by(preserved_order)
            
            kwargs["queryset"] = queryset
            field = RankedPlayerChoiceField(stats_dict=stats_dict, **kwargs)
            return field
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
