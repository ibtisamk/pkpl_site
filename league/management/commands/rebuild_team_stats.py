from django.core.management.base import BaseCommand
from league.models import Season, TeamSeasonStats, GroupMatch
from django.db.models import Q


class Command(BaseCommand):
    help = 'Rebuild team season stats for all teams in active season'

    def handle(self, *args, **options):
        season = Season.objects.filter(is_active=True).first()
        if not season:
            self.stdout.write(self.style.ERROR('No active season found'))
            return

        self.stdout.write(f'Rebuilding team stats for {season.name}...')

        team_stats = TeamSeasonStats.objects.filter(season=season)
        
        for stats in team_stats:
            team = stats.team
            
            # Reset
            stats.played = 0
            stats.wins = 0
            stats.draws = 0
            stats.losses = 0
            stats.goals_for = 0
            stats.goals_against = 0
            stats.clean_sheets = 0
            stats.points = 0
            stats.goal_difference = 0

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

            stats.goal_difference = stats.goals_for - stats.goals_against
            stats.save()
            
            self.stdout.write(
                f'  {team.name}: P{stats.played} GF{stats.goals_for} GA{stats.goals_against} GD{stats.goal_difference} Pts{stats.points}'
            )

        self.stdout.write(self.style.SUCCESS(f'Successfully rebuilt stats for {team_stats.count()} teams'))
