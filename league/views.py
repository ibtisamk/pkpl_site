from django.shortcuts import (
    render,
    get_object_or_404,
    redirect
)
from django.urls import reverse
from django.http import HttpResponseRedirect

from .forms import TeamRegistrationForm, PlayerRegistrationForm
from .models import (
    Club,
    Player,
    TeamRegistration,
    TeamRegistrationPlayer,
    PlayerSeasonStats,
    TeamSeasonStats,
    Season,
    PlayerMatchStats,
    Fixture,
    GroupMatch,
    KnockoutRound,
    KnockoutMatch,
    POSITIONS
)

from django.db.models import Q
from django.utils import timezone


# ---------------------------------------------------------
# TEAM REGISTRATION
# ---------------------------------------------------------
def register_team(request):
    if request.method == "POST":
        form = TeamRegistrationForm(request.POST)

        if form.is_valid():

            # Forbidden teams
            forbidden = ["Team A", "Team B", "Team C"]
            if form.cleaned_data["team_name"] in forbidden:
                form.add_error("team_name", "This team cannot register.")

            else:
                team = form.save()

                # Read players manually
                player_count = int(request.POST.get("player_count", 0))
                saved_players = 0

                for i in range(1, player_count + 1):
                    name = request.POST.get(f"player_name_{i}")
                    position = request.POST.get(f"player_position_{i}")

                    if name:
                        TeamRegistrationPlayer.objects.create(
                            team=team,
                            name=name,
                            position=position
                        )
                        saved_players += 1

                if saved_players < 1:
                    form.add_error(None, "At least 1 player is required.")
                else:
                    return redirect("register_success")

    else:
        form = TeamRegistrationForm()

    return render(request, "league/register_team.html", {
        "form": form,
        "positions": POSITIONS,   # <-- IMPORTANT for dropdown list
    })



# ---------------------------------------------------------
# PLAYER REGISTRATION
# ---------------------------------------------------------
def register_player(request):
    if request.method == "POST":
        form = PlayerRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("register_success")
    else:
        form = PlayerRegistrationForm()

    return render(request, "league/register_player.html", {
        "form": form,
    })


# ---------------------------------------------------------
# SUCCESS PAGE
# ---------------------------------------------------------
def register_success(request):
    return render(request, "league/register_success.html")


# ---------------------------------------------------------
# PPL3 HYPE PAGE (PRE-LAUNCH)
# ---------------------------------------------------------
def ppl3hype(request):
    clubs = Club.objects.all().order_by("id")
    return render(request, "league/ppl3hype.html", {"clubs": clubs})


# ---------------------------------------------------------
# REDIRECT /ppl3/ → PPL3 DASHBOARD
# ---------------------------------------------------------
def ppl3(request):
    return redirect("ppl3_overview")


# ---------------------------------------------------------
# ARCHIVE PAGES
# ---------------------------------------------------------
def ppl1(request):
    return render(request, "league/ppl1.html")


def ppl2(request):
    return render(request, "league/ppl2.html")


def story(request):
    return render(request, "league/story.html")


def teams(request):
    return redirect("/ppl3hype/#teams")


def rankings(request):
    return render(request, "league/rankings.html")


def register(request):
    return render(request, "league/register.html")


