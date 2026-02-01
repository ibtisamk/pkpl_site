import random
from django.db import transaction
from league.models import Group, GroupMembership

@transaction.atomic
def generate_groups_for_season(
    season,
    num_groups=4,
    random_draw=True,
    use_seeds=True,
):
    clubs = list(season.clubs.all())

    if not clubs:
        raise ValueError("No clubs assigned to this season.")

    # Sort by seed if requested
    if use_seeds:
        clubs.sort(key=lambda c: c.seed_rank if c.seed_rank is not None else 9999)

    if random_draw:
        random.shuffle(clubs)

    # Delete old groups + memberships
    GroupMembership.objects.filter(group__season=season).delete()
    Group.objects.filter(season=season).delete()

    # Create groups
    groups = []
    for i in range(num_groups):
        group = Group.objects.create(
            season=season,
            name=f"Group {chr(ord('A') + i)}"
        )
        groups.append(group)

    # Assign clubs
    for idx, club in enumerate(clubs):
        group = groups[idx % num_groups]
        GroupMembership.objects.create(group=group, club=club)

    return groups
