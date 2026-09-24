import datetime
import json
import uuid
from typing import Any
from unittest import mock

from django.apps import apps
from django.core import mail
from django.db.models import ProtectedError
from django.db.models.query import QuerySet
from django.test import TestCase
from django.utils.timezone import now

from server.chat.models import ChatSession
from server.core.models import (
    Accreditation,
    CollegeId,
    CommentaryInfo,
    Guardianship,
    Player,
    Team,
    User,
    Vaccination,
)
from server.duplicates.history import log
from server.duplicates.merge import (
    MergeBlockedError,
    MergeFieldError,
    MergeIncompleteError,
    build_plan,
    find_references,
    merge_accounts,
)
from server.duplicates.models import (
    AccountMerge,
    ClusterEvent,
    ClusterMember,
    DuplicateCluster,
    EmailAlias,
)
from server.membership.models import Membership
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType
from server.tests.base import create_event, create_player, create_tournament
from server.ticket.models import Ticket, TicketMessage
from server.tournament.models import MatchScore, Registration, Tournament
from server.transaction.models import ManualTransaction, PhonePeTransaction
from server.wrapped.models import PlayerWrapped


def row_counts() -> dict[str, int]:
    return {model._meta.label: model._default_manager.count() for model in apps.get_models()}


class MergeTestCase(TestCase):
    def setUp(self) -> None:
        self.primary = self.make_user("primary@x.com")
        self.duplicate = self.make_user("dup@x.com")
        self.primary_player = create_player(self.primary)
        self.duplicate_player = create_player(self.duplicate)
        self.event = create_event("Nationals")
        self.tournament = create_tournament(self.event)

    def make_user(self, username: str, **kwargs: object) -> User:
        return User.objects.create(
            username=username,
            email=username,
            first_name="Rahul",
            last_name="Sharma",
            **kwargs,
        )

    def populate(self, user: User, player: Player, tag: str) -> None:
        """A row in as many relations as the account can hold."""
        Membership.objects.create(
            player=player,
            membership_number=f"MEM-{tag}",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            is_active=True,
        )
        Vaccination.objects.create(player=player, is_vaccinated=True)
        Accreditation.objects.create(
            player=player,
            is_valid=True,
            level="STD",
            date=datetime.date(2026, 1, 1),
            certificate=f"accreditation_certificates/{tag}.pdf",
        )
        CollegeId.objects.create(player=player, expiry=datetime.date(2030, 1, 1))
        CommentaryInfo.objects.create(
            player=player,
            jersey_number=7,
            ultimate_origin="x",
            ultimate_attraction="x",
            ultimate_fav_role="x",
            ultimate_fav_exp="x",
            interests="x",
            fun_fact="x",
        )
        PlayerWrapped.objects.create(player=player, year=2025)
        MatchScore.objects.create(entered_by=player, score_team_1=1, score_team_2=2)

        team = Team.objects.create(name=f"Team {tag}")
        team.admins.add(user)
        player.teams.add(team)
        self.tournament.volunteers.add(user)

        request = ServiceRequest.objects.create(
            user=user, type=ServiceRequestType.REQUEST_SPONSORED_MEMBERSHIP, message="hi"
        )
        request.service_players.add(player)

        ChatSession.objects.create(user=user)
        ticket = Ticket.objects.create(title=f"T {tag}", description="d", created_by=user)
        TicketMessage.objects.create(ticket=ticket, sender=user, message="m")

        transaction = ManualTransaction.objects.create(user=user, amount=100, transaction_id=tag)
        transaction.players.add(player)


class TestMergeKeepsEveryRow(MergeTestCase):
    def test_no_rows_are_lost(self) -> None:
        self.populate(self.primary, self.primary_player, "a")
        self.populate(self.duplicate, self.duplicate_player, "b")
        before = row_counts()

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        after = row_counts()
        # One account and its player are gone; the merge records itself.
        expected = before | {
            "server.User": before["server.User"] - 1,
            "server.Player": before["server.Player"] - 1,
            "server.Membership": before["server.Membership"] - 1,
            "server.Vaccination": before["server.Vaccination"] - 1,
            "server.Accreditation": before["server.Accreditation"] - 1,
            "server.CollegeId": before["server.CollegeId"] - 1,
            "server.CommentaryInfo": before["server.CommentaryInfo"] - 1,
            # unique_together ("player", "year"): one wrapped record survives.
            "server.PlayerWrapped": before["server.PlayerWrapped"] - 1,
            "server.AccountMerge": before["server.AccountMerge"] + 1,
            "server.EmailAlias": before["server.EmailAlias"] + 1,
        }
        self.assertEqual(after, expected)

    def test_rows_now_belong_to_the_primary(self) -> None:
        self.populate(self.primary, self.primary_player, "a")
        self.populate(self.duplicate, self.duplicate_player, "b")

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.assertEqual(MatchScore.objects.filter(entered_by=self.primary_player).count(), 2)
        self.assertEqual(ChatSession.objects.filter(user=self.primary).count(), 2)
        self.assertEqual(Ticket.objects.filter(created_by=self.primary).count(), 2)
        self.assertEqual(TicketMessage.objects.filter(sender=self.primary).count(), 2)
        self.assertEqual(PlayerWrapped.objects.filter(player=self.primary_player).count(), 1)
        self.assertEqual(self.primary_player.teams.count(), 2)
        self.assertEqual(self.primary.admin_teams.count(), 2)
        self.assertEqual(Tournament.objects.filter(volunteers=self.primary).count(), 1)
        self.assertEqual(
            ServiceRequest.objects.filter(service_players=self.primary_player).count(), 2
        )
        self.assertEqual(ManualTransaction.objects.filter(players=self.primary_player).count(), 2)

    def test_nothing_references_the_deleted_account(self) -> None:
        self.populate(self.duplicate, self.duplicate_player, "b")
        merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.assertFalse(User.objects.filter(pk=self.duplicate.pk).exists())


