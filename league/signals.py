from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Match, PlayerMatchStats, PlayerSeasonStats, TeamSeasonStats


# ---------------------------------------------------------
# TEAM SEASON STATS UPDATE
# ---------------------------------------------------------
@receiver(post_save, sender=Match)
def update_team_stats(sender, instance, **kwargs):
    """
    Updates TeamSeasonStats whenever a Match is saved.
    Only applies to active seasons.
    Incremental update (same behavior as your old system).
    """
    match = instance
    fixture = match.fixture
    season = fixture.season

    if not season.is_active:
        return  # archived seasons stay manual

    home = fixture.home_club
    away = fixture.away_club

    home_stats, _ = TeamSeasonStats.objects.get_or_create(team=home, season=season)
    away_stats, _ = TeamSeasonStats.objects.get_or_create(team=away, season=season)

    # --- INCREMENTAL UPDATE (same behavior as your old code) ---
    home_stats.played += 1
    away_stats.played += 1

    home_stats.goals_for += match.home_goals
    home_stats.goals_against += match.away_goals

    away_stats.goals_for += match.away_goals
    away_stats.goals_against += match.home_goals

    # Clean sheets
    if match.away_goals == 0:
        home_stats.clean_sheets += 1
    if match.home_goals == 0:
        away_stats.clean_sheets += 1

    # Determine result
    if match.home_goals > match.away_goals:
        home_stats.wins += 1
        away_stats.losses += 1
        home_stats.points += 3
    elif match.away_goals > match.home_goals:
        away_stats.wins += 1
        home_stats.losses += 1
        away_stats.points += 3
    else:
        home_stats.draws += 1
        away_stats.draws += 1
        home_stats.points += 1
        away_stats.points += 1

    home_stats.save()
    away_stats.save()


# ---------------------------------------------------------
# PLAYER SEASON STATS UPDATE
# ---------------------------------------------------------
@receiver(post_save, sender=PlayerMatchStats)
def update_player_season_stats(sender, instance, **kwargs):
    """
    Updates PlayerSeasonStats whenever PlayerMatchStats is saved.
    Only applies to active seasons.
    Incremental update (same behavior as your old system).
    """
    pms = instance
    match = pms.match
    season = match.fixture.season

    if not season.is_active:
        return

    player = pms.player
    club = player.club

    season_stats, _ = PlayerSeasonStats.objects.get_or_create(
        player=player,
        season=season,
        club=club,
        manual=False
    )

    # --- INCREMENTAL UPDATE (same behavior as your old code) ---
    season_stats.goals += pms.goals
    season_stats.assists += pms.assists

    # Appearance = if minutes_played > 0 OR if player is in home/away list
    if pms.minutes_played > 0 or \
       player in match.home_players.all() or \
       player in match.away_players.all():
        season_stats.appearances += 1

    # Clean sheet logic
    clean_sheet = False
    if player in match.home_players.all() and match.away_goals == 0:
        clean_sheet = True
    if player in match.away_players.all() and match.home_goals == 0:
        clean_sheet = True

    if clean_sheet:
        season_stats.clean_sheets += 1

    # Rating update (simple average)
    if pms.rating > 0:
        if season_stats.appearances == 1:
            season_stats.rating = pms.rating
        else:
            season_stats.rating = (season_stats.rating + pms.rating) / 2

    season_stats.save()


# ---------------------------------------------------------
# DELETE HANDLING (keeps stats consistent)
# ---------------------------------------------------------
@receiver(post_delete, sender=PlayerMatchStats)
def rebuild_player_stats_on_delete(sender, instance, **kwargs):
    """
    When a PlayerMatchStats entry is deleted,
    rebuild that player's season stats from scratch.
    """
    pms = instance
    match = pms.match
    season = match.fixture.season
    player = pms.player
    club = player.club

    if not season.is_active:
        return

    season_stats, _ = PlayerSeasonStats.objects.get_or_create(
        player=player,
        season=season,
        club=club,
        manual=False
    )

    # Reset
    season_stats.goals = 0
    season_stats.assists = 0
    season_stats.appearances = 0
    season_stats.clean_sheets = 0
    season_stats.rating = 0

    # Rebuild from all remaining matches
    all_stats = PlayerMatchStats.objects.filter(
        player=player,
        match__fixture__season=season
    )

    for s in all_stats:
        season_stats.goals += s.goals
        season_stats.assists += s.assists

        if s.minutes_played > 0:
            season_stats.appearances += 1

        if s.rating > 0:
            if season_stats.rating == 0:
                season_stats.rating = s.rating
            else:
                season_stats.rating = (season_stats.rating + s.rating) / 2

        m = s.match
        if player in m.home_players.all() and m.away_goals == 0:
            season_stats.clean_sheets += 1
        if player in m.away_players.all() and m.home_goals == 0:
            season_stats.clean_sheets += 1

    season_stats.save()
