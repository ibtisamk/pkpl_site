from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Rebuild PlayerSeasonStats from existing PlayerMatchStats rows"

    def handle(self, *args, **options):
        from league.models import PlayerMatchStats, Player, Season
        try:
            from league.signals import rebuild_player_season_stats
        except Exception:
            rebuild_player_season_stats = None

        def _get_season_from_row(row):
            if getattr(row, 'group_match', None) and row.group_match and getattr(row.group_match, 'fixture', None):
                return row.group_match.fixture
            if getattr(row, 'knockout_match', None) and row.knockout_match and getattr(row.knockout_match, 'round', None):
                return row.knockout_match.round
            if getattr(row, 'fixture', None) and row.fixture:
                return row.fixture
            return None

        qs = PlayerMatchStats.objects.select_related(
            'player', 'fixture', 'group_match__fixture', 'knockout_match__round__season'
        )

        pairs = set()
        for row in qs.iterator():
            season_obj = None
            # group_match -> fixture -> season
            if getattr(row, 'group_match', None) and row.group_match and getattr(row.group_match, 'fixture', None):
                season_obj = row.group_match.fixture.season
            elif getattr(row, 'knockout_match', None) and row.knockout_match and getattr(row.knockout_match, 'round', None):
                season_obj = row.knockout_match.round.season
            elif getattr(row, 'fixture', None) and row.fixture:
                season_obj = row.fixture.season

            if season_obj is None:
                continue

            pairs.add((row.player_id, season_obj.id))

        self.stdout.write(f"Found {len(pairs)} player+season pairs to rebuild")

        from django.contrib.auth import get_user_model

        for player_id, season_id in pairs:
            try:
                player = Player.objects.get(pk=player_id)
                season = Season.objects.get(pk=season_id)
            except Exception:
                continue

            if rebuild_player_season_stats:
                rebuild_player_season_stats(player, season)
                self.stdout.write(f"Rebuilt stats for player {player} season {season}")
            else:
                self.stdout.write("rebuild helper not available, skipping")

        self.stdout.write(self.style.SUCCESS("Done"))