class TestMergeMechanics(MergeTestCase):
    def test_player_moves_when_the_primary_has_none(self) -> None:
        # The account someone can sign in to is often the emptier one.
        self.primary_player.delete()
        self.populate(self.duplicate, self.duplicate_player, "b")

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        player = Player.objects.get(user=self.primary)
        self.assertEqual(player.pk, self.duplicate_player.pk)
        self.assertEqual(PlayerWrapped.objects.filter(player=player).count(), 1)

    def test_the_better_membership_survives(self) -> None:
        Membership.objects.create(
            player=self.primary_player,
            membership_number="OLD",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
            is_active=False,
        )
        Membership.objects.create(
            player=self.duplicate_player,
            membership_number="CURRENT",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            is_active=True,
        )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        membership = Membership.objects.get(player=self.primary_player)
        self.assertEqual(membership.membership_number, "CURRENT")
        self.assertEqual(Membership.objects.count(), 1)

    def test_a_unique_together_collision_keeps_the_primary_row(self) -> None:
        Registration.objects.create(
            event=self.event, player=self.primary_player, team=Team.objects.create(name="A")
        )
        Registration.objects.create(
            event=self.event, player=self.duplicate_player, team=Team.objects.create(name="B")
        )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        registration = Registration.objects.get()
        self.assertEqual(registration.player, self.primary_player)
        self.assertEqual(registration.team.name, "A")

        # The row that lost is recoverable rather than merely gone.
        models = {row["model"] for row in AccountMerge.objects.get().snapshot}
        self.assertIn("server.registration", models)

    def test_the_snapshot_says_whose_the_destroyed_row_was(self) -> None:
        """The row is repointed in memory before the save that fails, and
        that mutation used to reach the archive - so the one record of a
        destroyed row named the survivor, the single account it did not
        belong to, and restoring it would have put it on the wrong person."""
        Registration.objects.create(
            event=self.event, player=self.primary_player, team=Team.objects.create(name="A")
        )
        Registration.objects.create(
            event=self.event, player=self.duplicate_player, team=Team.objects.create(name="B")
        )
        absorbed_player_id = self.duplicate_player.id

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        lost = next(
            row
            for row in AccountMerge.objects.get().snapshot
            if row["model"] == "server.registration"
        )
        self.assertEqual(lost["fields"]["player"], absorbed_player_id)

    def test_the_merge_locks_the_accounts_it_is_dismantling(self) -> None:
        """Asserts the lock is asked for, which is all a SQLite test can do:
        select_for_update emits nothing there. Production is Postgres, where
        without it two merges sharing an account can each cascade away rows
        the other has just moved, and both report success."""
        locked = []
        unlocked = QuerySet.select_for_update

        def spy(queryset: QuerySet[Any], *args: Any, **kwargs: Any) -> QuerySet[Any]:
            locked.append(queryset.model)
            return unlocked(queryset, *args, **kwargs)

        with mock.patch.object(QuerySet, "select_for_update", spy):
            merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.assertIn(User, locked)

    def test_sponsorship_survives_from_either_side(self) -> None:
        """An admin granted it. Whichever account the person signs in to, a
        merge must not take it away."""
        self.duplicate_player.sponsored = True
        self.duplicate_player.save()
        self.assertFalse(self.primary_player.sponsored)

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.primary_player.refresh_from_db()
        self.assertTrue(self.primary_player.sponsored)

    def test_sponsorship_on_the_kept_account_is_left_alone(self) -> None:
        self.primary_player.sponsored = True
        self.primary_player.save()

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.primary_player.refresh_from_db()
        self.assertTrue(self.primary_player.sponsored)

    def test_neither_sponsored_stays_unsponsored(self) -> None:
        merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.primary_player.refresh_from_db()
        self.assertFalse(self.primary_player.sponsored)

    def test_the_review_step_cannot_grant_sponsorship(self) -> None:
        with self.assertRaises(MergeFieldError):
            merge_accounts(
                self.primary, [self.duplicate], resolved={"sponsored": True}, dry_run=False
            )
        self.primary_player.refresh_from_db()
        self.assertFalse(self.primary_player.sponsored)

    def test_blank_fields_are_filled_from_the_duplicate(self) -> None:
        self.primary.phone = ""
        self.primary.save()
        self.duplicate.phone = "9876543210"
        self.duplicate.save()

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.primary.refresh_from_db()
        self.assertEqual(self.primary.phone, "9876543210")

    def test_a_password_change_after_load_survives_the_merge(self) -> None:
        """merge_accounts is handed request.user - loaded by auth middleware
        before the row lock. _fill_blanks used to end in a bare save(), which
        writes back every column as that stale instance held it, reverting
        anything changed in the database after it was loaded."""
        stale_primary = User.objects.get(pk=self.primary.pk)
        self.primary.set_password("new-password")
        self.primary.save()
        changed_hash = self.primary.password

        merge_accounts(stale_primary, [self.duplicate], dry_run=False)

        self.primary.refresh_from_db()
        self.assertEqual(self.primary.password, changed_hash)

    def test_the_absorbed_address_becomes_an_alias(self) -> None:
        merge_accounts(self.primary, [self.duplicate], dry_run=False)
        alias = EmailAlias.objects.get(email="dup@x.com")
        self.assertEqual(alias.user, self.primary)

    def test_the_snapshot_keeps_no_password(self) -> None:
        """Deleting the account has to take its credential with it, and the
        snapshot outlives the row."""
        self.duplicate.set_password("hunter2")
        self.duplicate.save()

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        users = [
            row for row in AccountMerge.objects.get().snapshot if row["model"] == "server.user"
        ]
        self.assertTrue(users)
        for row in users:
            self.assertNotIn("password", row["fields"])
        self.assertIn("email", users[0]["fields"])

    def test_the_merge_is_recorded(self) -> None:
        self.populate(self.duplicate, self.duplicate_player, "b")
        duplicate_id = self.duplicate.id
        merge_accounts(self.primary, [self.duplicate], matched_by="name+dob", dry_run=False)

        merge = AccountMerge.objects.get()
        self.assertEqual(merge.primary_user, self.primary)
        self.assertEqual(merge.duplicate_user_ids, [duplicate_id])
        self.assertEqual(merge.duplicate_emails, ["dup@x.com"])
        self.assertEqual(merge.matched_by, "name+dob")
        self.assertTrue(merge.snapshot)

    def test_merging_three_accounts_at_once(self) -> None:
        third = self.make_user("third@x.com")
        create_player(third)
        merge_accounts(self.primary, [self.duplicate, third], dry_run=False)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Player.objects.count(), 1)


