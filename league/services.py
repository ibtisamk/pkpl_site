import math
import random
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from .models import (
    Season,
    Club,
    Group,
    GroupMembership,
    Fixture,
    GroupMatch,          
    KnockoutRound,
    KnockoutMatch,
    TeamSeasonStats,
)



# -----------------------------
# GROUP GENERATION
# -----------------------------

@transaction.atomic
def generate_groups_for_season(
    season: Season,
    num_groups: int,
    random_draw: bool = True,
    use_seeds: bool = True,
):
    clubs = list(season.clubs.all())
    if not clubs:
        raise ValueError("No clubs assigned to this season.")

    if use_seeds:
        clubs.sort(key=lambda c: c.seed_rank if c.seed_rank is not None else 9999)

    if random_draw:
        random.shuffle(clubs)

    groups = []
    for i in range(num_groups):
        group, _ = Group.objects.get_or_create(
            season=season,
            name=f"Group {chr(ord('A') + i)}",
        )
        groups.append(group)

    GroupMembership.objects.filter(group__season=season).delete()

    for idx, club in enumerate(clubs):
        group = groups[idx % num_groups]
        GroupMembership.objects.create(group=group, club=club)

    return groups


# -----------------------------
# GROUP FIXTURE GENERATION
# -----------------------------

