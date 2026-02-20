from django.db import models
from django.utils import timezone
from django.contrib import admin


def generate_group_fixtures(group, repeats: int):
    memberships = group.members.select_related("club")
    clubs = [m.club for m in memberships]

    if len(clubs) < 2:
        return 0

    created_count = 0

    for i in range(len(clubs)):
        for j in range(i + 1, len(clubs)):
            home = clubs[i]
            away = clubs[j]

            existing = Fixture.objects.filter(
                group=group,
                season=group.season,
            ).filter(
                home_club__in=[home, away],
                away_club__in=[home, away],
            ).count()

            to_create = max(0, repeats - existing)

            for _ in range(to_create):
                Fixture.objects.create(
                    season=group.season,
                    group=group,
                    home_club=home,
                    away_club=away,
                    date=timezone.now(),
                    week_number=None,
                )
                created_count += 1

    return created_count


POSITIONS = [
    ("ST", "ST"),
    ("LW", "LW / LM"),
    ("RW", "RW / RM"),
    ("CM", "CM"),
    ("CDM", "CDM"),
    ("CAM", "CAM"),
    ("LB", "LB"),
    ("CB", "CB"),
    ("RB", "RB"),
    ("GK", "GK"),
    ("ANY", "ANY"),
]

PLATFORMS = [
    ("PS5", "PlayStation 5"),
    ("PC", "PC"),
    ("XBOX", "Xbox"),
]

REGIONS = [
    ("PK", "Pakistan"),
    ("ME", "Middle East"),
    ("EU", "Europe"),
    ("OT", "Other"),
]


# ---------------------------------------------------------
# TEAM REGISTRATION
# ---------------------------------------------------------
class TeamRegistration(models.Model):
    team_name = models.CharField(max_length=100)
    founded = models.CharField(max_length=50, blank=True, null=True)
    stadium = models.CharField(max_length=100, blank=True, null=True)

    platform = models.CharField(max_length=10, choices=PLATFORMS, blank=True, null=True)
    region = models.CharField(max_length=10, choices=REGIONS, blank=True, null=True)

    captain_name = models.CharField(max_length=100)
    captain_whatsapp = models.CharField(max_length=20)
    captain_position = models.CharField(max_length=10, choices=POSITIONS)

    timestamp = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.team_name} (Captain: {self.captain_name})"


class TeamRegistrationPlayer(models.Model):
    team = models.ForeignKey(TeamRegistration, on_delete=models.CASCADE, related_name="players")
    name = models.CharField(max_length=100)
    position = models.CharField(max_length=10, choices=POSITIONS)

    def __str__(self):
        return f"{self.name} - {self.position}"


# ---------------------------------------------------------
# PLAYER REGISTRATION
# ---------------------------------------------------------
class PlayerRegistration(models.Model):
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=20)
    preferred_club = models.CharField(max_length=100, blank=True, null=True)
    position = models.CharField(max_length=10, choices=POSITIONS)

    region = models.CharField(max_length=10, choices=REGIONS, blank=True, null=True)
    platform = models.CharField(max_length=10, choices=PLATFORMS, blank=True, null=True)

    timestamp = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.position})"


# -------------------------
#  SEASON
# -------------------------
class Season(models.Model):
    name = models.CharField(max_length=100)
    year = models.IntegerField()
    is_active = models.BooleanField(default=False)

    clubs = models.ManyToManyField("Club", related_name="seasons", blank=True)

    def __str__(self):
        return f"{self.name} ({self.year})"


# -------------------------
#  CLUB / TEAM
# -------------------------
class Club(models.Model):
    name = models.CharField(max_length=100, unique=True)
    founded = models.IntegerField(null=True, blank=True)
    stadium = models.CharField(max_length=100, null=True, blank=True)
    short_name = models.CharField(max_length=20, blank=True, null=True)
    
    logo = models.ImageField(
        upload_to='league/pplLogos/', 
        null=True, 
        blank=True
    )

    seed_rank = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Lower = stronger seed (1 is top seed). Leave blank for unseeded."
    )

    def __str__(self):
        return self.name
    
    @property
    def logo_url(self):
        """Get the proper Cloudinary URL for the logo"""
        if self.logo:
            try:
                import cloudinary
                # If logo.name is a Cloudinary public_id, build the URL
                return cloudinary.CloudinaryImage(str(self.logo.name)).build_url()
            except Exception:
                # Fallback to default URL
                return self.logo.url if self.logo else None
        return None