class TestMergeRefuses(MergeTestCase):
    def test_a_guardianship_edge_blocks_the_merge(self) -> None:
        Guardianship.objects.create(
            user=self.primary, player=self.duplicate_player, relation=Guardianship.Relation.FA
        )
        with self.assertRaises(MergeBlockedError) as caught:
            merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.assertIn("guardianship", caught.exception.args[0])
        self.assertEqual(User.objects.count(), 2)

    def test_two_wards_of_one_guardian_are_refused(self) -> None:
        """Twins reach a cluster through the parent's phone, not by being one
        person. The guardian is not one of the accounts, so the edge above
        cannot see them."""
        parent = User.objects.create(username="mum@x.com", email="mum@x.com", first_name="Meera")
        self.duplicate.first_name = "Aryan"
        self.duplicate.save()
        self.primary.first_name = "Arjun"
        self.primary.save()
        for player in (self.primary_player, self.duplicate_player):
            Guardianship.objects.create(
                user=parent, player=player, relation=Guardianship.Relation.MO
            )

        with self.assertRaises(MergeBlockedError) as caught:
            merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.assertIn("different-wards", caught.exception.args[0])
        self.assertEqual(User.objects.filter(id=self.duplicate.id).count(), 1)

    def test_one_child_registered_twice_is_allowed(self) -> None:
        parent = User.objects.create(username="dad@x.com", email="dad@x.com", first_name="Vikram")
        for player in (self.primary_player, self.duplicate_player):
            Guardianship.objects.create(
                user=parent, player=player, relation=Guardianship.Relation.FA
            )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.assertEqual(User.objects.filter(id=self.duplicate.id).count(), 0)

    def test_differently_named_accounts_are_refused(self) -> None:
        """A shared inbox or phone is not evidence of one person, and a merge
        by hand names no rule, so it has to clear the same bar."""
        self.duplicate.first_name = "Kavya"
        self.duplicate.last_name = "Iyer"
        self.duplicate.save()

        with self.assertRaises(MergeBlockedError) as caught:
            merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.assertIn("name-mismatch", caught.exception.args[0])
        self.assertEqual(User.objects.filter(id=self.duplicate.id).count(), 1)

    def test_a_name_rule_on_the_cluster_does_not_excuse_it(self) -> None:
        """A cluster is a chain, so one matching pair anywhere used to make the
        whole thing look name-matched. The names themselves decide."""
        self.duplicate.first_name = "Kavya"
        self.duplicate.last_name = "Iyer"
        self.duplicate.save()

        with self.assertRaises(MergeBlockedError) as caught:
            merge_accounts(
                self.primary, [self.duplicate], matched_by="name+dob email", dry_run=False
            )
        self.assertIn("name-mismatch", caught.exception.args[0])
        self.assertEqual(User.objects.filter(id=self.duplicate.id).count(), 1)

    def test_an_account_with_no_name_is_not_a_mismatch(self) -> None:
        blank = User.objects.create(username="blank@x.com", email="blank@x.com")
        merge_accounts(blank, [self.duplicate], dry_run=False)
        self.assertEqual(User.objects.filter(id=self.duplicate.id).count(), 0)

    def test_two_guardians_for_one_child_are_refused(self) -> None:
        mother = User.objects.create(username="mum@x.com", email="mum@x.com")
        father = User.objects.create(username="dad@x.com", email="dad@x.com")
        Guardianship.objects.create(
            user=mother, player=self.primary_player, relation=Guardianship.Relation.MO
        )
        Guardianship.objects.create(
            user=father, player=self.duplicate_player, relation=Guardianship.Relation.FA
        )

        with self.assertRaises(MergeBlockedError) as caught:
            merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.assertIn("different-guardians", caught.exception.args[0])
        self.assertEqual(User.objects.filter(id=self.duplicate.id).count(), 1)

    def test_one_guardian_on_both_sides_still_merges(self) -> None:
        mother = User.objects.create(username="mum2@x.com", email="mum2@x.com")
        for player in (self.primary_player, self.duplicate_player):
            Guardianship.objects.create(
                user=mother, player=player, relation=Guardianship.Relation.MO
            )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.assertEqual(User.objects.filter(id=self.duplicate.id).count(), 0)
        # The child merged their own accounts; their mother must not notice.
        self.assertEqual(Guardianship.objects.get(user=mother).player, self.primary_player)

    def test_a_guardian_on_the_absorbed_side_follows_the_child(self) -> None:
        mother = User.objects.create(username="mum3@x.com", email="mum3@x.com")
        Guardianship.objects.create(
            user=mother, player=self.duplicate_player, relation=Guardianship.Relation.MO
        )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        guardianship = Guardianship.objects.get(user=mother)
        self.assertEqual(guardianship.player, self.primary_player)
        self.assertEqual(guardianship.relation, Guardianship.Relation.MO)

    def test_a_given_name_one_letter_off_cannot_be_merged(self) -> None:
        """Arun and Tarun score 97 as whole names. The engine checks names
        itself, so reaching it some other way must still be refused."""
        User.objects.filter(id=self.primary.id).update(first_name="Arun", last_name="Venkatesan")
        User.objects.filter(id=self.duplicate.id).update(first_name="Tarun", last_name="Venkatesan")
        self.primary.refresh_from_db()
        self.duplicate.refresh_from_db()

        with self.assertRaises(MergeBlockedError) as caught:
            merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.assertIn("name-mismatch", caught.exception.args[0])

    def test_a_different_gender_cannot_be_merged(self) -> None:
        Player.objects.filter(id=self.primary_player.id).update(gender=Player.GenderTypes.MALE)
        Player.objects.filter(id=self.duplicate_player.id).update(gender=Player.GenderTypes.FEMALE)

        with self.assertRaises(MergeBlockedError) as caught:
            merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.assertIn("different-gender", caught.exception.args[0])

    def test_merging_an_account_into_itself_is_refused(self) -> None:
        with self.assertRaises(MergeBlockedError):
            merge_accounts(self.primary, [self.primary], dry_run=False)

    def test_the_survivor_keeps_the_profile_of_an_emptier_account(self) -> None:
        """Signing in to the account with nothing on it is common. The player
        moves across rather than cascading away with the deleted row."""
        blank = User.objects.create(username="blank@x.com", email="blank@x.com")
        self.populate(self.duplicate, self.duplicate_player, "b")

        merge_accounts(blank, [self.duplicate], dry_run=False)

        blank.refresh_from_db()
        self.assertEqual(Player.objects.filter(user=blank).count(), 1)
        self.assertEqual(blank.get_full_name(), "Rahul Sharma")

    def test_the_survivor_keeps_exactly_one_player(self) -> None:
        merge_accounts(self.primary, [self.duplicate], dry_run=False)
        self.assertEqual(Player.objects.filter(user=self.primary).count(), 1)

    def test_a_lost_player_rolls_the_merge_back(self) -> None:
        """Stand in for a regression that drops the profile instead of moving
        it. Nothing may be committed when the survivor comes out without one."""
        blank = User.objects.create(username="blank2@x.com", email="blank2@x.com")
        before = row_counts()

        with (
            self.assertRaises(MergeIncompleteError),
            mock.patch.object(Player, "save", lambda *a, **k: None),
        ):
            merge_accounts(blank, [self.duplicate], dry_run=False)

        self.assertEqual(row_counts(), before)

    def test_a_dangling_reference_rolls_the_merge_back(self) -> None:
        self.populate(self.duplicate, self.duplicate_player, "b")
        before = row_counts()

        # Stand in for a relation the walk failed to move.
        def leave_a_row_behind(users: list[User]) -> dict[str, int]:
            return {"server.Pretend.user": 1}

        with self.settings():
            import server.duplicates.merge as merge_module

            original = merge_module.find_references
            merge_module.find_references = leave_a_row_behind
            try:
                with self.assertRaises(MergeIncompleteError):
                    merge_accounts(self.primary, [self.duplicate], dry_run=False)
            finally:
                merge_module.find_references = original

        self.assertEqual(row_counts(), before)


