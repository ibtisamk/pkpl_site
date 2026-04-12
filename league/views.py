from django.shortcuts import (
    render,
    get_object_or_404,
    redirect
)
from django.urls import reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib.admin.views.decorators import staff_member_required

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
    TeamOfTheWeek,
    TeamOfTheWeekSelection,
    POSITIONS
)

from django.db.models import Q
from django.utils import timezone
from django.db.utils import ProgrammingError


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
    try:
        all_player_stats = PlayerSeasonStats.objects.filter(
            player__in=players
        ).select_related('season', 'player')
        list(all_player_stats[:1])  # Force eval to check if skill_rating exists
    except ProgrammingError:
        all_player_stats = PlayerSeasonStats.objects.filter(
            player__in=players
        ).select_related('season', 'player').defer('skill_rating')
    
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
    try:
        all_stats = PlayerSeasonStats.objects.filter(
            player=player
        ).select_related('season')
        list(all_stats[:1])
    except ProgrammingError:
        all_stats = PlayerSeasonStats.objects.filter(
            player=player
        ).select_related('season').defer('skill_rating')
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
    knockout_tree = {
        "R16": [],
        "QF": [],
        "SF": [],
        "F": [],
        "3P": [],
    }
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
                "home_club": m.home_club,
                "away_club": m.away_club,
                "home": home,
                "away": away,
                "played": m.is_played,
                "score": f"{m.home_goals}-{m.away_goals}" if m.is_played else None,
                "detail_url": detail_url,
            })

            if len(formatted_matches) >= max_display:
                break

        round_payload = {
            "round": rnd,
            "matches": formatted_matches,
        }
        knockout_data.append(round_payload)

        if rnd.round_type in knockout_tree:
            knockout_tree[rnd.round_type] = formatted_matches

    # -----------------------------
    # TOP 10 PLAYERS SNAPSHOT
    # -----------------------------
    try:
        top_players = (
            PlayerSeasonStats.objects
            .filter(season=season, appearances__gte=3)
            .select_related('player', 'club', 'player__club')
            .order_by('-skill_rating', '-rating', '-goals', '-assists')[:10]
        )
        list(top_players)  # Force evaluation to catch error
    except ProgrammingError:
        top_players = (
            PlayerSeasonStats.objects
            .filter(season=season, appearances__gte=3)
            .select_related('player', 'club', 'player__club')
            .defer('skill_rating')
            .order_by('-rating', '-goals', '-assists')[:10]
        )

    # -----------------------------
    # TOP 5 SCORERS & ASSISTERS
    # -----------------------------
    try:
        top_scorers = (
            PlayerSeasonStats.objects
            .filter(season=season, goals__gt=0)
            .select_related('player', 'club', 'player__club')
            .order_by('-goals', '-assists', '-skill_rating')[:5]
        )
        list(top_scorers)  # Force evaluation
    except ProgrammingError:
        top_scorers = (
            PlayerSeasonStats.objects
            .filter(season=season, goals__gt=0)
            .select_related('player', 'club', 'player__club')
            .defer('skill_rating')
            .order_by('-goals', '-assists', '-rating')[:5]
        )

    try:
        top_assisters = (
            PlayerSeasonStats.objects
            .filter(season=season, assists__gt=0)
            .select_related('player', 'club', 'player__club')
            .order_by('-assists', '-goals', '-skill_rating')[:5]
        )
        list(top_assisters)  # Force evaluation
    except ProgrammingError:
        top_assisters = (
            PlayerSeasonStats.objects
            .filter(season=season, assists__gt=0)
            .select_related('player', 'club', 'player__club')
            .defer('skill_rating')
            .order_by('-assists', '-goals', '-rating')[:5]
        )

    # -----------------------------
    # LATEST PUBLISHED TOTW
    # -----------------------------
    latest_totw = None
    try:
        latest_totw = (
            TeamOfTheWeek.objects
            .filter(season=season, is_published=True)
            .prefetch_related('selections__player__club')
            .order_by('-totw_number')
            .first()
        )
    except Exception:
        pass

    return render(request, "league/ppl3/overview.html", {
        "season": season,
        "groups": group_data,
        "fixtures": fixtures,
        "results": results,
        "knockouts": knockout_data,
        "knockout_tree": knockout_tree,
        "top_players": top_players,
        "top_scorers": top_scorers,
        "top_assisters": top_assisters,
        "latest_totw": latest_totw,
    })


