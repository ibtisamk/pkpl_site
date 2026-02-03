from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from .models import KnockoutMatch, Season
from .services import resolve_knockout_placeholders
from .models import (
    GroupMatch,
    PlayerMatchStats,
    PlayerSeasonStats,
    TeamSeasonStats,
    KnockoutMatch,
)
from .services import resolve_knockout_placeholders


# ---------------------------------------------------------
# ENSURE TEAM SEASON STATS EXIST AS SOON AS GROUP MATCH IS CREATED
# ---------------------------------------------------------
@receiver(post_save, sender=GroupMatch)
def ensure_team_season_stats_exist(sender, instance, created, **kwargs):
    if not created:
        return

    match = instance
    season = match.fixture.season

    if not season.is_active:
        return

    home = match.fixture.home_club
    away = match.fixture.away_club

    # Create empty stats rows so groups always show teams
    TeamSeasonStats.objects.get_or_create(team=home, season=season)
    TeamSeasonStats.objects.get_or_create(team=away, season=season)


# ---------------------------------------------------------
# TEAM SEASON STATS — ALWAYS REBUILT (NO DOUBLE COUNTING)
# ---------------------------------------------------------
@receiver(post_save, sender=GroupMatch)
def update_team_stats(sender, instance, **kwargs):
    match = instance
    fixture = match.fixture
    season = fixture.season

    if not season.is_active:
        return

    home = fixture.home_club
    away = fixture.away_club

    # Rebuild stats for BOTH teams
    for team in [home, away]:
        stats, _ = TeamSeasonStats.objects.get_or_create(team=team, season=season)

        # Reset
        stats.played = 0
        stats.wins = 0
        stats.draws = 0
        stats.losses = 0
        stats.goals_for = 0
        stats.goals_against = 0
        stats.clean_sheets = 0
        stats.points = 0

        # Only count matches that were actually played
        all_matches = (
            GroupMatch.objects.filter(
                fixture__season=season,
                fixture__home_club=team,
                is_played=True
            )
            | GroupMatch.objects.filter(
                fixture__season=season,
                fixture__away_club=team,
                is_played=True
            )
        ).distinct()

        for m in all_matches:
            stats.played += 1

            # Determine GF/GA depending on home/away
            if m.fixture.home_club == team:
                gf = m.home_goals
                ga = m.away_goals
            else:
                gf = m.away_goals
                ga = m.home_goals

            stats.goals_for += gf
            stats.goals_against += ga

            if ga == 0:
                stats.clean_sheets += 1

            # Result
            if gf > ga:
                stats.wins += 1
                stats.points += 3
            elif gf < ga:
                stats.losses += 1
            else:
                stats.draws += 1
                stats.points += 1

        stats.save()


# ---------------------------------------------------------
# PLAYER SEASON STATS — ONLY INCREMENT ON CREATION
# ---------------------------------------------------------

def rebuild_player_season_stats(player_obj, season_obj):
    """Recompute and save PlayerSeasonStats for a player and season by
    aggregating all PlayerMatchStats rows belonging to that season."""
    from django.db.models import Q

    pms_qs = PlayerMatchStats.objects.filter(
        Q(group_match__fixture__season=season_obj) |
        Q(knockout_match__round__season=season_obj) |
        Q(fixture__season=season_obj),
        player=player_obj
    )

    total_goals = 0
    total_assists = 0
    total_appearances = 0
    total_clean_sheets = 0
    ratings = []

    for row in pms_qs:
        total_goals += row.goals
        total_assists += row.assists

        appeared = False
        if row.minutes_played and row.minutes_played > 0:
            appeared = True

        # check membership in home/away players where available
        if not appeared and getattr(row, 'group_match', None) and row.group_match is not None:
            if player_obj in row.group_match.home_players.all() or player_obj in row.group_match.away_players.all():
                appeared = True
        if not appeared and getattr(row, 'knockout_match', None) and row.knockout_match is not None:
            if player_obj in row.knockout_match.home_players.all() or player_obj in row.knockout_match.away_players.all():
                appeared = True
        if not appeared and getattr(row, 'fixture', None) and row.fixture is not None:
            # prefer group_match players if present on fixture
            if hasattr(row.fixture, 'group_match') and row.fixture.group_match is not None:
                gm = row.fixture.group_match
                if player_obj in gm.home_players.all() or player_obj in gm.away_players.all():
                    appeared = True

        if appeared:
            total_appearances += 1

        # clean sheet
        try:
            if getattr(row, 'group_match', None) and row.group_match is not None:
                gm = row.group_match
                if player_obj in gm.home_players.all() and gm.away_goals == 0:
                    total_clean_sheets += 1
                if player_obj in gm.away_players.all() and gm.home_goals == 0:
                    total_clean_sheets += 1
            elif getattr(row, 'knockout_match', None) and row.knockout_match is not None:
                km = row.knockout_match
                if player_obj in km.home_players.all() and km.away_goals == 0:
                    total_clean_sheets += 1
                if player_obj in km.away_players.all() and km.home_goals == 0:
                    total_clean_sheets += 1
        except Exception:
            pass

        if row.rating and row.rating > 0:
            ratings.append(row.rating)

    season_stats, _ = PlayerSeasonStats.objects.get_or_create(
        player=player_obj,
        season=season_obj,
        club=player_obj.club,
        manual=False,
    )

    season_stats.goals = total_goals
    season_stats.assists = total_assists
    season_stats.appearances = total_appearances
    season_stats.clean_sheets = total_clean_sheets
    season_stats.rating = sum(ratings) / len(ratings) if ratings else 0
    season_stats.save()