class TestCollisionsKeepTheBetterRow(MergeTestCase):
    """A unique_together clash used to keep the primary's row whatever it held."""

    def test_the_row_that_voted_survives(self) -> None:
        from server.election.models import Election, VoterVerification

        election = Election.objects.create(
            title="AGM",
            description="d",
            start_date=now(),
            end_date=now() + datetime.timedelta(days=30),
            num_winners=1,
        )
        VoterVerification.objects.create(
            election=election,
            user=self.primary,
            verification_token="a",  # noqa: S106
            is_used=False,
        )
        VoterVerification.objects.create(
            election=election,
            user=self.duplicate,
            verification_token="b",  # noqa: S106
            is_used=True,
        )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        surviving = VoterVerification.objects.get(election=election, user=self.primary)
        self.assertTrue(surviving.is_used, "the unused row won, so the merge can vote twice")

    def test_the_registration_that_is_playing_survives(self) -> None:
        team = Team.objects.create(name="T")
        Registration.objects.create(
            event=self.event, team=team, player=self.primary_player, is_playing=False
        )
        Registration.objects.create(
            event=self.event,
            team=team,
            player=self.duplicate_player,
            is_playing=True,
            points=42,
        )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        surviving = Registration.objects.get(event=self.event, player=self.primary_player)
        self.assertTrue(surviving.is_playing)
        self.assertEqual(surviving.points, 42)

    def test_the_loser_is_still_in_the_snapshot(self) -> None:
        team = Team.objects.create(name="T")
        Registration.objects.create(
            event=self.event, team=team, player=self.primary_player, is_playing=False
        )
        Registration.objects.create(
            event=self.event, team=team, player=self.duplicate_player, is_playing=True
        )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        models = {row["model"] for row in AccountMerge.objects.get().snapshot}
        self.assertIn("server.registration", models)


