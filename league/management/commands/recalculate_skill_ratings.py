from django.core.management.base import BaseCommand
from league.models import PlayerSeasonStats


class Command(BaseCommand):
    help = "Recalculate skill_rating for all PlayerSeasonStats"

    def handle(self, *args, **options):
        # Use defer to avoid querying skill_rating if it doesn't exist yet
        try:
            stats = PlayerSeasonStats.objects.defer('skill_rating').all()
        except Exception:
            stats = PlayerSeasonStats.objects.all()
        
        count = stats.count()
        
        self.stdout.write(f"Recalculating skill_rating for {count} player season stats...")
        
        updated = 0
        for stat in stats:
            if stat.rating > 0:
                try:
                    stat.calculate_skill_rating()
                    stat.save()
                    updated += 1
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Failed to update {stat}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated} records"))
