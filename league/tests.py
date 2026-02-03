from django.test import TestCase, RequestFactory
from django.contrib import admin
from types import SimpleNamespace
from django.utils import timezone

from .models import Club, Player, Season, Fixture, GroupMatch, PlayerMatchStats, TeamSeasonStats
from django.db.models import Q
from .admin import PlayerMatchStatsInline


class AdminPlayerFilterTest(TestCase):
    def setUp(self):
        self.home = Club.objects.create(name='Home FC')
        self.away = Club.objects.create(name='Away FC')
        self.other = Club.objects.create(name='Other FC')

        self.p1 = Player.objects.create(gamertag='H1', platform='PC', club=self.home, position='ST')
        self.p2 = Player.objects.create(gamertag='A1', platform='PC', club=self.away, position='ST')
        self.p3 = Player.objects.create(gamertag='O1', platform='PC', club=self.other, position='ST')

        season = Season.objects.create(name='Season', year=2025)
        fixture = Fixture.objects.create(season=season, home_club=self.home, away_club=self.away, date=timezone.now())
        # Match is created automatically by Fixture.save()
        self.match = GroupMatch.objects.get(fixture=fixture)

    def test_inline_player_queryset_filtered(self):
        db_field = PlayerMatchStats._meta.get_field('player')
        request = RequestFactory().get(f'/admin/league/match/{self.match.id}/change/')
        request.resolver_match = SimpleNamespace(kwargs={'object_id': str(self.match.id)})

        inline = PlayerMatchStatsInline(PlayerMatchStats, admin.site)
        formfield = inline.formfield_for_foreignkey(db_field, request)
        qs = formfield.queryset

        self.assertIn(self.p1, qs)
        self.assertIn(self.p2, qs)
        self.assertNotIn(self.p3, qs)


class FixturesViewsAndMatchSaveTest(TestCase):
    def setUp(self):
        self.home = Club.objects.create(name='Home FC')
        self.away = Club.objects.create(name='Away FC')
        season = Season.objects.create(name='Season', year=2025)
        self.fixture1 = Fixture.objects.create(season=season, home_club=self.home, away_club=self.away, date=timezone.now())
        self.match1 = GroupMatch.objects.get(fixture=self.fixture1)

        # unplayed fixture 2
        self.fixture2 = Fixture.objects.create(season=season, home_club=self.home, away_club=self.away, date=timezone.now())
        self.match2 = GroupMatch.objects.get(fixture=self.fixture2)

    def test_upcoming_and_results_views(self):
        # mark match1 as played
        self.match1.home_goals = 2
        self.match1.away_goals = 1
        self.match1.save()

        resp_upcoming = self.client.get('/fixtures/upcoming/')
        self.assertEqual(resp_upcoming.status_code, 200)
        self.assertContains(resp_upcoming, self.fixture2.home_club.name)
        self.assertNotContains(resp_upcoming, self.fixture1.home_club.name)

        resp_results = self.client.get('/fixtures/results/')
        self.assertEqual(resp_results.status_code, 200)
        self.assertContains(resp_results, self.fixture1.home_club.name)
        self.assertNotContains(resp_results, self.fixture2.home_club.name)

        # Overview snapshot should show upcoming fixture and link to fixtures page
        resp_overview = self.client.get('/ppl3/overview/')
        self.assertEqual(resp_overview.status_code, 200)
        self.assertContains(resp_overview, self.fixture2.home_club.name)
        self.assertContains(resp_overview, '/fixtures/upcoming/')
        self.assertContains(resp_overview, self.match1.home_club.name)
        self.assertContains(resp_overview, '/fixtures/results/')


    def test_match_save_updates_teamseasonstats(self):
        # ensure stats initially zero
        stats_home = TeamSeasonStats.objects.filter(team=self.home).first()
        self.assertTrue(stats_home is None or stats_home.played == 0)

        # play match1
        self.match1.home_goals = 3
        self.match1.away_goals = 1
        self.match1.save()

        stats_home = TeamSeasonStats.objects.get(team=self.home, season=self.fixture1.season)
        stats_away = TeamSeasonStats.objects.get(team=self.away, season=self.fixture1.season)

        self.assertEqual(stats_home.played, 1)
        self.assertEqual(stats_home.wins, 1)
        self.assertEqual(stats_home.goals_for, 3)
        self.assertEqual(stats_away.losses, 1)
        self.assertEqual(stats_away.goals_against, 3)


