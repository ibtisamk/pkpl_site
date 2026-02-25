from django.core.management.base import BaseCommand
from league.models import PlayerSeasonStats


class Command(BaseCommand):
    help = "Recalculate skill_rating for all PlayerSeasonStats"

    def handle(self, *args, **options):
        # Check if skill_rating column exists before running
        from django.db import connection
        from django.db.utils import ProgrammingError
        
        with connection.cursor() as cursor:
            try:
                cursor.execute("SELECT skill_rating FROM league_playerseasonstats LIMIT 0")
            except ProgrammingError:
                self.stdout.write(self.style.ERROR(
                    "skill_rating column doesn't exist yet. "
                    "Run migrations first: python manage.py migrate"
                ))
                return
        
        stats = PlayerSeasonStats.objects.all()
        count = stats.count()
        
        self.stdout.write(f"Recalculating skill_rating for {count} player season stats...")
        
        updated = 0
        for stat in stats:
            if stat.rating > 0:
                try:
                    stat.calculate_skill_rating()
                    stat.save()  # This will work once column exists
                    updated += 1
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Failed to update {stat}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated} records"))
