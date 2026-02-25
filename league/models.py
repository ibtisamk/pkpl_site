from django.db import models
from django.db.utils import ProgrammingError
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
    ("ST", "Striker"),
    ("LW", "Left Wing"),
    ("RW", "Right Wing"),
    ("CM", "Central Midfielder"),
    ("CDM", "Defensive Midfielder"),
    ("CAM", "Attacking Midfielder"),
    ("LB", "Left Back"),
    ("CB", "Centre Back"),
    ("RB", "Right Back"),
    ("GK", "Goalkeeper"),
    ("ANY", "Any Position"),
]

# Map positions to broader categories for TOTW
POSITION_CATEGORIES = {
    'ST': 'ATT', 'LW': 'ATT', 'RW': 'ATT',
    'CAM': 'MID', 'CM': 'MID', 'CDM': 'MID',
    'LB': 'DEF', 'CB': 'DEF', 'RB': 'DEF',
    'GK': 'GK',
    'ANY': 'ANY',
}

MATCH_POSITIONS = [
    ('ATT', 'Attacker'),
    ('MID', 'Midfielder'),
    ('DEF', 'Defender'),
    ('GK', 'Goalkeeper'),
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

    class Meta:
        indexes = [
            models.Index(fields=['season', 'date']),
            models.Index(fields=['season', 'week_number']),
            models.Index(fields=['season', 'group']),
        ]

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
    
    # Position played in this specific match
    position_played = models.CharField(
        max_length=3,
        choices=MATCH_POSITIONS,
        null=True,
        blank=True,
        help_text="Position played in this match (for TOTW selection)"
    )

    class Meta:
        indexes = [
            models.Index(fields=['player', 'group_match']),
            models.Index(fields=['player', 'knockout_match']),
            models.Index(fields=['group_match', 'rating']),
            models.Index(fields=['man_of_the_match']),
            models.Index(fields=['position_played', '-rating']),
        ]

    def __str__(self):
        return f"{self.player.gamertag} - Match Stats"


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
    
    # Weighted rating (Bayesian average) for fair rankings
    skill_rating = models.FloatField(
        default=0,
        help_text="Weighted average rating accounting for games played"
    )

    manual = models.BooleanField(default=False)

    class Meta:
        unique_together = ('player', 'season')
        indexes = [
            models.Index(fields=['season', 'player']),
            models.Index(fields=['season', '-rating', '-goals', '-assists']),
            models.Index(fields=['season', '-skill_rating']),
            models.Index(fields=['season', '-goals', '-assists']),
            models.Index(fields=['season', 'appearances']),
        ]
    
    def _get_contribution_points_per_match(self):
        """
        Calculate contribution points based on position-weighted scoring.
        Returns average contribution points per match.
        """
        if self.appearances == 0:
            return 0.0
        
        # Get player position from Player model (with safety check)
        try:
            position = self.player.position if self.player else 'ANY'
        except Exception:
            position = 'ANY'
        
        # Determine position category
        attackers = ['ST', 'LW', 'RW']
        midfielders = ['CAM', 'CM']
        defenders = ['LB', 'CB', 'RB']
        goalkeepers = ['GK']
        
        # Calculate base contribution points
        total_points = 0.0
        
        if position in attackers:
            # Attackers: Goal=5, Assist=3
            total_points = (self.goals * 5) + (self.assists * 3)
            max_per_match = 15
            
        elif position in midfielders:
            # Midfielders: Goal=5, Assist=3
            total_points = (self.goals * 5) + (self.assists * 3)
            max_per_match = 12
            
        elif position in defenders:
            # Defenders: Goal=6, Assist=5, Clean Sheet=3
            total_points = (self.goals * 6) + (self.assists * 5) + (self.clean_sheets * 3)
            max_per_match = 10
            
        elif position in goalkeepers:
            # Goalkeepers: Clean Sheet=3
            total_points = self.clean_sheets * 3
            max_per_match = 8
            
        else:
            # Others (CDM, etc.): Clean Sheet=2
            total_points = (self.goals * 5) + (self.assists * 3) + (self.clean_sheets * 2)
            max_per_match = 12
        
        # Apply per-match cap
        max_total_allowed = max_per_match * self.appearances
        total_points = min(total_points, max_total_allowed)
        
        # Return average per match
        return total_points / self.appearances
    
    def calculate_skill_rating(self):
        """
        Calculate weighted skill rating combining match rating and contribution score.
        
        Formula:
        - Match Rating Weight: 80%
        - Contribution Score Weight: 20%
        - SkillRating = (0.8 * AvgMatchRating) + (0.2 * ContributionScore)
        
        Contribution scoring is position-based with per-match caps to prevent stat padding.
        """
        if self.appearances == 0:
            self.skill_rating = 0.0
            return self.skill_rating
        
        # 80% weight: Average Match Rating
        match_rating_component = 0.8 * self.rating
        
        # 20% weight: Contribution Score
        contribution_score = self._get_contribution_points_per_match()
        contribution_component = 0.2 * contribution_score
        
        # Final weighted skill rating
        self.skill_rating = match_rating_component + contribution_component
        
        return self.skill_rating
    
    def save(self, *args, **kwargs):
        # Auto-calculate skill rating on save
        if self.rating > 0 or self.appearances > 0:
            try:
                self.calculate_skill_rating()
            except Exception:
                pass
        super().save(*args, **kwargs)

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

    class Meta:
        indexes = [
            models.Index(fields=['season', 'team']),
            models.Index(fields=['season', '-points', '-goal_difference', '-goals_for']),
        ]

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


# -------------------------
#  TEAM OF THE WEEK
# -------------------------
class TeamOfTheWeek(models.Model):
    """Represents a Team of the Week event for a specific period"""
    WEEK_TYPES = [
        ('GW', 'Gameweek'),
        ('KO', 'Knockout Stage'),
        ('TOTS', 'Team of the Season'),
    ]
    
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='team_of_weeks')
    week_number = models.IntegerField(help_text="Week number (1, 2, 3, etc.)")
    week_type = models.CharField(max_length=4, choices=WEEK_TYPES, default='GW')
    
    # Date range for this TOTW
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    # Publishing status
    is_published = models.BooleanField(
        default=False,
        help_text="Make this TOTW visible on the website"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('season', 'week_number', 'week_type')
        ordering = ['-season__year', 'week_type', 'week_number']
        indexes = [
            models.Index(fields=['season', 'week_type', 'week_number']),
            models.Index(fields=['is_published', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.season.name} - {self.get_week_type_display()} {self.week_number}"
    
    @property
    def title(self):
        if self.week_type == 'TOTS':
            return f"Team of the Season - {self.season.name}"
        elif self.week_type == 'KO':
            return f"Knockout Stage TOTW - {self.season.name}"
        return f"Gameweek {self.week_number} TOTW"


class TeamOfTheWeekSelection(models.Model):
    """Individual player selection in a Team of the Week"""
    totw = models.ForeignKey(
        TeamOfTheWeek,
        on_delete=models.CASCADE,
        related_name='selections'
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name='totw_selections'
    )
    position = models.CharField(
        max_length=3,
        choices=MATCH_POSITIONS,
        help_text="Position for this TOTW selection"
    )
    
    # Stats for this specific period
    games_played = models.IntegerField(default=0)
    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    clean_sheets = models.IntegerField(default=0)
    avg_rating = models.FloatField(default=0)
    
    # Display order (1-11 for starting XI)
    lineup_position = models.IntegerField(
        default=0,
        help_text="Position in lineup for display (1-11)"
    )
    
    class Meta:
        unique_together = ('totw', 'player')
        ordering = ['lineup_position']
        indexes = [
            models.Index(fields=['totw', 'position']),
            models.Index(fields=['player', '-avg_rating']),
        ]
    
    def __str__(self):
        return f"{self.player.gamertag} - {self.totw} ({self.get_position_display()})"