# When deleting a Season we want to avoid triggering rebuilds that recreate
# `PlayerSeasonStats` (or other objects) referencing the soon-to-be-deleted
# Season. Use a module-level flag toggled by pre_delete/post_delete of
# Season to skip rebuild handlers during a season deletion cascade.
_SKIP_REBUILD_DURING_SEASON_DELETE = False


@receiver(pre_delete, sender=Season)
def _pre_delete_season(sender, instance, **kwargs):
    global _SKIP_REBUILD_DURING_SEASON_DELETE
    _SKIP_REBUILD_DURING_SEASON_DELETE = True


@receiver(post_delete, sender=Season)
def _post_delete_season(sender, instance, **kwargs):
    global _SKIP_REBUILD_DURING_SEASON_DELETE
    _SKIP_REBUILD_DURING_SEASON_DELETE = False


def _resolve_season_from_pms(pms_obj):
    """Safely determine a Season from a PlayerMatchStats instance without
    triggering related-object access that may raise DoesNotExist during
    cascading deletes. Uses FK id fields and guarded queries.
    """
    # Try group_match by id
    try:
        gm_id = getattr(pms_obj, 'group_match_id', None)
        if gm_id:
            gm = GroupMatch.objects.filter(id=gm_id).select_related('fixture__season').first()
            if gm and getattr(gm, 'fixture', None) and getattr(gm.fixture, 'season', None):
                return gm.fixture.season
    except Exception:
        pass

    # Try knockout_match by id
    try:
        km_id = getattr(pms_obj, 'knockout_match_id', None)
        if km_id:
            km = KnockoutMatch.objects.filter(id=km_id).select_related('round__season').first()
            if km and getattr(km, 'round', None) and getattr(km.round, 'season', None):
                return km.round.season
    except Exception:
        pass

    # Try direct fixture by id
    try:
        fixture_id = getattr(pms_obj, 'fixture_id', None)
        if fixture_id:
            f = None
            from .models import Fixture
            f = Fixture.objects.filter(id=fixture_id).select_related('season').first()
            if f and getattr(f, 'season', None):
                return f.season
    except Exception:
        pass

    return None

@receiver(post_save, sender=PlayerMatchStats)
def update_player_season_stats(sender, instance, created, **kwargs):
    # Rebuild full season stats for the affected player/season to ensure consistency
    pms = instance

    # If we're deleting a Season, skip rebuilds to avoid recreating rows
    # that reference the deleting Season and trigger FK errors.
    if _SKIP_REBUILD_DURING_SEASON_DELETE:
        return

    season = _resolve_season_from_pms(pms)
    if not season or not season.is_active:
        return

    player = pms.player
    # Use module-level helper
    rebuild_player_season_stats(player, season)


# Ensure we also rebuild when a PlayerMatchStats row is deleted
@receiver(post_delete, sender=PlayerMatchStats)
def player_match_stats_deleted(sender, instance, **kwargs):
    pms = instance

    if _SKIP_REBUILD_DURING_SEASON_DELETE:
        return

    season = _resolve_season_from_pms(pms)
    if not season or not season.is_active:
        return

    # rebuild for the player
    rebuild_player_season_stats(pms.player, season)


# Recompute player season stats for all players involved in a match when the match is saved
@receiver(post_save, sender=GroupMatch)
def rebuild_players_for_group_match(sender, instance, **kwargs):
    match = instance
    season = match.fixture.season if getattr(match, 'fixture', None) else None
    if not season or not season.is_active:
        return

    if _SKIP_REBUILD_DURING_SEASON_DELETE:
        return

    players = set()
    try:
        players.update(list(match.home_players.all()))
    except Exception:
        pass
    try:
        players.update(list(match.away_players.all()))
    except Exception:
        pass

    # Also include any players who have PlayerMatchStats rows referencing this group match
    for pid in PlayerMatchStats.objects.filter(group_match=match).values_list('player', flat=True).distinct():
        try:
            players.add(match.home_players.model.objects.get(pk=pid))
        except Exception:
            try:
                players.add(match.away_players.model.objects.get(pk=pid))
            except Exception:
                pass

    for p in players:
        rebuild_player_season_stats(p, season)


@receiver(post_save, sender=KnockoutMatch)
def rebuild_players_for_knockout_match(sender, instance, **kwargs):
    match = instance
    season = match.round.season if getattr(match, 'round', None) else None
    if not season or not season.is_active:
        return

    if _SKIP_REBUILD_DURING_SEASON_DELETE:
        return

    players = set()
    try:
        players.update(list(match.home_players.all()))
    except Exception:
        pass
    try:
        players.update(list(match.away_players.all()))
    except Exception:
        pass

    for pid in PlayerMatchStats.objects.filter(knockout_match=match).values_list('player', flat=True).distinct():
        # try to fetch player by id
        from .models import Player
        try:
            players.add(Player.objects.get(pk=pid))
        except Exception:
            pass

    for p in players:
        rebuild_player_season_stats(p, season)


# ---------------------------------------------------------
# KNOCKOUT MATCH SAVE — RESOLVE PLACEHOLDERS WHEN RESULTS ENTERED
# ---------------------------------------------------------
@receiver(post_save, sender=KnockoutMatch)
def knockout_match_saved(sender, instance, **kwargs):
    return


@receiver(post_save, sender=KnockoutMatch)
def knockout_match_saved(sender, instance, **kwargs):
    # Prevent recursive triggering
    if getattr(instance, "_skip_signal", False):
        return

    try:
        # Mark this instance so internal saves don't re-trigger the signal
        instance._skip_signal = True

        # Call your resolver
        resolve_knockout_placeholders(instance.round.season)

    except Exception:
        pass

    finally:
        # Always remove the flag
        if hasattr(instance, "_skip_signal"):
            del instance._skip_signal