@transaction.atomic
def generate_group_fixtures(
    season: Season,
    double_round_robin: bool = False,
    auto_week_numbers: bool = True,
    start_date=None,
    days_between_rounds: int = 7,
):
    if start_date is None:
        start_date = timezone.now()

    fixtures_created = []

    for group in season.groups.all():
        clubs = [gm.club for gm in group.members.select_related("club")]

        pairings = []
        for i in range(len(clubs)):
            for j in range(i + 1, len(clubs)):
                pairings.append((clubs[i], clubs[j]))

        week = 1
        current_date = start_date

        for home, away in pairings:
            fixture = Fixture.objects.create(
                season=season,
                home_club=home,
                away_club=away,
                date=current_date,
                week_number=week if auto_week_numbers else None,
                group=group,
            )
            fixtures_created.append(fixture)

            if double_round_robin:
                fixture2 = Fixture.objects.create(
                    season=season,
                    home_club=away,
                    away_club=home,
                    date=current_date + timedelta(days=days_between_rounds // 2),
                    week_number=(week + 1) if auto_week_numbers else None,
                    group=group,
                )
                fixtures_created.append(fixture2)

            week += 1
            current_date += timedelta(days=days_between_rounds)

    return fixtures_created


# -----------------------------
# KNOCKOUT GENERATION (NEW)
# -----------------------------

def _decide_knockout_round_name(num_teams: int) -> str:
    if num_teams == 16:
        return "R16"
    if num_teams == 8:
        return "QF"
    if num_teams == 4:
        return "SF"
    if num_teams == 2:
        return "F"
    raise ValueError(f"Unsupported number of teams for knockout: {num_teams}")


def _generate_placeholder_pairs(groups, qualifiers_per_group):
    """
    Returns placeholder pairs like:
    A1 vs B2, B1 vs A2, C1 vs D2, ...
    """
    placeholders = []

    group_names = [g.name.split()[-1] for g in groups]  # ["A", "B", "C", "D"]

    # Example for 2 qualifiers:
    # A1 vs B2
    # B1 vs A2
    for i in range(0, len(group_names), 2):
        g1 = group_names[i]
        g2 = group_names[i + 1]

        for q in range(1, qualifiers_per_group + 1):
            placeholders.append((f"{g1}{q}", f"{g2}{qualifiers_per_group - q + 1}"))
            placeholders.append((f"{g2}{q}", f"{g1}{qualifiers_per_group - q + 1}"))

    return placeholders


def _resolve_placeholder(season, placeholder):
    """
    Convert placeholder like 'A1' into a real club.
    If standings aren't ready, return None.
    """
    group_letter = placeholder[0]
    rank = int(placeholder[1:])

    group = Group.objects.filter(season=season, name=f"Group {group_letter}").first()
    if not group:
        return None

    group_clubs = [gm.club for gm in group.members.select_related("club")]

    stats = (
        TeamSeasonStats.objects
        .filter(season=season, team__in=group_clubs)
        .order_by("-points", "-goal_difference", "-goals_for")
    )

    if len(stats) < rank:
        return None

    return stats[rank - 1].team


@transaction.atomic
def generate_knockouts_for_season(
    season: Season,
    qualifiers_per_group: int = None,
    total_qualified: int = None,
    random_bracket: bool = False,
    seeded_bracket: bool = True,
    two_leg_rounds: bool = False,
    create_fixtures: bool = False,
):
    groups = list(season.groups.all())
    if not groups:
        raise ValueError("No groups found for this season.")

    # Derive qualifiers_per_group from total_qualified if provided
    if total_qualified is not None:
        if total_qualified % len(groups) != 0:
            raise ValueError("total_qualified must be divisible by number of groups")
        qualifiers_per_group = total_qualified // len(groups)

    if qualifiers_per_group is None:
        raise ValueError("Either qualifiers_per_group or total_qualified must be provided")

    num_teams = len(groups) * qualifiers_per_group
    round_type = _decide_knockout_round_name(num_teams)

    # Create or get knockout round
    round_obj, created = KnockoutRound.objects.get_or_create(
        season=season,
        round_type=round_type,
    )

    # Try to get real qualified teams
    qualified = []
    for group in groups:
        group_clubs = [gm.club for gm in group.members.select_related("club")]

        stats = (
            TeamSeasonStats.objects
            .filter(season=season, team__in=group_clubs)
            .order_by("-points", "-goal_difference", "-goals_for")
        )

        if len(stats) >= qualifiers_per_group:
            qualified.extend(stats[:qualifiers_per_group])

    # CASE 1 — No real standings yet → generate placeholders
    if len(qualified) < num_teams:
        # Only create placeholders if none exist yet for this round
        existing_placeholders = round_obj.matches.filter(home_placeholder__isnull=False).exists()
        if existing_placeholders:
            return round_obj, "PLACEHOLDERS_ALREADY_EXIST"

        placeholders = _generate_placeholder_pairs(groups, qualifiers_per_group)

        for home_ph, away_ph in placeholders:
            KnockoutMatch.objects.create(
                round=round_obj,
                home_placeholder=home_ph,
                away_placeholder=away_ph,
            )

        return round_obj, "PLACEHOLDERS_CREATED"

    # CASE 2 — Real teams exist → generate real bracket
    clubs = [ts.team for ts in qualified]

    if seeded_bracket:
        qualified.sort(key=lambda ts: (-ts.points, -ts.goal_difference, -ts.goals_for))
        clubs = [ts.team for ts in qualified]

    if random_bracket:
        random.shuffle(clubs)

    # Remove placeholder matches for this round to avoid duplicates when real teams exist
    round_obj.matches.filter(Q(home_placeholder__isnull=False) | Q(away_placeholder__isnull=False)).delete()

    # If matches already exist for this round, avoid duplicating
    existing_matches = list(round_obj.matches.filter(home_club__isnull=False, away_club__isnull=False))
    if existing_matches:
        matches = existing_matches
    else:
        matches = []
        for i in range(0, num_teams, 2):
            km = KnockoutMatch.objects.create(
                round=round_obj,
                home_club=clubs[i],
                away_club=clubs[i + 1],
            )
            matches.append(km)

    # Optionally create Fixtures for each UNIQUE knockout tie (no auto-created Matches)
    if create_fixtures:
        created_fixtures = []
        base_date = timezone.now()
        day_offset = 0

        # Normalize pairs to avoid duplicates when KMs contain both A vs B and B vs A or duplicates
        unique_pairs = {}
        for km in matches:
            if not km.home_club or not km.away_club:
                continue
            # key is unordered pair of club ids
            key = tuple(sorted((km.home_club_id, km.away_club_id)))
            # prefer existing mapping but keep the first km encountered
            unique_pairs.setdefault(key, km)

        # Expected number of ties
        expected_ties = num_teams // 2

        # Only consider up to expected_ties unique pairs (protect against existing data corruption)
        pairs = list(unique_pairs.values())[:expected_ties]

        for km in pairs:
            # Check if either direction fixture exists; if not, create first leg and optionally return leg
            exists_either = Fixture.objects.filter(
                season=season,
                group__isnull=True,
            ).filter(
                Q(home_club=km.home_club, away_club=km.away_club) | Q(home_club=km.away_club, away_club=km.home_club)
            ).exists()

            if not exists_either:
                # Create first leg with km's home/away orientation
                f = Fixture(
                    season=season,
                    home_club=km.home_club,
                    away_club=km.away_club,
                    date=base_date + timedelta(days=day_offset),
                    week_number=None,
                    group=None,
                )
                f.save(create_match=False)
                created_fixtures.append(f)

                if two_leg_rounds:
                    # Create reverse leg
                    f2 = Fixture(
                        season=season,
                        home_club=km.away_club,
                        away_club=km.home_club,
                        date=base_date + timedelta(days=day_offset + 7),
                        week_number=None,
                        group=None,
                    )
                    f2.save(create_match=False)
                    created_fixtures.append(f2)

            day_offset += 1

        return round_obj, matches, created_fixtures

    return round_obj, matches


# -----------------------------
# PLACEHOLDER RESOLUTION (AUTO)
# -----------------------------

def resolve_knockout_placeholders(season: Season):
    """
    Replace placeholders with real teams once standings exist.
    """
    rounds = KnockoutRound.objects.filter(season=season)

    for rnd in rounds:
        for match in rnd.matches.all():
            if match.home_placeholder and not match.home_club:
                match.home_club = _resolve_placeholder(season, match.home_placeholder)

            if match.away_placeholder and not match.away_club:
                match.away_club = _resolve_placeholder(season, match.away_placeholder)

            match._skip_signal = True
            match.save()


