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

    players = Player.objects.filter(club=club).order_by("position")
    squad_rows = []

    for player in players:
        per_season = []
        for season in seasons:
            stat = PlayerSeasonStats.objects.filter(player=player, season=season).first()

            match_stats = PlayerMatchStats.objects.filter(
                player=player,
                group_match__fixture__season=season
            )
            avg_rating = None
            if match_stats.exists():
                avg_rating = round(
                    sum(ms.rating for ms in match_stats) / match_stats.count(), 2
                )

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

    finishes = TeamSeasonStats.objects.filter(team=club)
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

    season_rows = []

    for season in seasons:
        stat = PlayerSeasonStats.objects.filter(player=player, season=season).first()

        match_stats = PlayerMatchStats.objects.filter(
            player=player,
            group_match__fixture__season=season
        )
        avg_rating = None
        if match_stats.exists():
            avg_rating = round(
                sum(ms.rating for ms in match_stats) / match_stats.count(), 2
            )

        season_rows.append({
            "season": season,
            "stats": stat,
            "avg_rating": avg_rating,
        })

    awards = []
    for season in seasons:
        if hasattr(season, "awards"):
            award = season.awards
            titles = []
            if award.mvp_id and award.mvp_id == player.id: titles.append("MVP")
            if award.top_scorer_id and award.top_scorer_id == player.id: titles.append("Top Scorer")
            if award.top_assister_id and award.top_assister_id == player.id: titles.append("Top Assister")
            if award.best_defender_id and award.best_defender_id == player.id: titles.append("Best Defender")
            if award.best_midfielder_id and award.best_midfielder_id == player.id: titles.append("Best Midfielder")

            if titles:
                awards.append({"season": season.name, "titles": titles})

    return render(request, "league/player_detail.html", {
        "player": player,
        "season_rows": season_rows,
        "awards": awards,
    })


