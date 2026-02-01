from django.shortcuts import render, redirect
from .forms import TeamRegistrationForm, PlayerRegistrationForm
from .models import (
    Club, Player, TeamRegistration, TeamRegistrationPlayer,
    PlayerSeasonStats, TeamSeasonStats, Season,
    PlayerMatchStats, Fixture, Match, KnockoutRound,
    POSITIONS
)

# ---------------------------------------------------------
# Registration landing page
# ---------------------------------------------------------
def register(request):
    return render(request, "league/register.html")


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
                match__fixture__season=season
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
            match__fixture__season=season
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
            if award.mvp_id == player.id: titles.append("MVP")
            if award.top_scorer_id == player.id: titles.append("Top Scorer")
            if award.top_assister_id == player.id: titles.append("Top Assister")
            if award.best_defender_id == player.id: titles.append("Best Defender")
            if award.best_midfielder_id == player.id: titles.append("Best Midfielder")

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
        awards = []

        for season in seasons:
            stat = PlayerSeasonStats.objects.filter(player=player, season=season).first()
            if stat:
                total_apps += stat.appearances
                total_goals += stat.goals
                total_assists += stat.assists

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

        player_data.append({
            "player": player,
            "club": player.club.name,
            "apps": total_apps,
            "goals": total_goals,
            "assists": total_assists,
            "clean_sheets": stat.clean_sheets if stat else 0,
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
    # UPCOMING FIXTURES (GROUP)
    # -----------------------------
    fixtures = (
        Fixture.objects
        .filter(season=season, group__isnull=False)
        .order_by("date")[:10]
    )

    # -----------------------------
    # KNOCKOUT ROUNDS + MATCHES
    # -----------------------------
    rounds = KnockoutRound.objects.filter(season=season).order_by("id")

    knockout_data = []
    for rnd in rounds:
        formatted_matches = []
        for m in rnd.matches.all():
            home = m.home_club.name if m.home_club else m.home_placeholder
            away = m.away_club.name if m.away_club else m.away_placeholder

            formatted_matches.append({
                "match": m,
                "home": home,
                "away": away,
                "played": m.is_played,
                "score": f"{m.home_goals}-{m.away_goals}" if m.is_played else None,
            })

        knockout_data.append({
            "round": rnd,
            "matches": formatted_matches,
        })

    return render(request, "league/ppl3/overview.html", {
        "season": season,
        "groups": group_data,
        "fixtures": fixtures,
        "knockouts": knockout_data,
    })


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

    # Knockout fixtures come from KnockoutMatch, not Fixture
    knockout_rounds = KnockoutRound.objects.filter(season=season).order_by("id")

    knockout_matches = []
    for rnd in knockout_rounds:
        for m in rnd.matches.all():
            home = m.home_club.name if m.home_club else m.home_placeholder
            away = m.away_club.name if m.away_club else m.away_placeholder

            knockout_matches.append({
                "round": rnd.round_type,
                "match": m,
                "home": home,
                "away": away,
                "played": m.is_played,
                "score": f"{m.home_goals}-{m.away_goals}" if m.is_played else None,
            })

    return render(request, "league/ppl3/fixtures.html", {
        "season": season,
        "group_fixtures": group_fixtures,
        "knockout_matches": knockout_matches,
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
        for m in rnd.matches.all():
            home = m.home_club.name if m.home_club else m.home_placeholder
            away = m.away_club.name if m.away_club else m.away_placeholder

            formatted_matches.append({
                "match": m,
                "home": home,
                "away": away,
                "played": m.is_played,
                "score": f"{m.home_goals}-{m.away_goals}" if m.is_played else None,
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
    match = get_object_or_404(Match, id=match_id)
    stats = PlayerMatchStats.objects.filter(match=match).select_related("player")

    return render(request, "league/ppl3/match_detail.html", {
        "match": match,
        "stats": stats,
    })


# ---------------------------------------------------------
# TEAM PAGE
# ---------------------------------------------------------
def ppl3_team(request, club_id):
    club = get_object_or_404(Club, id=club_id)
    season = Season.objects.filter(is_active=True).first()

    stats = TeamSeasonStats.objects.filter(team=club, season=season).first()

    fixtures = (
        Fixture.objects.filter(season=season, home_club=club) |
        Fixture.objects.filter(season=season, away_club=club)
    ).order_by("date")

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
        player=player,
        match__fixture__season=season
    ).select_related("match")

    return render(request, "league/ppl3/player.html", {
        "player": player,
        "season": season,
        "stats": stats,
        "match_stats": match_stats,
    })

