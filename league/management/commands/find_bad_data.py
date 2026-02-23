from django.core.management.base import BaseCommand
from league.models import Player, Club, Season, Fixture, GroupMatch


class Command(BaseCommand):
    help = 'Find records with encoding issues'

    def handle(self, *args, **options):
        self.stdout.write('Checking for bad data...\n')

        # Check Players
        self.stdout.write(self.style.WARNING('Checking Players...'))
        bad_players = []
        for p in Player.objects.all():
            try:
                _ = str(p)
                _ = p.gamertag.encode('utf-8').decode('utf-8')
            except Exception as e:
                bad_players.append((p.id, p.gamertag, str(e)))
                self.stdout.write(self.style.ERROR(f'  Player ID {p.id}: {e}'))
        
        if not bad_players:
            self.stdout.write(self.style.SUCCESS('  ✓ All players OK'))
        else:
            self.stdout.write(self.style.ERROR(f'  Found {len(bad_players)} bad players'))

        # Check Clubs
        self.stdout.write(self.style.WARNING('\nChecking Clubs...'))
        bad_clubs = []
        for c in Club.objects.all():
            try:
                _ = str(c)
                _ = c.name.encode('utf-8').decode('utf-8')
            except Exception as e:
                bad_clubs.append((c.id, c.name, str(e)))
                self.stdout.write(self.style.ERROR(f'  Club ID {c.id}: {e}'))
        
        if not bad_clubs:
            self.stdout.write(self.style.SUCCESS('  ✓ All clubs OK'))
        else:
            self.stdout.write(self.style.ERROR(f'  Found {len(bad_clubs)} bad clubs'))

        # Check Seasons
        self.stdout.write(self.style.WARNING('\nChecking Seasons...'))
        bad_seasons = []
        for s in Season.objects.all():
            try:
                _ = str(s)
                _ = s.name.encode('utf-8').decode('utf-8')
            except Exception as e:
                bad_seasons.append((s.id, s.name, str(e)))
                self.stdout.write(self.style.ERROR(f'  Season ID {s.id}: {e}'))
        
        if not bad_seasons:
            self.stdout.write(self.style.SUCCESS('  ✓ All seasons OK'))
        else:
            self.stdout.write(self.style.ERROR(f'  Found {len(bad_seasons)} bad seasons'))

        # Check Fixtures
        self.stdout.write(self.style.WARNING('\nChecking Fixtures...'))
        bad_fixtures = []
        count = 0
        for f in Fixture.objects.all()[:100]:  # Check first 100
            count += 1
            try:
                _ = str(f)
            except Exception as e:
                bad_fixtures.append((f.id, str(e)))
                self.stdout.write(self.style.ERROR(f'  Fixture ID {f.id}: {e}'))
        
        if not bad_fixtures:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Checked {count} fixtures, all OK'))
        else:
            self.stdout.write(self.style.ERROR(f'  Found {len(bad_fixtures)} bad fixtures'))

        # Summary
        self.stdout.write('\n' + '='*50)
        total_bad = len(bad_players) + len(bad_clubs) + len(bad_seasons) + len(bad_fixtures)
        if total_bad == 0:
            self.stdout.write(self.style.SUCCESS('✓ No encoding issues found!'))
        else:
            self.stdout.write(self.style.ERROR(f'✗ Found {total_bad} records with issues'))
            self.stdout.write('\nTo fix, you can:')
            self.stdout.write('1. Manually edit bad records in admin')
            self.stdout.write('2. Delete and recreate them')
            self.stdout.write('3. Use Django shell to update:')
            if bad_players:
                for pid, name, error in bad_players[:3]:
                    self.stdout.write(f'   Player.objects.filter(id={pid}).update(gamertag="FixedName")')
