import pandas as pd
from django.core.management.base import BaseCommand
from league.models import Club, Player


class Command(BaseCommand):
    help = "Import clubs and players from an Excel file"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to the Excel file")

    def handle(self, *args, **options):
        file_path = options["file_path"]

        self.stdout.write(self.style.SUCCESS(f"Reading Excel file: {file_path}"))

        # Load Excel
        try:
            xls = pd.ExcelFile(file_path)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading file: {e}"))
            return

        # ---------------------------
        # IMPORT CLUBS
        # ---------------------------
        if "clubs" not in xls.sheet_names:
            self.stdout.write(self.style.ERROR("Missing sheet: 'clubs'"))
            return

        clubs_df = pd.read_excel(xls, "clubs")

        club_count = 0
        for _, row in clubs_df.iterrows():
            name = str(row["Name"]).strip()

            club, created = Club.objects.get_or_create(
                name=name,
                defaults={
                    "short_name": row.get("Short Name", None),
                },
            )

            if created:
                club_count += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {club_count} new clubs"))

        # ---------------------------
        # IMPORT PLAYERS
        # ---------------------------
        if "players" not in xls.sheet_names:
            self.stdout.write(self.style.ERROR("Missing sheet: 'players'"))
            return

        players_df = pd.read_excel(xls, "players")

        player_count = 0
        for _, row in players_df.iterrows():
            gamertag = str(row["Name/Gamertag:"]).strip()
            club_name = str(row["Club"]).strip()

            # Skip players with "None" club
            if club_name.lower() == "none":
                self.stdout.write(self.style.WARNING(f"Skipping player with no club: {gamertag}"))
                continue

            try:
                club = Club.objects.get(name=club_name)
            except Club.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Club not found for player {gamertag}: {club_name}"))
                continue

            # ---------------------------
            # PLATFORM NORMALIZATION
            # ---------------------------
            raw_platform = str(row.get("Platform", "")).strip().lower()

            if "playstation" in raw_platform or "ps" in raw_platform:
                platform = "PS5"
            elif "xbox" in raw_platform:
                platform = "XBOX"
            elif "pc" in raw_platform:
                platform = "PC"
            else:
                platform = "PC"  # fallback

            # ---------------------------
            # CREATE PLAYER
            # ---------------------------
            player, created = Player.objects.get_or_create(
                gamertag=gamertag,
                defaults={
                    "platform": platform,
                    "club": club,
                    "position": row.get("Position", None),
                    "location": row.get("Location", None),
                    "age": row.get("Age", None),
                },
            )

            if created:
                player_count += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {player_count} new players"))
        self.stdout.write(self.style.SUCCESS("Excel import completed successfully!"))
