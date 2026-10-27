from typing import Any

from django.test import TestCase

from server.core.models import Team, User
from server.duplicates.teams.merge import merge_teams
from server.duplicates.teams.models import TeamNotDuplicate
from server.duplicates.teams.suggest import copies_of, normalized_name, suggestions_for
from server.servicerequests.models import ServiceRequest, ServiceRequestType
from server.tests.base import create_event
from server.tournament.models import Tournament


class SuggestTestCase(TestCase):
    def setUp(self) -> None:
        self.mine = Team.objects.create(name="Goosebumps", city="Bengaluru")
        self.copy = Team.objects.create(name="Goose-bumps ")
        self.other = Team.objects.create(name="Puyal")
        self.admin = User.objects.create(username="a@x.com", email="a@x.com")
        self.mine.admins.add(self.admin)

    def at_one_event(self, *teams: Team) -> None:
        Tournament.objects.create(event=create_event("Nationals")).teams.add(*teams)


class TestCopies(SuggestTestCase):
    def test_names_match_ignoring_case_spaces_and_punctuation(self) -> None:
        self.assertEqual(normalized_name("Disc - O - Deewane"), normalized_name("disc-o-deewane"))
        self.assertEqual(copies_of(self.mine), [self.copy])
        self.assertEqual(copies_of(self.other), [])

    def test_a_pair_marked_not_a_copy_is_not_suggested_either_way(self) -> None:
        TeamNotDuplicate.objects.create(team=self.copy, other=self.mine)
        self.assertEqual(copies_of(self.mine), [])
        self.assertEqual(copies_of(self.copy), [])

    def test_teams_at_one_event_are_never_suggested(self) -> None:
        self.at_one_event(self.mine, self.copy)
        self.assertEqual(copies_of(self.mine), [])

    def test_an_admin_of_two_copies_gets_one_suggestion(self) -> None:
        self.copy.admins.add(self.admin)
        self.assertEqual(suggestions_for(self.admin), [(self.mine, [self.copy])])

    def test_an_admin_sees_only_their_own_teams_with_copies(self) -> None:
        Team.objects.create(name="puyal").admins.add(User.objects.create(username="b@x.com"))
        self.other.admins.add(self.admin)
        found = suggestions_for(self.admin)
        self.assertEqual(
            [(team, copies) for team, copies in found],
            [
                (self.mine, [self.copy]),
                (self.other, [Team.objects.get(name="puyal")]),
            ],
        )
        self.assertEqual(suggestions_for(User.objects.create(username="c@x.com")), [])


class TestSuggestionsApi(SuggestTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.admin)

    def get(self, **params: Any) -> Any:
        return self.client.get("/api/team-merge/suggestions", params)

    def dismiss(self, team: Team, other: Team) -> Any:
        return self.client.post(
            "/api/team-merge/not-duplicates",
            {"team_id": team.pk, "other_id": other.pk},
            content_type="application/json",
        )

    def test_lists_each_team_with_its_copies(self) -> None:
        Tournament.objects.create(event=create_event("Regionals")).teams.add(self.copy)
        (found,) = self.get().json()
        self.assertEqual(found["team"]["id"], self.mine.pk)
        self.assertFalse(found["pending"])
        (copy,) = found["copies"]
        self.assertEqual(copy["id"], self.copy.pk)
        self.assertEqual(copy["label"], f"Goose-bumps #{self.copy.pk}")
        self.assertEqual(copy["tournaments"], 1)
        self.assertEqual(self.get(team_id=self.other.pk).json(), [])

    def test_says_when_staff_are_already_asked(self) -> None:
        asked = ServiceRequest.objects.create(
            user=self.admin, type=ServiceRequestType.REQUEST_TEAM_MERGE, message="x"
        )
        asked.service_teams.set([self.mine, self.copy])
        self.assertTrue(self.get().json()[0]["pending"])

    def test_not_a_copy_stops_the_suggestion(self) -> None:
        self.assertEqual(self.dismiss(self.mine, self.copy).status_code, 200)
        self.assertEqual(self.get().json(), [])
        self.assertEqual(self.dismiss(self.mine, self.copy).status_code, 200)
        self.assertEqual(TeamNotDuplicate.objects.count(), 1)

    def test_only_an_admin_of_the_team_may_say_so(self) -> None:
        self.assertEqual(self.dismiss(self.copy, self.mine).status_code, 403)
        self.assertEqual(self.dismiss(self.mine, self.mine).status_code, 400)
        self.assertEqual(self.dismiss(self.mine, self.other).status_code, 400)
        self.assertFalse(TeamNotDuplicate.objects.exists())

    def test_signed_out_gets_nothing(self) -> None:
        self.client.logout()
        self.assertEqual(self.get().status_code, 401)


class TestMergingKeepsDecisions(SuggestTestCase):
    def test_a_pair_stored_both_ways_does_not_block_the_merge(self) -> None:
        third = Team.objects.create(name="goosebumps")
        for a, b in [(self.copy, self.mine), (self.mine, self.copy), (self.copy, third)]:
            TeamNotDuplicate.objects.create(team=a, other=b)
        TeamNotDuplicate.objects.create(team=third, other=self.copy)

        merge_teams(self.mine, [self.copy, third])

        self.assertFalse(TeamNotDuplicate.objects.exists())

    def test_a_decision_follows_the_kept_team_and_a_self_pair_is_dropped(self) -> None:
        third = Team.objects.create(name="Goosebumps B")
        TeamNotDuplicate.objects.create(team=self.copy, other=third)
        TeamNotDuplicate.objects.create(team=self.copy, other=self.mine)

        merge_teams(self.mine, [self.copy])

        (row,) = TeamNotDuplicate.objects.all()
        self.assertEqual((row.team, row.other), (self.mine, third))

    def test_a_decision_both_teams_made_does_not_block_the_merge(self) -> None:
        third = Team.objects.create(name="Goosebumps B")
        TeamNotDuplicate.objects.create(team=self.mine, other=third)
        TeamNotDuplicate.objects.create(team=self.copy, other=third)
        TeamNotDuplicate.objects.create(team=third, other=self.copy)

        merge_teams(self.mine, [self.copy])

        (row,) = TeamNotDuplicate.objects.all()
        self.assertEqual((row.team, row.other), (self.mine, third))