class KnockoutGenerationTest(TestCase):
    def setUp(self):
        # Create 4 groups with 2 clubs each (total 8 clubs)
        self.season = Season.objects.create(name='Season X', year=2025)
        self.groups = []
        self.clubs = []
        for i, gname in enumerate(['A', 'B', 'C', 'D']):
            group = self.season.groups.create(name=f'Group {gname}')
            self.groups.append(group)
            for j in range(2):
                club = Club.objects.create(name=f'Club {gname}{j}')
                self.season.clubs.add(club)
                self.clubs.append(club)
                group.members.create(club=club)

        # Create team stats with distinct points so seeding is deterministic
        for idx, club in enumerate(self.clubs):
            TeamSeasonStats.objects.create(
                team=club,
                season=self.season,
                points=10 - idx,  # descending
                goals_for=5 + idx,
                goals_against=2,
            )

    def test_generate_knockouts_creates_fixtures_and_matches_and_is_idempotent(self):
        # Generate knockouts with 8 total teams (2 qualifiers per group)
        from .services import generate_knockouts_for_season
        rnd_obj, matches, fixtures = generate_knockouts_for_season(
            season=self.season,
            total_qualified=8,
            seeded_bracket=True,
            create_fixtures=True,
        )

        # Round created
        self.assertIsNotNone(rnd_obj)
        self.assertEqual(rnd_obj.round_type, 'QF')

        # Four knockout matches expected
        self.assertEqual(len(matches), 4)

        # Four fixtures created (single leg)
        self.assertEqual(len(fixtures), 4)

        # Matches should NOT be automatically created because admin will add matches manually
        for f in fixtures:
            # Each fixture should NOT have a Match created automatically
            self.assertFalse(hasattr(f, 'group_match'))

        # Call generator again; should not duplicate
        before_km_count = KnockoutMatch.objects.filter(round=rnd_obj).count()
        before_fixture_count = Fixture.objects.filter(season=self.season, group__isnull=True).count()

        res = generate_knockouts_for_season(
            season=self.season,
            total_qualified=8,
            seeded_bracket=True,
            create_fixtures=True,
        )

        after_km_count = KnockoutMatch.objects.filter(round=rnd_obj).count()
        after_fixture_count = Fixture.objects.filter(season=self.season, group__isnull=True).count()

        self.assertEqual(before_km_count, after_km_count)
        self.assertEqual(before_fixture_count, after_fixture_count)


    def test_placeholders_then_real_bracket_replaces_placeholders(self):
        # Create season with 4 groups but DO NOT create TeamSeasonStats yet
        s = Season.objects.create(name='Placeholder Season', year=2026)
        clubs = []
        for i, gname in enumerate(['A', 'B', 'C', 'D']):
            group = s.groups.create(name=f'Group {gname}')
            for j in range(2):
                club = Club.objects.create(name=f'P{gname}{j}')
                s.clubs.add(club)
                group.members.create(club=club)
                clubs.append(club)

        # First call should create placeholders
        rnd, status = generate_knockouts_for_season(
            season=s,
            total_qualified=8,
            seeded_bracket=True,
        )

        self.assertEqual(status, 'PLACEHOLDERS_CREATED')
        placeholder_count = KnockoutMatch.objects.filter(round=rnd).count()
        self.assertTrue(placeholder_count > 0)

        # Now create team stats so real teams exist and call again with fixtures creation
        for idx, club in enumerate(clubs):
            TeamSeasonStats.objects.create(
                team=club,
                season=s,
                points=10-idx,
                goals_for=5+idx,
                goals_against=1,
            )

        rnd2, matches, fixtures = generate_knockouts_for_season(
            season=s,
            total_qualified=8,
            seeded_bracket=True,
            create_fixtures=True,
            two_leg_rounds=True,
        )

        # Placeholders should be removed and replaced by real matches
        km_count = KnockoutMatch.objects.filter(round=rnd2, home_placeholder__isnull=False).count()
        self.assertEqual(km_count, 0)

        # Expect 4 knockout matches (8 teams => 4 ties)
        total_km = KnockoutMatch.objects.filter(round=rnd2).count()
        self.assertEqual(total_km, 4)

        # Expect fixtures = ties * 2 (two-leg)
        expected_fixtures = (8 // 2) * 2
        self.assertEqual(len(fixtures), expected_fixtures)


    def test_2_groups_of_4_select_top2_creates_4_fixtures_two_legs(self):
        # Two groups with 4 clubs each -> select top 2 from each -> total_qualified = 4
        s = Season.objects.create(name='Small Season', year=2026)
        clubs = []
        for gname in ['A', 'B']:
            group = s.groups.create(name=f'Group {gname}')
            for j in range(4):
                club = Club.objects.create(name=f'{gname}{j}')
                s.clubs.add(club)
                group.members.create(club=club)
                clubs.append(club)

        # Create team stats so standings exist
        for idx, club in enumerate(clubs):
            TeamSeasonStats.objects.create(
                team=club,
                season=s,
                points=100 - idx,  # descending to seed
                goals_for=10 + idx,
                goals_against=1,
            )

        rnd, matches, fixtures = generate_knockouts_for_season(
            season=s,
            total_qualified=4,
            seeded_bracket=True,
            create_fixtures=True,
            two_leg_rounds=True,
        )

        # total_qualified 4 -> 2 ties -> 4 fixtures (two legs each)
        self.assertEqual(len(matches), 2)
        self.assertEqual(len(fixtures), 4)


class MatchAdminAjaxTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.home = Club.objects.create(name='Home Ajax')
        self.away = Club.objects.create(name='Away Ajax')
        season = Season.objects.create(name='SeasonAjax', year=2025)
        self.fixture = Fixture.objects.create(season=season, home_club=self.home, away_club=self.away, date=timezone.now())
        self.p1 = Player.objects.create(gamertag='H1', platform='PC', club=self.home, position='ST')
        self.p2 = Player.objects.create(gamertag='A1', platform='PC', club=self.away, position='ST')

        # create superuser to access admin view
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'pass')

    def test_players_for_fixture_view(self):
        self.client.force_login(self.admin_user)
        url = f'/admin/league/match/players-for-fixture/?fixture_id={self.fixture.id}'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('home', data)
        self.assertIn('away', data)
        self.assertEqual(len(data['home']), 1)
        self.assertEqual(len(data['away']), 1)
        self.assertEqual(data['home'][0]['id'], self.p1.id)
        self.assertEqual(data['away'][0]['id'], self.p2.id)