def ppl3_rankings(request):
    """
    PPL3 player rankings with filtering by position and gameweek.
    """
    from django.db.models import Sum, Count, Avg, Q, F, Case, When, IntegerField
    
    season = Season.objects.filter(is_active=True).first()
    if not season:
        return render(request, "league/ppl3/rankings.html", {"season": None})

    # Get filter parameters
    position_filter = request.GET.get('position', 'all')
    week_from = request.GET.get('week_from', '')
    week_to = request.GET.get('week_to', '')
    qualified_only = request.GET.get('qualified', 'false') == 'true'

    # Determine if we're using weekly filtering
    use_weekly_filter = bool(week_from or week_to)
    
    # Convert to integers if provided
    try:
        week_from_int = int(week_from) if week_from else None
        week_to_int = int(week_to) if week_to else None
    except ValueError:
        week_from_int = None
        week_to_int = None

    # Position map for filtering
    position_map = {
        'attackers': ['ST', 'LW', 'RW'],
        'midfielders': ['CM', 'CDM', 'CAM', 'LM', 'RM'],
        'defenders': ['LB', 'CB', 'RB'],
        'goalkeepers': ['GK'],
    }

    if use_weekly_filter and (week_from_int or week_to_int):
        # WEEKLY AGGREGATION FROM PLAYERMATCHSTATS
        match_stats_filter = Q(
            group_match__fixture__season=season,
            group_match__is_played=True
        )
        
        if week_from_int:
            match_stats_filter &= Q(group_match__fixture__week_number__gte=week_from_int)
        if week_to_int:
            match_stats_filter &= Q(group_match__fixture__week_number__lte=week_to_int)
        
        # Apply position filter if needed
        if position_filter in position_map:
            match_stats_filter &= Q(player__position__in=position_map[position_filter])
        
        # Aggregate stats from PlayerMatchStats
        weekly_stats = (
            PlayerMatchStats.objects
            .filter(match_stats_filter)
            .values('player', 'player__gamertag', 'player__position', 'player__club__id', 'player__club__name', 'player__club__short_name')
            .annotate(
                appearances=Count('id'),
                goals=Sum('goals'),
                assists=Sum('assists'),
                avg_rating=Avg('rating'),
                # Count clean sheets for defenders/GKs
                clean_sheets=Count(
                    Case(
                        When(
                            Q(position_played__in=['GK', 'LB', 'CB', 'RB']) &
                            Q(group_match__fixture__home_club=F('player__club'), group_match__away_goals=0) |
                            Q(group_match__fixture__away_club=F('player__club'), group_match__home_goals=0),
                            then=1
                        ),
                        output_field=IntegerField()
                    )
                )
            )
            .filter(appearances__gte=1)
        )
        
        # Calculate weekly skill rating for each player
        players_list = []
        for stat in weekly_stats:
            # Get stats
            apps = stat['appearances'] or 1
            goals = stat['goals'] or 0
            assists = stat['assists'] or 0
            avg_rating = stat['avg_rating'] or 0
            clean_sheets = stat['clean_sheets'] or 0
            position = stat['player__position']
            
            # Calculate contribution score per match (same as season SR logic)
            attackers = ['ST', 'LW', 'RW']
            midfielders = ['CAM', 'CM', 'CDM', 'LM', 'RM']
            defenders = ['LB', 'CB', 'RB']
            goalkeepers = ['GK']
            
            total_contribution = 0.0
            if position in attackers:
                total_contribution = (goals * 5) + (assists * 3)
                max_per_match = 15
            elif position in midfielders:
                total_contribution = (goals * 5) + (assists * 3)
                max_per_match = 12
            elif position in defenders:
                total_contribution = (goals * 6) + (assists * 5) + (clean_sheets * 3)
                max_per_match = 10
            elif position in goalkeepers:
                total_contribution = clean_sheets * 3
                max_per_match = 8
            else:
                total_contribution = (goals * 5) + (assists * 3) + (clean_sheets * 2)
                max_per_match = 12
            
            # Apply per-match cap
            max_total_allowed = max_per_match * apps
            total_contribution = min(total_contribution, max_total_allowed)
            contribution_per_match = total_contribution / apps
            
            # Weekly Skill Rating formula (same as season SR)
            # 80% match rating + 20% contribution
            base_weekly_sr = (0.8 * avg_rating) + (0.2 * contribution_per_match)
            
            # Apply confidence multiplier based on games played (same as season SR)
            # 0.3 + (0.7 * min(1.0, appearances / 10))
            # At 5 games: 65% confidence, At 10+ games: 100% confidence
            confidence = 0.3 + (0.7 * min(1.0, apps / 10.0))
            weekly_sr = base_weekly_sr * confidence
            
            # Get season skill rating from PlayerSeasonStats for reference
            try:
                season_stats = PlayerSeasonStats.objects.get(
                    player_id=stat['player'],
                    season=season
                )
                season_sr = season_stats.skill_rating
            except PlayerSeasonStats.DoesNotExist:
                season_sr = 0
            
            players_list.append({
                'player_id': stat['player'],
                'player_gamertag': stat['player__gamertag'],
                'player_position': stat['player__position'],
                'club_id': stat['player__club__id'],
                'club_name': stat['player__club__name'],
                'club_short_name': stat['player__club__short_name'],
                'appearances': apps,
                'goals': goals,
                'assists': assists,
                'clean_sheets': clean_sheets,
                'avg_rating': round(avg_rating, 2) if avg_rating else 0,
                'weekly_skill_rating': round(weekly_sr, 2),
                'season_skill_rating': round(season_sr, 2) if season_sr else 0,
            })
        
        # Sort by weekly skill rating
        players_list.sort(key=lambda x: (-x['weekly_skill_rating'], -x['goals'], -x['assists']))
        
        # Top scorers and assisters for selected weeks
        top_scorers = sorted(
            [p for p in players_list if p['goals'] > 0],
            key=lambda x: (-x['goals'], -x['assists'], -x['weekly_skill_rating'])
        )
        
        top_assisters = sorted(
            [p for p in players_list if p['assists'] > 0],
            key=lambda x: (-x['assists'], -x['goals'], -x['weekly_skill_rating'])
        )
        
        players = players_list
        using_weekly_data = True
        
    else:
        # SEASON TOTALS (DEFAULT)
        players_qs = (
            PlayerSeasonStats.objects
            .filter(season=season, appearances__gte=1)
            .select_related('player', 'club', 'player__club')
        )
        
        # Apply qualified filter
        min_qualified_games = 5
        if qualified_only:
            players_qs = players_qs.filter(appearances__gte=min_qualified_games)

        # Apply position filter
        if position_filter in position_map:
            players_qs = players_qs.filter(player__position__in=position_map[position_filter])

        # Order by skill rating
        try:
            players = players_qs.order_by('-skill_rating', '-rating', '-goals', '-assists')
            list(players[:1])
        except ProgrammingError:
            players = players_qs.defer('skill_rating').order_by('-rating', '-goals', '-assists')

        # Top scorers and assisters (full lists)
        try:
            top_scorers = (
                PlayerSeasonStats.objects
                .filter(season=season, goals__gt=0)
                .select_related('player', 'club')
                .order_by('-goals', '-assists', '-skill_rating')
            )
            list(top_scorers[:1])
        except ProgrammingError:
            top_scorers = (
                PlayerSeasonStats.objects
                .filter(season=season, goals__gt=0)
                .select_related('player', 'club')
                .defer('skill_rating')
                .order_by('-goals', '-assists', '-rating')
            )

        try:
            top_assisters = (
                PlayerSeasonStats.objects
                .filter(season=season, assists__gt=0)
                .select_related('player', 'club')
                .order_by('-assists', '-goals', '-skill_rating')
            )
            list(top_assisters[:1])
        except ProgrammingError:
            top_assisters = (
                PlayerSeasonStats.objects
                .filter(season=season, assists__gt=0)
                .select_related('player', 'club')
                .defer('skill_rating')
                .order_by('-assists', '-goals', '-rating')
            )
        
        using_weekly_data = False

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

    return render(request, "league/ppl3/rankings.html", {
        "season": season,
        "players": players,
        "positions": positions,
        "current_position": position_filter,
        "gameweeks": gameweeks,
        "week_from": week_from,
        "week_to": week_to,
        "qualified_only": qualified_only,
        "min_qualified_games": 5,
        "top_scorers": top_scorers,
        "top_assisters": top_assisters,
        "using_weekly_data": using_weekly_data,
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

        # Build LIVE standings from currently existing played group matches.
        # This avoids stale cached totals if fixtures/matches were deleted.
        standings_map = {
            club.id: {
                'team': club,
                'played': 0,
                'wins': 0,
                'draws': 0,
                'losses': 0,
                'goals_for': 0,
                'goals_against': 0,
                'goal_difference': 0,
                'points': 0,
            }
            for club in clubs
        }

        matches = (
            GroupMatch.objects
            .filter(
                fixture__season=season,
                is_played=True,
                fixture__home_club__in=clubs,
                fixture__away_club__in=clubs,
            )
            .select_related('fixture__home_club', 'fixture__away_club')
        )

        for m in matches:
            home = m.fixture.home_club
            away = m.fixture.away_club

            # Guard against any bad/legacy membership data
            if home.id not in standings_map or away.id not in standings_map:
                continue

            home_row = standings_map[home.id]
            away_row = standings_map[away.id]

            home_row['played'] += 1
            away_row['played'] += 1

            home_row['goals_for'] += m.home_goals
            home_row['goals_against'] += m.away_goals
            away_row['goals_for'] += m.away_goals
            away_row['goals_against'] += m.home_goals

            if m.home_goals > m.away_goals:
                home_row['wins'] += 1
                away_row['losses'] += 1
                home_row['points'] += 3
            elif m.home_goals < m.away_goals:
                away_row['wins'] += 1
                home_row['losses'] += 1
                away_row['points'] += 3
            else:
                home_row['draws'] += 1
                away_row['draws'] += 1
                home_row['points'] += 1
                away_row['points'] += 1

        standings = list(standings_map.values())
        for row in standings:
            row['goal_difference'] = row['goals_for'] - row['goals_against']

        standings.sort(
            key=lambda r: (r['points'], r['goal_difference'], r['goals_for']),
            reverse=True,
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

    # Build LIVE season stats from the currently existing played matches.
    # This keeps the profile page in sync after deleted duplicate fixtures.
    stats = {
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
        "points": 0,
    }

    played_matches = list(
        GroupMatch.objects
        .filter(
            fixture__season=season,
            is_played=True,
        )
        .filter(Q(fixture__home_club=club) | Q(fixture__away_club=club))
        .values(
            'id',
            'fixture_id',
            'home_goals',
            'away_goals',
            'fixture__home_club_id',
            'fixture__away_club_id',
        )
    )

    played_match_by_fixture_id = {}
    for match in played_matches:
        played_match_by_fixture_id[match['fixture_id']] = match

    for match in played_matches:
        stats["played"] += 1

        if match['fixture__home_club_id'] == club.id:
            goals_for = match['home_goals']
            goals_against = match['away_goals']
        else:
            goals_for = match['away_goals']
            goals_against = match['home_goals']

        stats["goals_for"] += goals_for
        stats["goals_against"] += goals_against

        if goals_for > goals_against:
            stats["wins"] += 1
            stats["points"] += 3
        elif goals_for < goals_against:
            stats["losses"] += 1
        else:
            stats["draws"] += 1
            stats["points"] += 1

    stats["goal_difference"] = stats["goals_for"] - stats["goals_against"]

    fixture_qs = (
        Fixture.objects.filter(season=season, home_club=club).select_related('home_club', 'away_club') |
        Fixture.objects.filter(season=season, away_club=club).select_related('home_club', 'away_club')
    )

    fixture_rows = []
    for fixture in fixture_qs.order_by("date"):
        group_match = played_match_by_fixture_id.get(fixture.id)
        fixture_rows.append({
            "kind": "fixture",
            "home_name": fixture.home_club.name if fixture.home_club else "-",
            "away_name": fixture.away_club.name if fixture.away_club else "-",
            "date": fixture.date,
            "played": bool(group_match),
            "score": f"{group_match['home_goals']} - {group_match['away_goals']}" if group_match else None,
            "detail_url": reverse('ppl3_match_detail', args=[group_match['id']]) if group_match else None,
        })

    players = Player.objects.filter(club=club)

    return render(request, "league/ppl3/team.html", {
        "club": club,
        "season": season,
        "stats": stats,
        "fixtures": fixture_rows,
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


# ---------------------------------------------------------
# TEAM OF THE WEEK VIEWS
# ---------------------------------------------------------
def totw_list(request):
    """List all Team of the Week selections"""
    season = Season.objects.filter(is_active=True).first()
    
    totws = TeamOfTheWeek.objects.filter(
        is_published=True
    ).select_related('season').prefetch_related(
        'selections__player',
        'selections__player__club'
    ).order_by('-season__year', 'week_type', '-week_number')
    
    if season:
        totws = totws.filter(season=season)
    
    return render(request, "league/ppl3/totw_list.html", {
        "season": season,
        "totws": totws,
    })


def totw_detail(request, totw_id):
    """Display a specific Team of the Week"""
    totw = get_object_or_404(
        TeamOfTheWeek.objects.prefetch_related(
            'selections__player__club'
        ),
        id=totw_id,
        is_published=True
    )
    
    # Group selections by position for display
    selections_by_position = {
        'GK': [],
        'DEF': [],
        'MID': [],
        'ATT': [],
    }
    
    for selection in totw.selections.all():
        selections_by_position[selection.position].append(selection)
    
    return render(request, "league/ppl3/totw_detail.html", {
        "totw": totw,
        "selections_by_position": selections_by_position,
    })


# ---------------------------------------------------------
# ADMIN API: Player Stats for TOTW Selection
# ---------------------------------------------------------
@staff_member_required
def player_stats_api(request, player_id):
    """API endpoint for fetching player stats for TOTW admin"""
    try:
        player = Player.objects.get(id=player_id)
        active_season = Season.objects.filter(is_active=True).first()
        
        if not active_season:
            return JsonResponse({'error': 'No active season'}, status=404)
        
        try:
            season_stats = PlayerSeasonStats.objects.get(
                player=player,
                season=active_season
            )
            
            return JsonResponse({
                'name': player.gamertag,
                'club': player.club.name if player.club else 'N/A',
                'appearances': season_stats.appearances,
                'goals': season_stats.goals,
                'assists': season_stats.assists,
                'clean_sheets': season_stats.clean_sheets,
                'rating': float(season_stats.rating) if season_stats.rating else 0,
                'skill_rating': float(season_stats.skill_rating) if season_stats.skill_rating else 0,
            })
        except PlayerSeasonStats.DoesNotExist:
            return JsonResponse({
                'name': player.gamertag,
                'club': player.club.name if player.club else 'N/A',
                'appearances': 0,
                'goals': 0,
                'assists': 0,
                'clean_sheets': 0,
                'rating': 0,
                'skill_rating': 0,
            })
    except Player.DoesNotExist:
        return JsonResponse({'error': 'Player not found'}, status=404)

