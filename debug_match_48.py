import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pkpl_site.settings')
django.setup()

from league.models import GroupMatch, Player

match = GroupMatch.objects.select_related(
    'fixture__home_club',
    'fixture__away_club'
).prefetch_related('home_players', 'away_players').get(id=48)

print(f"Match ID: {match.id}")
print(f"Home Club: {match.fixture.home_club.name} (ID: {match.fixture.home_club.id})")
print(f"Away Club: {match.fixture.away_club.name} (ID: {match.fixture.away_club.id})")
print()

print("=== HOME PLAYERS IN MATCH ===")
home_players_in_match = match.home_players.all()
print(f"Count: {home_players_in_match.count()}")
for p in home_players_in_match:
    print(f"  - {p.gamertag} (ID: {p.id})")
print()

print("=== AWAY PLAYERS IN MATCH ===")
away_players_in_match = match.away_players.all()
print(f"Count: {away_players_in_match.count()}")
for p in away_players_in_match:
    print(f"  - {p.gamertag} (ID: {p.id})")
print()

print("=== ALL PLAYERS FOR HOME CLUB ===")
home_club_players = Player.objects.filter(club=match.fixture.home_club)
print(f"Count: {home_club_players.count()}")
for p in home_club_players:
    print(f"  - {p.gamertag} (ID: {p.id})")
print()

print("=== ALL PLAYERS FOR AWAY CLUB ===")
away_club_players = Player.objects.filter(club=match.fixture.away_club)
print(f"Count: {away_club_players.count()}")
for p in away_club_players:
    print(f"  - {p.gamertag} (ID: {p.id})")
print()

# Check other matches for these teams
print("=== OTHER MATCHES FOR HOME CLUB ===")
other_home_matches = GroupMatch.objects.filter(
    fixture__home_club=match.fixture.home_club
).exclude(id=48).prefetch_related('home_players')[:3]

for m in other_home_matches:
    print(f"Match {m.id}: {m.home_players.count()} players")
    
print()
print("=== OTHER MATCHES FOR AWAY CLUB ===")
other_away_matches = GroupMatch.objects.filter(
    fixture__away_club=match.fixture.away_club
).exclude(id=48).prefetch_related('away_players')[:3]

for m in other_away_matches:
    print(f"Match {m.id}: {m.away_players.count()} players")