class KnockoutResultsVisibilityTest(TestCase):
    def test_knockout_results_appear_on_pages(self):
        season = Season.objects.create(name='KO Season', year=2026, is_active=True)
        round_obj = KnockoutRound.objects.create(season=season, round_type='QF')
        home = Club.objects.create(name='Home KO')
        away = Club.objects.create(name='Away KO')

        km = round_obj.matches.create(home_club=home, away_club=away, home_goals=3, away_goals=1, is_played=True)

        resp_overview = self.client.get('/ppl3/overview/')
        self.assertEqual(resp_overview.status_code, 200)
        self.assertContains(resp_overview, 'Home KO vs Away KO')
        self.assertContains(resp_overview, '3-1')

        resp_knockouts = self.client.get('/ppl3/knockouts/')
        self.assertEqual(resp_knockouts.status_code, 200)
        self.assertContains(resp_knockouts, 'Home KO vs Away KO')
        self.assertContains(resp_knockouts, '3-1')


class KnockoutOverviewDedupTest(TestCase):
    def test_duplicates_are_removed_on_overview(self):
        s = Season.objects.create(name='Dedupe Season', year=2026, is_active=True)
        rnd = KnockoutRound.objects.create(season=s, round_type='SF')
        a = Club.objects.create(name='A Club')
        b = Club.objects.create(name='B Club')

        # Create duplicates and reversed duplicates
        rnd.matches.create(home_club=a, away_club=b)
        rnd.matches.create(home_club=b, away_club=a)
        rnd.matches.create(home_club=a, away_club=b)

        resp = self.client.get('/ppl3/overview/')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')

        # Count occurrences of the pairing in either order; should be 1
        occurrences = content.count('A Club vs B Club') + content.count('B Club vs A Club')
        self.assertEqual(occurrences, 1)