# ---------------------------------------------------------
# TEAM DETAIL (ALL SEASONS)
# ---------------------------------------------------------
def team_detail(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    seasons = Season.objects.all().order_by("id")

    season_rows = []
    for season in seasons:
        row = TeamSeasonStats.objects.filter(team=club, season=season).first()
        season_rows.append({
            "season": season,
            "played": row.played if row else None,
            "wins": row.wins if row else None,
            "draws": row.draws if row else None,
            "losses": row.losses if row else None,
            "points": row.points if row else None,
            "finish": row.finish_position if row else None,
        })

    # Optimize: Prefetch all season stats and match stats in advance
    from django.db.models import Avg
    players = Player.objects.filter(club=club).order_by("position").prefetch_related(
        'season_stats',
        'match_stats__group_match__fixture'
    )
    
    # Pre-fetch all season stats and match stats to avoid N+1
    all_player_stats = PlayerSeasonStats.objects.filter(
        player__in=players
    ).select_related('season', 'player')
    
    stats_by_player_season = {}
    for stat in all_player_stats:
        key = (stat.player_id, stat.season_id)
        stats_by_player_season[key] = stat
    
    # Pre-calculate average ratings per player per season
    from django.db.models import Avg
    avg_ratings = PlayerMatchStats.objects.filter(
        player__in=players,
        rating__gt=0
    ).values('player_id', 'group_match__fixture__season_id').annotate(
        avg_rating=Avg('rating')
    )
    
    ratings_dict = {}
    for item in avg_ratings:
        key = (item['player_id'], item['group_match__fixture__season_id'])
        ratings_dict[key] = round(item['avg_rating'], 2)

    squad_rows = []
    for player in players:
        per_season = []
        for season in seasons:
            stat = stats_by_player_season.get((player.id, season.id))
            avg_rating = ratings_dict.get((player.id, season.id))

            per_season.append({
                "season": season,
                "stats": stat,
                "avg_rating": avg_rating,
            })

        squad_rows.append({
            "player": player,
            "per_season": per_season,
        })

    achievements = {
        "champion": [],
        "runner_up": [],
        "third": [],
        "semis": [],
        "groups": [],
    }

    finishes = TeamSeasonStats.objects.filter(team=club).select_related('season')
    for s in finishes:
        if s.finish_position:
            achievements[s.finish_position].append(s.season.name)

    return render(request, "league/team_detail.html", {
        "club": club,
        "seasons": seasons,
        "season_rows": season_rows,
        "squad_rows": squad_rows,
        "achievements": achievements,
    })


# ---------------------------------------------------------
# PLAYER DETAIL (ALL SEASONS)
# ---------------------------------------------------------
def player_detail(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    seasons = Season.objects.all().order_by("id")

    # Optimize: Pre-fetch all stats for this player
    all_stats = PlayerSeasonStats.objects.filter(
        player=player
    ).select_related('season')
    stats_by_season = {stat.season_id: stat for stat in all_stats}
    
    # Optimize: Use database aggregation for average ratings
    from django.db.models import Avg
    avg_ratings_qs = PlayerMatchStats.objects.filter(
        player=player,
        rating__gt=0
    ).values('group_match__fixture__season_id').annotate(
        avg_rating=Avg('rating')
    )
    avg_ratings_dict = {
        item['group_match__fixture__season_id']: round(item['avg_rating'], 2)
        for item in avg_ratings_qs
    }

    season_rows = []
    for season in seasons:
        stat = stats_by_season.get(season.id)
        avg_rating = avg_ratings_dict.get(season.id)

        season_rows.append({
            "season": season,
            "stats": stat,
            "avg_rating": avg_rating,
        })

    # Optimize: Pre-fetch awards
    awards = []
    try:
        from .models import SeasonAwards
        all_awards = SeasonAwards.objects.filter(
            season__in=seasons
        ).select_related('season')
        
        for award in all_awards:
            titles = []
            if award.mvp_id and award.mvp_id == player.id:
                titles.append("MVP")
            if award.top_scorer_id and award.top_scorer_id == player.id:
                titles.append("Top Scorer")
            if award.top_assister_id and award.top_assister_id == player.id:
                titles.append("Top Assister")
            if award.best_defender_id and award.best_defender_id == player.id:
                titles.append("Best Defender")
            if award.best_midfielder_id and award.best_midfielder_id == player.id:
                titles.append("Best Midfielder")

            if titles:
                awards.append({"season": award.season.name, "titles": titles})
    except Exception:
        pass

    return render(request, "league/player_detail.html", {
        "player": player,
        "season_rows": season_rows,
        "awards": awards,
    })


# ---------------------------------------------------------
# ALL PLAYERS PAGE
# ---------------------------------------------------------
def all_players(request):
    from django.db.models import Sum, Avg, Count, Q, Case, When, IntegerField
    
    # Fetch all players with their clubs in one query
    players = Player.objects.select_related("club").all().order_by("gamertag")
    
    # Aggregate all stats per player in ONE query
    player_aggregates = PlayerSeasonStats.objects.values('player_id').annotate(
        total_apps=Sum('appearances'),
        total_goals=Sum('goals'),
        total_assists=Sum('assists'),
        total_clean_sheets=Sum('clean_sheets')
    )
    aggregates_dict = {item['player_id']: item for item in player_aggregates}
    
    # Calculate average ratings and MOTM counts in ONE query
    match_aggregates = PlayerMatchStats.objects.filter(
        rating__gt=0
    ).values('player_id').annotate(
        avg_rating=Avg('rating'),
        motm_count=Count('id', filter=Q(man_of_the_match=True))
    )
    match_dict = {item['player_id']: item for item in match_aggregates}
    
    # Fetch all season awards in one query
    try:
        from .models import SeasonAwards
        all_awards = SeasonAwards.objects.select_related('season').all()
    except:
        all_awards = []
    
    # Build awards lookup by player
    awards_by_player = {}
    for award in all_awards:
        for field_name, label in [
            ('mvp_id', 'MVP'),
            ('top_scorer_id', 'Top Scorer'),
            ('top_assister_id', 'Top Assister'),
            ('best_defender_id', 'Best Defender'),
            ('best_midfielder_id', 'Best Midfielder')
        ]:
            player_id = getattr(award, field_name, None)
            if player_id:
                if player_id not in awards_by_player:
                    awards_by_player[player_id] = []
                awards_by_player[player_id].append(f"{label} ({award.season.name})")
    
    # Build player data list
    player_data = []
    for player in players:
        # Get aggregated stats
        agg = aggregates_dict.get(player.id, {})
        match_agg = match_dict.get(player.id, {})
        
        avg_rating = match_agg.get('avg_rating')
        if avg_rating:
            avg_rating = round(avg_rating, 2)
        
        player_data.append({
            "player": player,
            "club": player.club.name if player.club else "Free Agent",
            "apps": agg.get('total_apps', 0),
            "goals": agg.get('total_goals', 0),
            "assists": agg.get('total_assists', 0),
            "clean_sheets": agg.get('total_clean_sheets', 0),
            "avg_rating": avg_rating,
            "motm_count": match_agg.get('motm_count', 0),
            "awards": awards_by_player.get(player.id, []),
        })
    
    return render(request, "league/all_players.html", {
        "player_data": player_data,
    })
    
    return render(request, "league/all_players.html", {
        "player_data": player_data,
    })

# ---------------------------------------------------------
# PPL3 DASHBOARD — FULLY REWRITTEN
# ---------------------------------------------------------

def ppl3_overview(request):
    season = Season.objects.filter(is_active=True).first()
    if not season:
        return render(request, "league/ppl3/overview.html", {"season": None})

    # -----------------------------
    # GROUPS + STANDINGS
    # -----------------------------
    groups = season.groups.prefetch_related(
        'members__club'
    ).all()

    group_data = []
    for group in groups:
        clubs = [gm.club for gm in group.members.all()]
        standings = (
            TeamSeasonStats.objects
            .filter(season=season, team__in=clubs)
            .select_related('team')
            .order_by("-points", "-goal_difference", "-goals_for")
        )
        group_data.append({
            "group": group,
            "standings": standings,
        })

    # -----------------------------
    # UPCOMING FIXTURES (SNAPSHOT)
    # -----------------------------
    fixtures = (
        Fixture.objects
        .filter(season=season)
        .filter(Q(group_match__is_played=False) | Q(group_match__isnull=True))
        .select_related('home_club', 'away_club', 'group_match')
        .order_by("date")[:10]
    )

    # All results: include played group fixtures and played knockout matches
    results = []
    played_fixtures = (
        Fixture.objects
        .filter(season=season, group_match__is_played=True)
        .select_related('home_club', 'away_club', 'group_match')
        .order_by("-date")
    )
    for f in played_fixtures:
        results.append({
            "type": "group_fixture",
            "date": f.date,
            "home": f.home_club.name,
            "away": f.away_club.name,
            "score": f"{f.group_match.home_goals}-{f.group_match.away_goals}",
            "detail_url": reverse('ppl3_match_detail', args=[f.group_match.id]) if hasattr(f, 'group_match') else None,
        })

    # include knockout match results
    kms = []
    try:
        kms = list(KnockoutRound.objects.filter(season=season).prefetch_related(
            'matches__home_club',
            'matches__away_club'
        ))
        round_order = {"R16": 0, "QF": 1, "SF": 2, "F": 3, "3P": 4}
        kms = sorted(kms, key=lambda r: round_order.get(r.round_type, 99))
    except Exception:
        kms = []
    for rnd in kms:
        for m in rnd.matches.filter(is_played=True):
            results.append({
                "type": "knockout",
                "date": None,
                "home": m.home_club.name if m.home_club else m.home_placeholder,
                "away": m.away_club.name if m.away_club else m.away_placeholder,
                "score": f"{m.home_goals}-{m.away_goals}",
                "detail_url": reverse('ppl3_match_detail', args=[m.id]),
            })

    # -----------------------------
    # KNOCKOUT ROUNDS + MATCHES
    # -----------------------------
    rounds_qs = list(KnockoutRound.objects.filter(season=season).prefetch_related(
        'matches__home_club',
        'matches__away_club'
    ))
    round_order = {"R16": 0, "QF": 1, "SF": 2, "F": 3, "3P": 4}
    rounds = sorted(rounds_qs, key=lambda r: round_order.get(r.round_type, 99))

    knockout_data = []
    for rnd in rounds:
        formatted_matches = []

        # Deduplicate pairings (ignore order) and limit results shown on overview
        seen_pairs = set()
        max_display = 6

        for m in rnd.matches.all():
            # Represent each side by club id if present, otherwise by placeholder text
            left = f"C{m.home_club.id}" if m.home_club else f"P{m.home_placeholder}"
            right = f"C{m.away_club.id}" if m.away_club else f"P{m.away_placeholder}"
            pair_key = tuple(sorted([left, right]))

            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            home = m.home_club.name if m.home_club else m.home_placeholder
            away = m.away_club.name if m.away_club else m.away_placeholder

            # Try to find a fixture+match for a detail link (if fixtures were created)
            detail_url = None
            try:
                fixture = Fixture.objects.filter(season=season, home_club=m.home_club, away_club=m.away_club).first()
                if fixture and hasattr(fixture, 'group_match'):
                    detail_url = reverse('ppl3_match_detail', args=[fixture.group_match.id])
            except Exception:
                detail_url = None

            # If we couldn't find a linked group fixture, link directly to the knockout match detail
            if not detail_url:
                try:
                    detail_url = reverse('ppl3_match_detail', args=[m.id])
                except Exception:
                    detail_url = None

            formatted_matches.append({
                "match": m,
                "home": home,
                "away": away,
                "played": m.is_played,
                "score": f"{m.home_goals}-{m.away_goals}" if m.is_played else None,
                "detail_url": detail_url,
            })

            if len(formatted_matches) >= max_display:
                break

        knockout_data.append({
            "round": rnd,
            "matches": formatted_matches,
        })

    # -----------------------------
    # TOP 10 PLAYERS SNAPSHOT
    # -----------------------------
    top_players = (
        PlayerSeasonStats.objects
        .filter(season=season, appearances__gte=1)
        .select_related('player', 'club', 'player__club')
        .order_by('-rating', '-goals', '-assists')[:10]
    )

    # -----------------------------
    # TOP 5 SCORERS & ASSISTERS
    # -----------------------------
    top_scorers = (
        PlayerSeasonStats.objects
        .filter(season=season, goals__gt=0)
        .select_related('player', 'club', 'player__club')
        .order_by('-goals', '-assists', '-rating')[:5]
    )

    top_assisters = (
        PlayerSeasonStats.objects
        .filter(season=season, assists__gt=0)
        .select_related('player', 'club', 'player__club')
        .order_by('-assists', '-goals', '-rating')[:5]
    )

    return render(request, "league/ppl3/overview.html", {
        "season": season,
        "groups": group_data,
        "fixtures": fixtures,
        "results": results,
        "knockouts": knockout_data,
        "top_players": top_players,
        "top_scorers": top_scorers,
        "top_assisters": top_assisters,
    })


def ppl3_rankings(request):
    """
    PPL3 player rankings with filtering by position and gameweek.
    """
    season = Season.objects.filter(is_active=True).first()
    if not season:
        return render(request, "league/ppl3/rankings.html", {"season": None})

    # Get filter parameters
    position_filter = request.GET.get('position', 'all')
    gameweek_filter = request.GET.get('gameweek', 'all')

    # Base queryset
    players_qs = (
        PlayerSeasonStats.objects
        .filter(season=season, appearances__gte=1)
        .select_related('player', 'club', 'player__club')
    )

    # Apply position filter
    position_map = {
        'attackers': ['ST', 'LW', 'RW'],
        'midfielders': ['CM', 'CDM', 'CAM', 'LW', 'RW'],
        'defenders': ['LB', 'CB', 'RB'],
        'goalkeepers': ['GK'],
    }

    if position_filter in position_map:
        players_qs = players_qs.filter(player__position__in=position_map[position_filter])

    # Note: Gameweek filtering would require PlayerMatchStats aggregation
    # For now, we'll show season totals and add gameweek support later if needed
    if gameweek_filter != 'all':
        try:
            week_num = int(gameweek_filter)
            # This would require filtering by week_number in fixtures
            # For now, showing all stats but we can enhance this
        except ValueError:
            pass

    # Order by rating, then goals, then assists
    players = players_qs.order_by('-rating', '-goals', '-assists')

    # Position tabs for template
    positions = [
        {'key': 'all', 'label': 'Overall'},
        {'key': 'attackers', 'label': 'Attackers'},
        {'key': 'midfielders', 'label': 'Midfielders'},
        {'key': 'defenders', 'label': 'Defenders'},
        {'key': 'goalkeepers', 'label': 'Goalkeepers'},
    ]

    # Get available gameweeks
    gameweeks = list(
        Fixture.objects
        .filter(season=season, week_number__isnull=False)
        .values_list('week_number', flat=True)
        .distinct()
        .order_by('week_number')
    )

    # Top scorers and assisters (full lists)
    top_scorers = (
        PlayerSeasonStats.objects
        .filter(season=season, goals__gt=0)
        .select_related('player', 'club')
        .order_by('-goals', '-assists', '-rating')
    )

    top_assisters = (
        PlayerSeasonStats.objects
        .filter(season=season, assists__gt=0)
        .select_related('player', 'club')
        .order_by('-assists', '-goals', '-rating')
    )

    return render(request, "league/ppl3/rankings.html", {
        "season": season,
        "players": players,
        "positions": positions,
        "current_position": position_filter,
        "gameweeks": gameweeks,
        "current_gameweek": gameweek_filter,
        "top_scorers": top_scorers,
        "top_assisters": top_assisters,
    })


def upcoming_fixtures(request):
    fixtures = Fixture.objects.filter(
        Q(group_match__is_played=False) | Q(group_match__isnull=True)
    ).select_related(
        'home_club',
        'away_club',
        'group',
        'group_match'
    ).order_by("-date", "id")
    return render(request, "fixtures/upcoming.html", {"fixtures": fixtures})


def results(request):
    fixtures = Fixture.objects.filter(
        group_match__is_played=True
    ).select_related(
        'home_club',
        'away_club',
        'group',
        'group_match'
    ).order_by("-date")
    return render(request, "fixtures/results.html", {"fixtures": fixtures})


# ---------------------------------------------------------
# GROUPS PAGE
# ---------------------------------------------------------
def ppl3_groups(request):
    season = Season.objects.filter(is_active=True).first()
    if not season:
        return render(request, "league/ppl3/groups.html", {"season": None})

    groups = season.groups.prefetch_related('members__club').all()

    group_data = []
    for group in groups:
        clubs = [gm.club for gm in group.members.all()]
        standings = (
            TeamSeasonStats.objects
            .filter(season=season, team__in=clubs)
            .select_related('team')
            .order_by("-points", "-goal_difference", "-goals_for")
        )
        group_data.append({
            "group": group,
            "standings": standings,
        })

    return render(request, "league/ppl3/groups.html", {
        "season": season,
        "groups": group_data,
    })


# ---------------------------------------------------------
# FIXTURES PAGE
# ---------------------------------------------------------
def ppl3_fixtures(request):
    season = Season.objects.filter(is_active=True).first()
    if not season:
        return render(request, "league/ppl3/fixtures.html", {"season": None})

    group_fixtures = (
        Fixture.objects
        .filter(season=season, group__isnull=False)
        .select_related('home_club', 'away_club', 'group', 'group_match')
        .order_by("week_number", "date")
    )

    # For knockout fixtures, show fixtures created for knockout ties (fixtures with no group)
    knockout_fixtures = (
        Fixture.objects
        .filter(season=season, group__isnull=True)
        .select_related('home_club', 'away_club', 'group_match')
        .order_by('date')
    )

    return render(request, "league/ppl3/fixtures.html", {
        "season": season,
        "group_fixtures": group_fixtures,
        "knockout_fixtures": knockout_fixtures,
    })


# ---------------------------------------------------------
# KNOCKOUTS PAGE
# ---------------------------------------------------------
def ppl3_knockouts(request):
    season = Season.objects.filter(is_active=True).first()
    if not season:
        return render(request, "league/ppl3/knockouts.html", {"season": None})

    rounds = KnockoutRound.objects.filter(season=season).prefetch_related(
        'matches__home_club',
        'matches__away_club'
    ).order_by("id")

    knockout_data = []
    for rnd in rounds:
        formatted_matches = []

        for km in rnd.matches.all():
            # Include matches that have results or have participating clubs
            if not km.home_club and not km.away_club and not km.is_played:
                continue

            had_recorded = False

            # Find all fixtures for this tie (both directions)
            fixtures = Fixture.objects.filter(season=season, group__isnull=True).filter(
                Q(home_club=km.home_club, away_club=km.away_club) | Q(home_club=km.away_club, away_club=km.home_club)
            ).select_related('home_club', 'away_club', 'group_match').order_by('date')

            for f in fixtures:
                if hasattr(f, 'group_match'):
                    match = f.group_match
                    formatted_matches.append({
                        "match": match,
                        "home": f.home_club.name,
                        "away": f.away_club.name,
                        "played": match.is_played,
                        "score": f"{match.home_goals}-{match.away_goals}" if match.is_played else None,
                        "detail_url": reverse('ppl3_match_detail', args=[match.id]),
                    })
                    had_recorded = True

            # Fallback: show km if it has its own recorded score
            if not had_recorded and km.is_played:
                formatted_matches.append({
                    "match": km,
                    "home": km.home_club.name if km.home_club else km.home_placeholder,
                    "away": km.away_club.name if km.away_club else km.away_placeholder,
                    "played": True,
                    "score": f"{km.home_goals}-{km.away_goals}",
                    "detail_url": None,
                })

        knockout_data.append({
            "round": rnd,
            "matches": formatted_matches,
        })

    return render(request, "league/ppl3/knockouts.html", {
        "season": season,
        "rounds": knockout_data,
    })


# ---------------------------------------------------------
# MATCH DETAIL
# ---------------------------------------------------------
def ppl3_match_detail(request, match_id):
    # Try GroupMatch first, then KnockoutMatch
    match = GroupMatch.objects.filter(id=match_id).select_related(
        'fixture__home_club',
        'fixture__away_club',
        'fixture__season'
    ).first()
    if match:
        stats = PlayerMatchStats.objects.filter(group_match=match).select_related(
            "player",
            "player__club"
        ).order_by('-rating', '-goals', '-assists')
        return render(request, "league/ppl3/match_detail.html", {"match": match, "stats": stats})

    # Fallback to KnockoutMatch
    from .models import KnockoutMatch
    km = KnockoutMatch.objects.filter(id=match_id).select_related(
        'home_club',
        'away_club',
        'round__season'
    ).first()
    if km:
        stats = PlayerMatchStats.objects.filter(knockout_match=km).select_related(
            "player",
            "player__club"
        ).order_by('-rating', '-goals', '-assists')
        return render(request, "league/ppl3/match_detail.html", {"match": km, "stats": stats})

    return render(request, "league/404.html", status=404)


# ---------------------------------------------------------
# TEAM PAGE
# ---------------------------------------------------------
def ppl3_team(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    season = Season.objects.filter(is_active=True).first()

    stats = TeamSeasonStats.objects.filter(team=club, season=season).select_related('season').first()

    fixture_qs = (
        Fixture.objects.filter(season=season, home_club=club).select_related('home_club', 'away_club', 'group_match') |
        Fixture.objects.filter(season=season, away_club=club).select_related('home_club', 'away_club', 'group_match')
    )

    # Also include knockout matches where this club appears
    km_list = []
    try:
        km_list = list(KnockoutMatch.objects.filter(round__season=season).filter(
            Q(home_club=club) | Q(away_club=club)
        ).select_related('home_club', 'away_club', 'round'))
    except Exception:
        km_list = []

    fixtures = list(fixture_qs.order_by("date"))
    # Append knockout matches to fixtures list so templates can render them too
    for km in km_list:
        fixtures.append(km)

    players = Player.objects.filter(club=club)

    return render(request, "league/ppl3/team.html", {
        "club": club,
        "season": season,
        "stats": stats,
        "fixtures": fixtures,
        "players": players,
    })


# ---------------------------------------------------------
# PLAYER PAGE
# ---------------------------------------------------------
def ppl3_player(request, player_id):
    from django.db.models import Count
    
    player = get_object_or_404(Player.objects.select_related('club'), id=player_id)
    season = Season.objects.filter(is_active=True).first()

    stats = PlayerSeasonStats.objects.filter(
        player=player, 
        season=season
    ).select_related('season', 'club').first()
    
    match_stats = PlayerMatchStats.objects.filter(
        player=player
    ).filter(
        Q(group_match__fixture__season=season) |
        Q(knockout_match__round__season=season) |
        Q(fixture__season=season)
    ).select_related(
        "group_match__fixture__home_club",
        "group_match__fixture__away_club",
        "knockout_match__round",
        "knockout_match__home_club",
        "knockout_match__away_club",
        "fixture__home_club",
        "fixture__away_club"
    ).order_by('-rating', '-goals')
    
    # Count MOTM awards for this season using database aggregation
    motm_count = match_stats.filter(man_of_the_match=True).count()

    return render(request, "league/ppl3/player.html", {
        "player": player,
        "season": season,
        "stats": stats,
        "match_stats": match_stats,
        "motm_count": motm_count,
    })

