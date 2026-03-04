import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pkpl_site.settings')
django.setup()

from league.models import Club, GroupMatch, TeamSeasonStats, Season
from django.db.models import Q

season = Season.objects.filter(is_active=True).first()
club = Club.objects.get(id=20)

print(f'Club: {club.name}')
print(f'Season: {season.name}')
print()

matches = (
    GroupMatch.objects.filter(fixture__season=season, fixture__home_club=club) |
    GroupMatch.objects.filter(fixture__season=season, fixture__away_club=club)
).distinct().select_related('fixture__home_club', 'fixture__away_club')

print(f'Total matches: {matches.count()}')
print()

for m in matches:
    print(f'Match {m.id}: {m.fixture.home_club.name} vs {m.fixture.away_club.name}')
    print(f'  Played: {m.is_played}')
    print(f'  Score: {m.home_goals}-{m.away_goals}')
    print()

stats = TeamSeasonStats.objects.filter(team=club, season=season).first()
if stats:
    print(f'TeamSeasonStats:')
    print(f'  Played: {stats.played}')
    print(f'  Wins: {stats.wins}')
    print(f'  Draws: {stats.draws}')
    print(f'  Losses: {stats.losses}')
    print(f'  Goals For: {stats.goals_for}')
    print(f'  Goals Against: {stats.goals_against}')
    print(f'  Points: {stats.points}')
else:
    print('No TeamSeasonStats found')