class KnockoutRecordedMatchesTest(TestCase):
    def test_knockout_shows_only_recorded_matches_and_links(self):
        season = Season.objects.create(name='KO Show', year=2026, is_active=True)
        rnd = KnockoutRound.objects.create(season=season, round_type='QF')
        home = Club.objects.create(name='Recorded Home')
        away = Club.objects.create(name='Recorded Away')

        # Create backend tie
        km = rnd.matches.create(home_club=home, away_club=away)

        # Create a fixture and actual Match for this tie
        f = Fixture.objects.create(season=season, home_club=home, away_club=away, date=timezone.now(), group=None)
        # avoid auto-creating a match from fixture.save
        f.save(create_match=False)
        # Create a Match object for this fixture
        match = GroupMatch.objects.create(fixture=f, home_goals=2, away_goals=1, is_played=True)

        resp = self.client.get('/ppl3/knockouts/')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')

        # Should contain the pairing and score
        self.assertIn('Recorded Home vs Recorded Away', content)
        self.assertIn('2-1', content)

        # Should include a link to the match detail page
        self.assertIn(f'/ppl3/match/{match.id}/', content)


class FinalGenerationActionTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser('admin', 'a@b.com', 'pass')

    def test_generate_single_final_from_semis(self):
        season = Season.objects.create(name='FinalSeason', year=2026, is_active=True)
        sf = KnockoutRound.objects.create(season=season, round_type='SF')

        h1 = Club.objects.create(name='H1')
        a1 = Club.objects.create(name='A1')
        h2 = Club.objects.create(name='H2')
        a2 = Club.objects.create(name='A2')

        # Semi 1: H1 beats A1 via fixture match
        km1 = sf.matches.create(home_club=h1, away_club=a1)
        f1 = Fixture(season=season, home_club=h1, away_club=a1, date=timezone.now(), group=None)
        f1.save(create_match=False)
        GroupMatch.objects.create(fixture=f1, home_goals=2, away_goals=0, is_played=True)

        # Semi 2: H2 beats A2 via knockout match record directly
        km2 = sf.matches.create(home_club=h2, away_club=a2, home_goals=1, away_goals=0, is_played=True)

        # Call admin action
        from django.test import RequestFactory
        from django.contrib import admin
        rf = RequestFactory()
        req = rf.post('/admin/league/season/action_generate_final/', data={'match_format': 'single'})
        req.user = self.admin_user

        season_admin = admin.site._registry[Season]
        res = season_admin.action_generate_final(req, Season.objects.filter(id=season.id))

        # Verify a final round exists and fixture created
        final_round = KnockoutRound.objects.filter(season=season, round_type='F').first()
        self.assertIsNotNone(final_round)

        # There should be a fixture between H1 and H2
        final_fixture = Fixture.objects.filter(season=season, group__isnull=True).filter(
            Q(home_club=h1, away_club=h2) | Q(home_club=h2, away_club=h1)
        ).first()
        self.assertIsNotNone(final_fixture)