class TestCommentaryKeepsTheFullerRow(MergeTestCase):
    def test_the_row_with_more_answers_survives(self) -> None:
        """Seven free-text answers the person wrote. A sparse surviving row
        used to beat a complete absorbed one and throw the lot away."""
        CommentaryInfo.objects.create(player=self.primary_player, jersey_number=7)
        CommentaryInfo.objects.create(
            player=self.duplicate_player,
            jersey_number=9,
            ultimate_origin="a friend",
            ultimate_attraction="the spirit",
            ultimate_fav_role="handler",
            ultimate_fav_exp="nationals",
            interests="music",
            fun_fact="once threw 80m",
        )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        surviving = CommentaryInfo.objects.get(player=self.primary_player)
        self.assertEqual(surviving.fun_fact, "once threw 80m")
        self.assertEqual(surviving.jersey_number, 9)

    def test_the_fuller_row_on_the_kept_account_stays(self) -> None:
        CommentaryInfo.objects.create(
            player=self.primary_player, jersey_number=7, fun_fact="keeps this"
        )
        CommentaryInfo.objects.create(player=self.duplicate_player, jersey_number=9)

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.assertEqual(
            CommentaryInfo.objects.get(player=self.primary_player).fun_fact, "keeps this"
        )


class TestTheAddressIsNotCopied(MergeTestCase):
    def test_a_blank_primary_keeps_its_blank_address(self) -> None:
        """Writing email without username would strand the account: sign in
        resolves on username. The address becomes an alias instead."""
        blank = User.objects.create(username="blank-slug", email="")

        merge_accounts(blank, [self.duplicate], dry_run=False)

        blank.refresh_from_db()
        self.assertEqual(blank.email, "")
        self.assertEqual(blank.username, "blank-slug")
        self.assertEqual(EmailAlias.objects.get(email="dup@x.com").user_id, blank.id)

    def test_the_absorbed_address_still_signs_in(self) -> None:
        from server.core.accounts import resolve_login_user

        blank = User.objects.create(username="blank-slug2", email="")
        merge_accounts(blank, [self.duplicate], dry_run=False)

        self.assertEqual(resolve_login_user("dup@x.com").id, blank.id)