# -------------------------
#  PLAYER
# -------------------------
class Player(models.Model):
    gamertag = models.CharField("Name/Gamertag", max_length=100)
    platform = models.CharField(
        max_length=10,
        choices=[
            ('PS5', 'PlayStation 5'),
            ('XBOX', 'Xbox'),
            ('PC', 'PC'),
        ]
    )
    club = models.ForeignKey("Club", on_delete=models.CASCADE, related_name='players')
    position = models.CharField(max_length=50)
    location = models.CharField(max_length=50, blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.gamertag


# -------------------------
#  GROUP STAGE
# -------------------------
class Group(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.season.name} - {self.name}"


class GroupMembership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    club = models.ForeignKey("Club", on_delete=models.CASCADE, related_name='group_entries')

    class Meta:
        unique_together = ('group', 'club')

    def __str__(self):
        return f"{self.group} - {self.club}"


class Fixture(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='fixtures')
    home_club = models.ForeignKey("Club", on_delete=models.CASCADE, related_name='home_fixtures')
    away_club = models.ForeignKey("Club", on_delete=models.CASCADE, related_name='away_fixtures')
    date = models.DateTimeField()
    week_number = models.IntegerField(blank=True, null=True)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, create_match=True, **kwargs):
        super().save(*args, **kwargs)
        if create_match:
            # Avoid circular import by importing GroupMatch locally using apps.get_model
            from django.apps import apps
            GroupMatch = apps.get_model('league', 'GroupMatch')
            GroupMatch.objects.get_or_create(fixture=self)

    def __str__(self):
        return f"{self.season} - {self.home_club} vs {self.away_club}"


# -------------------------
#  GROUP MATCH (RENAMED FROM Match)
# -------------------------
class GroupMatch(models.Model):
    fixture = models.OneToOneField(
        Fixture,
        on_delete=models.CASCADE,
        related_name='group_match'
    )
    home_goals = models.IntegerField(default=0)
    away_goals = models.IntegerField(default=0)
    is_played = models.BooleanField(default=False)

    home_players = models.ManyToManyField(
        Player,
        related_name='home_group_matches',
        blank=True
    )
    away_players = models.ManyToManyField(
        Player,
        related_name='away_group_matches',
        blank=True
    )

    class Meta:
        pass

    def __str__(self):
        return f"{self.fixture} ({self.home_goals}-{self.away_goals})"



    @property
    def winner(self):
        if self.home_goals > self.away_goals:
            return self.fixture.home_club
        elif self.away_goals > self.home_goals:
            return self.fixture.away_club
        return None

        season = self.fixture.season
        home_club = self.fixture.home_club
        away_club = self.fixture.away_club

        for club in (home_club, away_club):
            stats, _ = TeamSeasonStats.objects.get_or_create(team=club, season=season)

            matches = GroupMatch.objects.filter(
                fixture__season=season,
                is_played=True
            ).filter(
                models.Q(fixture__home_club=club) | models.Q(fixture__away_club=club)
            )

            played = wins = draws = losses = goals_for = goals_against = 0

            for m in matches:
                if m.fixture.home_club_id == club.id:
                    gf = m.home_goals
                    ga = m.away_goals
                    if m.home_goals > m.away_goals:
                        w, d, l = 1, 0, 0
                    elif m.home_goals < m.away_goals:
                        w, d, l = 0, 0, 1
                    else:
                        w, d, l = 0, 1, 0
                else:
                    gf = m.away_goals
                    ga = m.home_goals
                    if m.away_goals > m.home_goals:
                        w, d, l = 1, 0, 0
                    elif m.away_goals < m.home_goals:
                        w, d, l = 0, 0, 1
                    else:
                        w, d, l = 0, 1, 0

                played += 1
                wins += w
                draws += d
                losses += l
                goals_for += gf
                goals_against += ga

            stats.played = played
            stats.wins = wins
            stats.draws = draws
            stats.losses = losses
            stats.goals_for = goals_for
            stats.goals_against = goals_against
            stats.goal_difference = goals_for - goals_against
            stats.points = wins * 3 + draws
            stats.save()


