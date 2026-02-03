import pandas as pd
from league.models import Club, Player

# -------------------------
# LOAD EXCEL
# -------------------------
df_clubs = pd.read_excel("import_data.xlsx", sheet_name="clubs")
df_players = pd.read_excel("import_data.xlsx", sheet_name="players")

# -------------------------
# PLATFORM NORMALIZATION
# -------------------------
PLATFORM_MAP = {
    "PlayStation 5": "PS5",
    "PS5": "PS5",
    "Xbox": "XBOX",
    "XBOX": "XBOX",
    "PC": "PC",
}

# -------------------------
# CREATE CLUBS
# -------------------------
print("Creating clubs...")

for _, row in df_clubs.iterrows():
    name = str(row["Name"]).strip()

    club, created = Club.objects.get_or_create(
        name=name,
        defaults={
            "founded": row.get("Founded", None),
            "stadium": row.get("Stadium", None),
            "short_name": row.get("Short Name", None),
        }
    )

    print(f"{'Created' if created else 'Exists'}: {club.name}")

print("Clubs imported.\n")

# -------------------------
# CREATE PLAYERS
# -------------------------
print("Creating players...")

for _, row in df_players.iterrows():
    gamertag = str(row["Name/Gamertag:"]).strip()
    platform_raw = str(row["Platform"]).strip()
    club_name = str(row["Club"]).strip()
    position = str(row["Position"]).strip()
    location = str(row["Location"]).strip() if not pd.isna(row["Location"]) else None
    age = int(row["Age"]) if not pd.isna(row["Age"]) else None

    # Normalize platform
    platform = PLATFORM_MAP.get(platform_raw, "PS5")

    # Handle "None" club
    if club_name.lower() == "none":
        print(f"Skipping player without club: {gamertag}")
        continue

    # Fetch club
    try:
        club = Club.objects.get(name=club_name)
    except Club.DoesNotExist:
        print(f"ERROR: Club '{club_name}' not found for player {gamertag}. Skipping.")
        continue

    # Create player
    player, created = Player.objects.get_or_create(
        gamertag=gamertag,
        defaults={
            "platform": platform,
            "club": club,
            "position": position,
            "location": location,
            "age": age,
        }
    )

    print(f"{'Created' if created else 'Exists'}: {player.gamertag} → {club.name}")

print("Players imported successfully.")