class TestTheRecord(MergeTestCase):
    """A count cannot be undone. These are the two things nothing else holds."""

    def test_every_moved_row_is_named(self) -> None:
        self.populate(self.duplicate, self.duplicate_player, "b")

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        moves = AccountMerge.objects.get().record["moves"]
        self.assertTrue(moves)
        for entry in moves:
            if "pk" in entry:  # a row that was repointed
                self.assertEqual(set(entry), {"model", "pk", "field", "was", "now"})
                self.assertIsNotNone(entry["pk"])
            else:  # a many-to-many entry, named by the end that stayed put
                self.assertEqual(
                    set(entry), {"model", "field", "other_pk", "was", "now", "already_held"}
                )
                self.assertIsNotNone(entry["other_pk"])
        # The membership moved, and the entry says where from and where to.
        membership = next(m for m in moves if m["model"] == "server.Membership")
        self.assertEqual(membership["was"], self.duplicate_player.id)
        self.assertEqual(membership["now"], self.primary_player.id)

    def test_a_bulk_moved_relation_is_named_row_by_row(self) -> None:
        """These move in one UPDATE, so the identities have to be read first
        or they are gone."""
        ChatSession.objects.create(user=self.duplicate)
        ChatSession.objects.create(user=self.duplicate)
        absorbed_id = self.duplicate.id  # delete() nulls the instance pk

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        chats = [
            m
            for m in AccountMerge.objects.get().record["moves"]
            if m["model"] == "server.ChatSession"
        ]
        self.assertEqual(len(chats), 2)
        self.assertEqual({m["was"] for m in chats}, {absorbed_id})

    def test_an_overwritten_field_keeps_what_it_replaced(self) -> None:
        self.primary.phone = ""
        self.primary.save()
        self.duplicate.phone = "9876543210"
        self.duplicate.save()

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        overwrites = AccountMerge.objects.get().record["overwrites"]
        phone = next(o for o in overwrites if o["field"] == "phone")
        self.assertEqual(phone["was"], "")
        self.assertEqual(phone["now"], "9876543210")
        self.assertEqual(phone["pk"], self.primary.id)

    def test_a_chosen_value_records_what_it_replaced(self) -> None:
        self.primary_player.city = "Mumbai"
        self.primary_player.save()
        self.duplicate_player.city = "Chennai"
        self.duplicate_player.save()

        merge_accounts(self.primary, [self.duplicate], resolved={"city": "Chennai"}, dry_run=False)

        overwrites = AccountMerge.objects.get().record["overwrites"]
        city = next(o for o in overwrites if o["field"] == "city")
        self.assertEqual(city["now"], "Chennai")

    def test_the_record_has_every_section(self) -> None:
        self.populate(self.duplicate, self.duplicate_player, "b")
        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        stored = AccountMerge.objects.get().record
        # json.dumps on a value read back from the database proves nothing:
        # it is already JSON or the write would have failed. The value that
        # could not be encoded is covered below, by merging a row that has
        # one, which is the check this test used to claim to be.
        json.dumps(stored)
        self.assertEqual(set(stored), {"moves", "overwrites", "deleted", "aliases", "proof"})

    def test_an_account_that_has_paid_can_still_be_merged(self) -> None:
        """PhonePeTransaction is keyed by a UUID rather than an int, and one
        reaching the JSONField raw aborted the whole merge - for a quarter of
        the groups in production, because paying members are exactly who has
        two accounts."""
        transaction_id = uuid.uuid4()
        PhonePeTransaction.objects.create(
            transaction_id=transaction_id, amount=70000, currency="INR", user=self.duplicate
        )

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.assertEqual(PhonePeTransaction.objects.get().user, self.primary)
        moved = next(
            entry
            for entry in AccountMerge.objects.get().record["moves"]
            if entry["model"] == "server.PhonePeTransaction"
        )
        self.assertEqual(moved["pk"], str(transaction_id))

    def test_a_team_membership_moves_with_a_record_of_it(self) -> None:
        """teams belongs to the player row being deleted, and the snapshot is
        taken after that delete, so it reads back empty. If the move is not
        recorded here nothing anywhere says this player was on the team."""
        team = Team.objects.create(name="Tigers")
        self.duplicate_player.teams.add(team)
        absorbed_player_id = self.duplicate_player.id

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.assertIn(team, self.primary_player.teams.all())
        entry = next(
            move
            for move in AccountMerge.objects.get().record["moves"]
            if move.get("field") == "teams"
        )
        self.assertEqual(entry["other_pk"], team.id)
        self.assertEqual(entry["was"], absorbed_player_id)
        self.assertEqual(entry["now"], self.primary_player.id)
        self.assertFalse(entry["already_held"])

    def test_a_team_they_were_both_on_is_recorded_as_a_removal(self) -> None:
        """Adding the survivor changes nothing, so the entry only leaves the
        absorbed side. Replayed as a move it would take the survivor off a
        team it was on before the merge."""
        team = Team.objects.create(name="Tigers")
        self.primary_player.teams.add(team)
        self.duplicate_player.teams.add(team)

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        entry = next(
            move
            for move in AccountMerge.objects.get().record["moves"]
            if move.get("field") == "teams" and move["other_pk"] == team.id
        )
        self.assertTrue(entry["already_held"])

    def test_the_record_says_what_was_deleted_and_why(self) -> None:
        Registration.objects.create(
            event=self.event, player=self.primary_player, team=Team.objects.create(name="A")
        )
        Registration.objects.create(
            event=self.event, player=self.duplicate_player, team=Team.objects.create(name="B")
        )
        absorbed_id = self.duplicate.id  # delete() nulls the instance pk

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        deleted = AccountMerge.objects.get().record["deleted"]
        reasons = {(row["model"], row["reason"]) for row in deleted}
        self.assertIn(("server.User", "explicit"), reasons)
        self.assertIn(("server.Player", "explicit"), reasons)
        self.assertIn(("server.Registration", "unique-clash"), reasons)
        self.assertIn(absorbed_id, [row["pk"] for row in deleted])

    def test_an_address_taken_off_another_account_is_recorded(self) -> None:
        """An absorbed address can already be somebody else's alias, and
        repointing it takes away their way of signing in. Whether that should
        be allowed is another question; it may not happen unnoticed."""
        other = self.make_user("other@x.com")
        EmailAlias.objects.create(email="dup@x.com", user=other)

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        alias = next(
            entry
            for entry in AccountMerge.objects.get().record["aliases"]
            if entry["email"] == "dup@x.com"
        )
        self.assertEqual(alias["user_id"], self.primary.id)
        self.assertEqual(alias["replaced_user_id"], other.id)

    def test_a_blank_answer_cannot_erase_a_recovered_detail(self) -> None:
        """The merge recovers state_ut from the duplicate; a blank arriving
        from a client that did not filter it would write over it again, and
        full_clean only catches that on required fields."""
        self.primary_player.state_ut = ""
        self.primary_player.save()
        self.duplicate_player.state_ut = "KA"
        self.duplicate_player.save()

        with self.assertRaises(MergeFieldError):
            merge_accounts(
                self.primary, [self.duplicate], resolved={"state_ut": None}, dry_run=False
            )

        self.assertTrue(User.objects.filter(id=self.duplicate.id).exists())

    def test_a_dry_run_records_nothing(self) -> None:
        merge_accounts(self.primary, [self.duplicate], dry_run=True)
        self.assertEqual(AccountMerge.objects.count(), 0)


