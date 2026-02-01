from django.db import models

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

    # NEW: optional seeding for draws/brackets
    seed_rank = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Lower = stronger seed (1 is top seed). Leave blank for unseeded."
    )

    def __str__(self):
        return self.name


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
    name = models.CharField(max_length=5)  # e.g. "Group A"

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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from .models import Match
        Match.objects.get_or_create(fixture=self)

    def __str__(self):
        return f"{self.season} - {self.home_club} vs {self.away_club}"



class Match(models.Model):
    fixture = models.OneToOneField(Fixture, on_delete=models.CASCADE, related_name='match')
    home_goals = models.IntegerField(default=0)
    away_goals = models.IntegerField(default=0)
    is_played = models.BooleanField(default=False)

    # NEW: players who played
    home_players = models.ManyToManyField(Player, related_name='home_matches', blank=True)
    away_players = models.ManyToManyField(Player, related_name='away_matches', blank=True)

    def __str__(self):
        return f"{self.fixture} ({self.home_goals}-{self.away_goals})"

    @property
    def winner(self):
        if self.home_goals > self.away_goals:
            return self.fixture.home_club
        elif self.away_goals > self.home_goals:
            return self.fixture.away_club
        return None


# -------------------------
#  PLAYER MATCH STATS
# -------------------------

class PlayerMatchStats(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='player_stats')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='match_stats')

    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    minutes_played = models.IntegerField(default=0)
    rating = models.FloatField(default=0)

    def __str__(self):
        return f"{self.player} - {self.match}"


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

    # Real teams (filled once standings exist)
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

    # Placeholder slots (A1, B2, C1, etc.)
    home_placeholder = models.CharField(
        max_length=10,
        null=True,
        blank=True
    )
    away_placeholder = models.CharField(
        max_length=10,
        null=True,
        blank=True
    )

    # Match result
    home_goals = models.IntegerField(default=0)
    away_goals = models.IntegerField(default=0)
    is_played = models.BooleanField(default=False)

    def __str__(self):
        # Show placeholder if real team not assigned yet
        home = self.home_club.name if self.home_club else self.home_placeholder
        away = self.away_club.name if self.away_club else self.away_placeholder
        return f"{self.round} - {home} vs {away}"

    
class SeasonAwards(models.Model):
    """
    Awards per season (MVP, top scorer, etc.).
    Works for both archived and active seasons.
    """
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


