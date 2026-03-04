from django.core.management.base import BaseCommand
from league.models import Club, GroupMatch, TeamSeasonStats, Season
from django.db.models import Q


class Command(BaseCommand):
    help = 'Check team match data and stats'

    def add_arguments(self, parser):
        parser.add_argument('club_id', type=int, help='Club ID to check')

    def handle(self, *args, **options):
        club_id = options['club_id']
        
        season = Season.objects.filter(is_active=True).first()
        club = Club.objects.get(id=club_id)

        self.stdout.write(f'Club: {club.name}')
        self.stdout.write(f'Season: {season.name}')
        self.stdout.write('')

        matches = (
            GroupMatch.objects.filter(fixture__season=season, fixture__home_club=club) |
            GroupMatch.objects.filter(fixture__season=season, fixture__away_club=club)
        ).distinct().select_related('fixture__home_club', 'fixture__away_club')

        self.stdout.write(f'Total matches: {matches.count()}')
        self.stdout.write('')

        for m in matches:
            self.stdout.write(f'Match {m.id}: {m.fixture.home_club.name} vs {m.fixture.away_club.name}')
            self.stdout.write(f'  Played: {m.is_played}')
            self.stdout.write(f'  Score: {m.home_goals}-{m.away_goals}')
            self.stdout.write('')

        stats = TeamSeasonStats.objects.filter(team=club, season=season).first()
        if stats:
            self.stdout.write(self.style.SUCCESS('TeamSeasonStats:'))
            self.stdout.write(f'  Played: {stats.played}')
            self.stdout.write(f'  Wins: {stats.wins}')
            self.stdout.write(f'  Draws: {stats.draws}')
            self.stdout.write(f'  Losses: {stats.losses}')
            self.stdout.write(f'  Goals For: {stats.goals_for}')
            self.stdout.write(f'  Goals Against: {stats.goals_against}')
            self.stdout.write(f'  Points: {stats.points}')
        else:
            self.stdout.write(self.style.ERROR('No TeamSeasonStats found'))