class TestMergePlan(MergeTestCase):
    def test_a_dry_run_writes_nothing(self) -> None:
        self.populate(self.duplicate, self.duplicate_player, "b")
        before = row_counts()

        plan = merge_accounts(self.primary, [self.duplicate])

        self.assertEqual(row_counts(), before)
        self.assertGreater(plan.rows_moved, 0)

    def test_the_plan_names_what_would_move(self) -> None:
        ChatSession.objects.create(user=self.duplicate)
        plan = build_plan(self.primary, [self.duplicate])
        labels = {move.label: move.moved for move in plan.moves}
        self.assertEqual(labels["server.ChatSession.user"], 1)

    def test_the_plan_counts_what_would_be_destroyed(self) -> None:
        """The one thing a dry run exists to tell you, which it used to
        report as zero whatever the merge was about to delete."""
        team = Team.objects.create(name="T")
        Registration.objects.create(
            event=self.event, team=team, player=self.primary_player, is_playing=False
        )
        Registration.objects.create(
            event=self.event, team=team, player=self.duplicate_player, is_playing=True
        )

        plan = merge_accounts(self.primary, [self.duplicate], dry_run=True)

        move = next(m for m in plan.moves if m.label == "server.Registration.player")
        self.assertEqual(move.collided, 1)
        # The duplicate's row is playing, so the primary's is the one dropped.
        self.assertEqual(move.primary_loses, 1)

    def test_the_plan_says_nothing_clashes_when_nothing_does(self) -> None:
        team = Team.objects.create(name="T")
        Registration.objects.create(
            event=self.event, team=team, player=self.duplicate_player, is_playing=True
        )

        plan = merge_accounts(self.primary, [self.duplicate], dry_run=True)

        move = next(m for m in plan.moves if m.label == "server.Registration.player")
        self.assertEqual((move.moved, move.collided), (1, 0))

    def test_a_dry_run_that_counts_clashes_still_writes_nothing(self) -> None:
        team = Team.objects.create(name="T")
        Registration.objects.create(
            event=self.event, team=team, player=self.primary_player, is_playing=False
        )
        Registration.objects.create(
            event=self.event, team=team, player=self.duplicate_player, is_playing=True
        )
        before = row_counts()

        merge_accounts(self.primary, [self.duplicate], dry_run=True)

        self.assertEqual(row_counts(), before)

    def test_find_references_sees_rows_before_a_merge(self) -> None:
        ChatSession.objects.create(user=self.duplicate)
        self.assertIn("server.ChatSession.user", find_references([self.duplicate]))


class TestResolvedFields(MergeTestCase):
    """The review step: the person picks which details survive."""

    def test_a_chosen_value_beats_what_the_merge_worked_out(self) -> None:
        self.primary.phone = "1111111111"
        self.primary.save()
        self.duplicate.phone = "9876543210"
        self.duplicate.save()

        merge_accounts(
            self.primary,
            [self.duplicate],
            resolved={"phone": "9876543210"},
            dry_run=False,
        )

        self.primary.refresh_from_db()
        self.assertEqual(self.primary.phone, "9876543210")

    def test_a_value_belonging_to_neither_account_is_refused(self) -> None:
        """The radio buttons only ever offer the two accounts' own values;
        a raw API call must not be able to smuggle a third value past
        them - the review step is a choice, not a free-text edit."""
        with self.assertRaises(MergeFieldError):
            merge_accounts(
                self.primary, [self.duplicate], resolved={"last_name": "Verma"}, dry_run=False
            )
        self.primary.refresh_from_db()
        self.assertEqual(self.primary.last_name, "Sharma")

    def test_a_player_field_is_written_to_the_surviving_profile(self) -> None:
        self.duplicate_player.city = "Bengaluru"
        self.duplicate_player.date_of_birth = datetime.date(1995, 6, 15)
        self.duplicate_player.save()

        merge_accounts(
            self.primary,
            [self.duplicate],
            resolved={"city": "Bengaluru", "date_of_birth": "1995-06-15"},
            dry_run=False,
        )
        player = Player.objects.get(user=self.primary)
        self.assertEqual(player.city, "Bengaluru")
        self.assertEqual(player.date_of_birth, datetime.date(1995, 6, 15))

    def test_a_field_outside_the_form_is_refused(self) -> None:
        with self.assertRaises(MergeFieldError):
            merge_accounts(
                self.primary, [self.duplicate], resolved={"is_staff": True}, dry_run=False
            )
        self.assertEqual(User.objects.count(), 2)

    def test_the_address_cannot_be_edited_here(self) -> None:
        # username is the address and sign in resolves on it.
        with self.assertRaises(MergeFieldError):
            merge_accounts(
                self.primary,
                [self.duplicate],
                resolved={"email": "someone@else.com"},
                dry_run=False,
            )

    def test_an_invalid_value_rolls_the_whole_merge_back(self) -> None:
        before = row_counts()
        with self.assertRaises(MergeFieldError):
            merge_accounts(
                self.primary,
                [self.duplicate],
                resolved={"date_of_birth": "not-a-date"},
                dry_run=False,
            )
        self.assertEqual(row_counts(), before)

    def test_an_otp_created_account_can_still_be_resolved(self) -> None:
        """Only the fields being set are validated. Signing in by OTP leaves
        password blank, which a whole-model clean rejects - and that is every
        account this campaign writes to. Resolves on phone, not a name field:
        the blank account's empty name is what keeps it clear of the merge's
        own name-mismatch blocker, and both accounts are given a non-blank,
        differing phone so only the resolved choice, not _fill_blanks, can
        produce the asserted value."""
        blank = User.objects.create(username="otp@x.com", email="otp@x.com", phone="1112223333")
        self.assertEqual(blank.password, "")
        self.duplicate.phone = "9998887777"
        self.duplicate.save()

        merge_accounts(blank, [self.duplicate], resolved={"phone": "9998887777"}, dry_run=False)

        blank.refresh_from_db()
        self.assertEqual(blank.phone, "9998887777")