# -------------------------
#  PLAYER MATCH STATS (UPDATED)
# -------------------------
class PlayerMatchStats(models.Model):
    group_match = models.ForeignKey(
        'GroupMatch',
        on_delete=models.CASCADE,
        related_name="player_stats",
        null=True,
        blank=True,
    )

    # Support knockout/final matches
    knockout_match = models.ForeignKey(
        'KnockoutMatch',
        on_delete=models.CASCADE,
        related_name='player_stats',
        null=True,
        blank=True,
    )

    # Also allow linking directly to a Fixture when appropriate
    fixture = models.ForeignKey(
        'Fixture',
        on_delete=models.CASCADE,
        related_name='player_stats',
        null=True,
        blank=True,
    )

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='match_stats')

    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    minutes_played = models.IntegerField(default=0)
    rating = models.FloatField(default=0)
    man_of_the_match = models.BooleanField(default=False)

    def __str__(self):
        match_ref = self.group_match or self.knockout_match or self.fixture
        return f"{self.player} - {match_ref}"


# -------------------------
#  PLAYER SEASON STATS
# -------------------------
class PlayerSeasonStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='season_stats')
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='player_stats')
    club = models.ForeignKey("Club", on_delete=models.CASCADE, related_name='player_season_stats')

    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    clean_sheets = models.IntegerField(default=0)
    appearances = models.IntegerField(default=0)
    rating = models.FloatField(default=0)

    manual = models.BooleanField(default=False)

    class Meta:
        unique_together = ('player', 'season')

    def __str__(self):
        return f"{self.player} - {self.season}"


# -------------------------
#  TEAM SEASON STATS
# -------------------------
class TeamSeasonStats(models.Model):
    team = models.ForeignKey("Club", on_delete=models.CASCADE)
    season = models.ForeignKey(Season, on_delete=models.CASCADE)

    played = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    points = models.IntegerField(default=0)

    goals_for = models.IntegerField(default=0)
    goals_against = models.IntegerField(default=0)
    goal_difference = models.IntegerField(default=0)
    clean_sheets = models.IntegerField(default=0)

    finish_position = models.CharField(
        max_length=20,
        choices=[
            ("champion", "Champion"),
            ("runner_up", "Runner Up"),
            ("third", "Third Place"),
            ("semis", "Semi Finalist"),
            ("groups", "Group Stage"),
        ],
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.team.name} - {self.season.name}"


# -------------------------
#  KNOCKOUTS
# -------------------------
class KnockoutRound(models.Model):
    ROUND_CHOICES = [
        ("R16", "Round of 16"),
        ("QF", "Quarterfinals"),
        ("SF", "Semifinals"),
        ("F", "Final"),
        ("3P", "Third Place Match"),
    ]

    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='knockout_rounds')
    round_type = models.CharField(max_length=3, choices=ROUND_CHOICES)

    def __str__(self):
        return f"{self.season.name} - {self.get_round_type_display()}"


class KnockoutMatch(models.Model):
    round = models.ForeignKey(
        KnockoutRound,
        on_delete=models.CASCADE,
        related_name='matches'
    )

    home_club = models.ForeignKey(
        "Club",
        on_delete=models.SET_NULL,
        related_name='knockout_home',
        null=True,
        blank=True
    )
    away_club = models.ForeignKey(
        "Club",
        on_delete=models.SET_NULL,
        related_name='knockout_away',
        null=True,
        blank=True
    )

    home_placeholder = models.CharField(max_length=10, null=True, blank=True)
    away_placeholder = models.CharField(max_length=10, null=True, blank=True)

    home_goals = models.IntegerField(default=0)
    away_goals = models.IntegerField(default=0)
    is_played = models.BooleanField(default=False)

    # Players involved in the knockout match (selected from the clubs)
    home_players = models.ManyToManyField(
        Player,
        related_name='home_knockout_matches',
        blank=True,
    )
    away_players = models.ManyToManyField(
        Player,
        related_name='away_knockout_matches',
        blank=True,
    )

    def __str__(self):
        home = self.home_club.name if self.home_club else self.home_placeholder
        away = self.away_club.name if self.away_club else self.away_placeholder
        return f"{self.round} - {home} vs {away}"


class SeasonAwards(models.Model):
    season = models.OneToOneField(Season, on_delete=models.CASCADE, related_name='awards')

    mvp = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='mvp_awards'
    )
    top_scorer = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='golden_boot_awards'
    )
    top_assister = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='playmaker_awards'
    )
    best_defender = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='defender_awards'
    )
    best_midfielder = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='midfielder_awards'
    )

    def __str__(self):
        return f"Awards for {self.season}"