# ---------------------------------------------------------
# ALL PLAYERS PAGE
# ---------------------------------------------------------
def all_players(request):
    players = Player.objects.select_related("club").all().order_by("gamertag")
    seasons = Season.objects.all().order_by("id")

    player_data = []
    for player in players:
        total_apps = 0
        total_goals = 0
        total_assists = 0
        total_clean_sheets = 0
        awards = []

        for season in seasons:
            stat = PlayerSeasonStats.objects.filter(player=player, season=season).first()
            if stat:
                total_apps += stat.appearances
                total_goals += stat.goals
                total_assists += stat.assists
                total_clean_sheets += stat.clean_sheets

            try:
                if hasattr(season, "awards"):
                    award = season.awards
                    if award.mvp_id == player.id:
                        awards.append(f"MVP ({season.name})")
                    if award.top_scorer_id == player.id:
                        awards.append(f"Top Scorer ({season.name})")
                    if award.top_assister_id == player.id:
                        awards.append(f"Top Assister ({season.name})")
                    if award.best_defender_id == player.id:
                        awards.append(f"Best Defender ({season.name})")
                    if award.best_midfielder_id == player.id:
                        awards.append(f"Best Midfielder ({season.name})")
            except Exception:
                pass

        player_data.append({
            "player": player,
            "club": player.club.name if player.club else "Free Agent",
            "apps": total_apps,
            "goals": total_goals,
            "assists": total_assists,
            "clean_sheets": total_clean_sheets,
            "avg_rating": None,
            "awards": awards,
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
    groups = season.groups.all().prefetch_related("members__club")

    group_data = []
    for group in groups:
        clubs = [gm.club for gm in group.members.all()]
        standings = (
            TeamSeasonStats.objects
            .filter(season=season, team__in=clubs)
            .order_by("-points", "-goal_difference", "-goals_for")
        )
        group_data.append({
            "group": group,
            "standings": standings,
        })

    # -----------------------------
    # UPCOMING FIXTURES (SNAPSHOT)
    # -----------------------------
    # Show a snapshot of the next upcoming (unplayed) fixtures for the season.
    # Include fixtures that don't have an associated GroupMatch (e.g. knockout fixtures)
    fixtures = (
        Fixture.objects
        .filter(season=season)
        .filter(Q(group_match__is_played=False) | Q(group_match__isnull=True))
        .order_by("date")[:10]  # Show next 10 fixtures
    )

    # All results: include played group fixtures and played knockout matches
    results = []
    played_fixtures = (
        Fixture.objects
        .filter(season=season, group_match__is_played=True)
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
        kms = list(KnockoutRound.objects.filter(season=season))
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
    rounds_qs = list(KnockoutRound.objects.filter(season=season))
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

    return render(request, "league/ppl3/overview.html", {
        "season": season,
        "groups": group_data,
        "fixtures": fixtures,
        "results": results,
        "knockouts": knockout_data,
    })


def upcoming_fixtures(request):
    fixtures = Fixture.objects.filter(
        Q(group_match__is_played=False) | Q(group_match__isnull=True)
    ).order_by("-date", "id")
    return render(request, "fixtures/upcoming.html", {"fixtures": fixtures})


def results(request):
    fixtures = Fixture.objects.filter(group_match__is_played=True).order_by("-date")
    return render(request, "fixtures/results.html", {"fixtures": fixtures})


# ---------------------------------------------------------
# GROUPS PAGE
# ---------------------------------------------------------
def ppl3_groups(request):
    season = Season.objects.filter(is_active=True).first()
    if not season:
        return render(request, "league/ppl3/groups.html", {"season": None})

    groups = season.groups.all().prefetch_related("members__club")

    group_data = []
    for group in groups:
        clubs = [gm.club for gm in group.members.all()]
        standings = (
            TeamSeasonStats.objects
            .filter(season=season, team__in=clubs)
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
        .order_by("week_number", "date")
    )

    # For knockout fixtures, show fixtures created for knockout ties (fixtures with no group)
    knockout_fixtures = (
        Fixture.objects
        .filter(season=season, group__isnull=True)
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

    rounds = KnockoutRound.objects.filter(season=season).order_by("id")

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
            ).order_by('date')

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
    match = GroupMatch.objects.filter(id=match_id).first()
    if match:
        stats = PlayerMatchStats.objects.filter(group_match=match).select_related("player")
        return render(request, "league/ppl3/match_detail.html", {"match": match, "stats": stats})

    # Fallback to KnockoutMatch
    from .models import KnockoutMatch
    km = KnockoutMatch.objects.filter(id=match_id).first()
    if km:
        stats = PlayerMatchStats.objects.filter(knockout_match=km).select_related("player")
        return render(request, "league/ppl3/match_detail.html", {"match": km, "stats": stats})

    return render(request, "league/404.html", status=404)


# ---------------------------------------------------------
# TEAM PAGE
# ---------------------------------------------------------
def ppl3_team(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    season = Season.objects.filter(is_active=True).first()

    stats = TeamSeasonStats.objects.filter(team=club, season=season).first()

    fixture_qs = (
        Fixture.objects.filter(season=season, home_club=club) |
        Fixture.objects.filter(season=season, away_club=club)
    )

    # Also include knockout matches where this club appears
    km_list = []
    try:
        km_list = list(KnockoutMatch.objects.filter(round__season=season).filter(Q(home_club=club) | Q(away_club=club)))
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
    player = get_object_or_404(Player, id=player_id)
    season = Season.objects.filter(is_active=True).first()

    stats = PlayerSeasonStats.objects.filter(player=player, season=season).first()
    match_stats = PlayerMatchStats.objects.filter(
        player=player
    ).filter(
        Q(group_match__fixture__season=season) |
        Q(knockout_match__round__season=season) |
        Q(fixture__season=season)
    ).select_related("group_match__fixture", "knockout_match__round", "fixture")

    return render(request, "league/ppl3/player.html", {
        "player": player,
        "season": season,
        "stats": stats,
        "match_stats": match_stats,
    })