class TestUniqueFieldsAreFilledSafely(MergeTestCase):
    def test_ultimate_central_id_moves_to_a_primary_without_one(self) -> None:
        self.duplicate_player.ultimate_central_id = 4242
        self.duplicate_player.save()

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.primary_player.refresh_from_db()
        self.assertEqual(self.primary_player.ultimate_central_id, 4242)

    def test_the_primary_keeps_its_own_ultimate_central_id(self) -> None:
        self.primary_player.ultimate_central_id = 1111
        self.primary_player.save()

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.primary_player.refresh_from_db()
        self.assertEqual(self.primary_player.ultimate_central_id, 1111)

    def test_conflicting_ultimate_central_ids_merge_and_archive_the_loser(self) -> None:
        """Ultimate Central is retired, so a clash no longer blocks. The id is
        unique, so the absorbed row must be gone before the fill."""
        self.primary_player.ultimate_central_id = 4242
        self.primary_player.save()
        self.duplicate_player.ultimate_central_id = 9999
        self.duplicate_player.save()

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        self.primary_player.refresh_from_db()
        self.assertEqual(self.primary_player.ultimate_central_id, 4242)
        archived = [
            row["fields"]["ultimate_central_id"]
            for row in AccountMerge.objects.get().snapshot
            if row["model"] == "server.player"
        ]
        self.assertIn(9999, archived)


class TestGroupHistory(MergeTestCase):
    """A merge must never rewrite the group it came from."""

    def setUp(self) -> None:
        super().setUp()
        self.cluster = DuplicateCluster.objects.create()
        for user in (self.primary, self.duplicate):
            ClusterMember.of(self.cluster, user).save()

    def test_the_absorbed_row_stays_in_its_group_marked_merged(self) -> None:
        absorbed_id = self.duplicate.id
        merge_accounts(self.primary, [self.duplicate], dry_run=False, cluster=self.cluster)

        row = ClusterMember.objects.get(cluster=self.cluster, account_id=absorbed_id)
        self.assertEqual(row.state, ClusterMember.State.MERGED)
        self.assertIsNone(row.user_id)
        self.assertEqual(row.account_email, "dup@x.com")
        self.assertEqual(row.merged_into_id, self.primary.id)
        self.assertEqual(row.merge, AccountMerge.objects.get())
        self.assertEqual(self.cluster.members.count(), 2)
        self.assertTrue(
            self.cluster.events.filter(kind=ClusterEvent.Kind.MERGED, member=row).exists()
        )

    def test_its_rows_in_other_groups_survive(self) -> None:
        other = DuplicateCluster.objects.create(status=DuplicateCluster.Status.DISMISSED)
        ClusterMember.of(other, self.duplicate).save()
        absorbed_id = self.duplicate.id

        merge_accounts(self.primary, [self.duplicate], dry_run=False, cluster=self.cluster)

        row = ClusterMember.objects.get(cluster=other, account_id=absorbed_id)
        self.assertEqual(row.state, ClusterMember.State.MERGED_ELSEWHERE)
        self.assertIsNone(row.user_id)
        self.assertTrue(
            other.events.filter(kind=ClusterEvent.Kind.MERGED_ELSEWHERE, member=row).exists()
        )

    def test_the_merge_names_its_group_keeper_and_proof(self) -> None:
        merge_accounts(
            self.primary,
            [self.duplicate],
            dry_run=False,
            cluster=self.cluster,
            proof={"method": "email-code"},
        )
        merge = AccountMerge.objects.get()
        self.assertEqual(merge.cluster, self.cluster)
        self.assertEqual(merge.primary_id, self.primary.id)
        self.assertEqual(merge.primary_email, "primary@x.com")
        self.assertEqual(merge.record["proof"], {"method": "email-code"})

    def test_a_group_with_a_merge_cannot_be_deleted(self) -> None:
        merge_accounts(self.primary, [self.duplicate], dry_run=False, cluster=self.cluster)
        ClusterEvent.objects.all().delete()
        with self.assertRaises(ProtectedError):
            self.cluster.delete()

    def test_a_verification_for_an_absorbed_keeper_resets(self) -> None:
        third = self.make_user("third@x.com")
        create_player(third)
        row = ClusterMember.of(self.cluster, third)
        row.state = ClusterMember.State.VERIFIED
        row.verified_by_id = self.duplicate.id
        row.proof = ClusterMember.Proof.EMAIL_CODE
        row.save()

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        row.refresh_from_db()
        self.assertEqual(row.state, ClusterMember.State.OPEN)
        self.assertIsNone(row.verified_by_id)
        self.assertTrue(
            self.cluster.events.filter(kind=ClusterEvent.Kind.KEEPER_MOVED, member=row).exists()
        )

    def test_a_staff_request_from_an_absorbed_keeper_closes_quietly(self) -> None:
        third = self.make_user("third@x.com")
        create_player(third)
        request = ServiceRequest.objects.create(
            user=self.duplicate, type=ServiceRequestType.REQUEST_ACCOUNT_MERGE, message="old"
        )
        row = ClusterMember.of(self.cluster, third)
        row.state = ClusterMember.State.PENDING_STAFF
        row.staff_request = request
        row.save()

        merge_accounts(self.primary, [self.duplicate], dry_run=False)

        request.refresh_from_db()
        row.refresh_from_db()
        self.assertEqual(request.status, ServiceRequestStatus.REJECTED)
        self.assertEqual(row.state, ClusterMember.State.OPEN)
        self.assertEqual(len(mail.outbox), 0)  # the approval signal skips this type

    def test_an_event_keeps_its_actor_after_the_actor_is_merged_away(self) -> None:
        log(self.cluster, ClusterEvent.Kind.CODE_SENT, actor=self.duplicate)
        absorbed_id = self.duplicate.id

        merge_accounts(self.primary, [self.duplicate], dry_run=False, cluster=self.cluster)

        event = self.cluster.events.get(kind=ClusterEvent.Kind.CODE_SENT)
        self.assertEqual(event.actor_id, absorbed_id)
        self.assertEqual(event.actor_email, "dup@x.com")
