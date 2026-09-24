import datetime
import json
import re
import threading
import time
from collections.abc import Callable
from io import StringIO
from smtplib import SMTPException
from typing import Any
from unittest import mock, skipUnless

import pyotp
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.management import call_command
from django.db import connection, connections
from django.db.models import F, ProtectedError
from django.test import TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils.timezone import now

from server.api import get_email_hash
from server.core.accounts import find_login_user, resolve_login_user
from server.core.models import Guardianship, Player, User
from server.duplicates import flow
from server.duplicates.clusters import (
    _dismissed_groups,
    close_finished,
    create_clusters,
    detect_and_create,
)
from server.duplicates.codes import MAX_CODES_PER_ACTOR_PER_DAY, MAX_CODES_PER_DAY, RESEND_AFTER
from server.duplicates.detect import find_clusters
from server.duplicates.emails import MERGED_SUBJECT, notify
from server.duplicates.flow import (
    MAX_REQUESTS_PER_DAY,
    FlowError,
    approve_staff,
    dismiss,
    merge_pair,
    reject_staff,
    request_staff,
    verify_same_inbox,
)
from server.duplicates.history import log
from server.duplicates.identity import mask_email
from server.duplicates.merge import MergeBlockedError, merge_accounts, resolvable_fields
from server.duplicates.models import (
    AccountMerge,
    ClusterEvent,
    ClusterMember,
    DuplicateCluster,
    EmailAlias,
)
from server.schema import UserFormSchema
from server.servicerequests.models import ServiceRequest, ServiceRequestStatus, ServiceRequestType
from server.task.models import Task

BASE = "/api/merge-accounts"


class MergeFlowTestCase(TestCase):
    def make_account(
        self, username: str, first: str = "Rahul", last: str = "Sharma", **kwargs: Any
    ) -> User:
        user = User.objects.create(
            username=username, email=username, first_name=first, last_name=last, **kwargs
        )
        Player.objects.create(
            user=user,
            date_of_birth=datetime.date(1995, 6, 15),
            gender=Player.GenderTypes.MALE,
            match_up=Player.MatchupTypes.MALE,
            city="Bengaluru",
        )
        return user

    def setUp(self) -> None:
        self.first = self.make_account("first@x.com", last_login=now())
        self.second = self.make_account("second@x.com")
        self.cluster = detect_and_create()[0]
        self.token = ClusterMember.objects.get(cluster=self.cluster, user=self.first).claim_token

    def confirm(self, token: str, absorb: int, resolved: dict[str, Any] | None = None) -> Any:
        # merge_pair emails only on_commit, which a plain TestCase never
        # reaches on its own (the outer transaction is rolled back, not
        # committed) — capture and run those callbacks so the emailing
        # tests can see them.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                f"{BASE}/{token}/confirm",
                data=json.dumps({"absorb_user_id": absorb, "resolved": resolved or {}}),
                content_type="application/json",
            )

    def wait_a_minute(self) -> None:
        """As if the resend wait had passed for every code sent so far."""
        ClusterEvent.objects.update(at=F("at") - RESEND_AFTER - datetime.timedelta(seconds=1))

    def confirmed(self, keeper: User, other: User, cluster: DuplicateCluster | None = None) -> None:
        """As if `keeper` had typed the code sent to `other`."""
        ClusterMember.objects.filter(cluster=cluster or self.cluster, user=other).update(
            state=ClusterMember.State.VERIFIED,
            verified_by_id=keeper.id,
            verified_at=now(),
            proof=ClusterMember.Proof.EMAIL_CODE,
        )


class TestClusterCreation(MergeFlowTestCase):
    def test_detection_creates_one_cluster_with_both_accounts(self) -> None:
        self.assertEqual(DuplicateCluster.objects.count(), 1)
        self.assertEqual(self.cluster.members.count(), 2)
        self.assertEqual(self.cluster.status, DuplicateCluster.Status.DETECTED)

    def test_members_get_distinct_tokens(self) -> None:
        tokens = set(self.cluster.members.values_list("claim_token", flat=True))
        self.assertEqual(len(tokens), 2)

    def test_running_detection_again_does_not_duplicate_the_cluster(self) -> None:
        detect_and_create()
        self.assertEqual(DuplicateCluster.objects.count(), 1)

    def test_a_dismissed_cluster_is_not_recreated(self) -> None:
        self.cluster.status = DuplicateCluster.Status.DISMISSED
        self.cluster.save()
        detect_and_create()
        self.assertEqual(DuplicateCluster.objects.count(), 1)

    def test_blocked_clusters_are_never_saved(self) -> None:
        ClusterEvent.objects.all().delete()
        DuplicateCluster.objects.all().delete()
        Guardianship.objects.create(
            user=self.first,
            player=Player.objects.get(user=self.second),
            relation=Guardianship.Relation.FA,
        )
        create_clusters(find_clusters())
        self.assertEqual(DuplicateCluster.objects.count(), 0)

    def test_each_row_remembers_its_account_as_it_was(self) -> None:
        row = ClusterMember.objects.get(cluster=self.cluster, user=self.second)
        self.assertEqual(row.account_id, self.second.id)
        self.assertEqual(row.account_email, "second@x.com")
        self.assertEqual(row.state, ClusterMember.State.OPEN)

    def test_a_detected_group_says_so(self) -> None:
        self.assertEqual(self.cluster.origin, DuplicateCluster.Origin.DETECTED)
        self.assertIsNone(self.cluster.requested_by_id)


class TestStatusPage(MergeFlowTestCase):
    def page(self, token: str | None = None) -> Any:
        return self.client.get(f"{BASE}/{token or self.token}")

    def rows(self) -> dict[str, dict[str, Any]]:
        return {row["email"]: row for row in self.page().json()["rows"]}

    def test_signed_out_sees_statuses_with_masked_addresses(self) -> None:
        data = self.page().json()
        self.assertFalse(data["can_act"])
        emails = {row["email"] for row in data["rows"]}
        self.assertEqual(emails, {mask_email("first@x.com"), mask_email("second@x.com")})
        self.assertTrue(all(row["profile"] is None for row in data["rows"]))

    def test_a_member_sees_their_own_details_and_the_other_s_email_but_not_its_profile(
        self,
    ) -> None:
        """Any signed-in member sees every row's full address (spec §4) —
        two masked Gmail addresses can be indistinguishable — but a profile
        still needs proof, not just sign in."""
        self.client.force_login(self.first)
        rows = self.rows()
        self.assertTrue(rows["first@x.com"]["is_yours"])
        self.assertIsNotNone(rows["first@x.com"]["profile"])
        other = rows["second@x.com"]
        self.assertIsNone(other["profile"])
        self.assertEqual(other["state"], ClusterMember.State.OPEN)

    def test_an_open_row_has_no_proof_yet(self) -> None:
        self.client.force_login(self.first)
        self.assertEqual(self.rows()["second@x.com"]["proof"], "")

    def test_a_signed_out_viewer_does_not_learn_how_a_row_was_proven(self) -> None:
        """ "Same inbox" under two masked rows tells a signed-out link
        holder the two accounts share a mailbox — a row's status must
        never reveal anything personal (spec §11). Gated like the rest of
        a row's detail on viewer_id, not shown merely because the row's
        state itself is public."""
        self.confirmed(self.first, self.second)
        row = next(r for r in self.page().json()["rows"] if r["user_id"] == self.second.id)
        self.assertEqual(row["state"], ClusterMember.State.VERIFIED)
        self.assertEqual(row["proof"], "")

    def test_a_confirmed_row_says_how_it_was_confirmed(self) -> None:
        """The reason a row auto-confirmed (spec §3) needs to reach the page,
        not just the database: `confirmed()` proves by code, so the row
        must say `email-code`, not merely that it is verified."""
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        self.assertEqual(self.rows()["second@x.com"]["proof"], ClusterMember.Proof.EMAIL_CODE)

    def test_a_confirmed_account_shows_its_details(self) -> None:
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        row = self.rows()["second@x.com"]
        self.assertTrue(row["verified_for_you"])
        self.assertIsNotNone(row["profile"])

    def test_a_signed_in_outsider_sees_only_masked_rows(self) -> None:
        self.client.force_login(self.make_account("out@x.com", first="Kavya", last="Iyer"))
        data = self.page().json()
        self.assertIsNone(data["signed_in_as"])
        self.assertEqual(
            {row["email"] for row in data["rows"]},
            {mask_email("first@x.com"), mask_email("second@x.com")},
        )
        self.assertTrue(all(row["profile"] is None for row in data["rows"]))

    def test_an_expired_link_still_shows_a_member_their_table(self) -> None:
        ClusterMember.objects.filter(cluster=self.cluster).update(
            expires_at=now() - datetime.timedelta(days=1)
        )
        self.client.force_login(self.first)
        data = self.page().json()
        self.assertFalse(data["can_act"])
        self.assertEqual(len(data["rows"]), 2)

    def test_an_expired_open_link_is_not_found_signed_out(self) -> None:
        ClusterMember.objects.filter(cluster=self.cluster).update(
            expires_at=now() - datetime.timedelta(days=1)
        )
        self.assertEqual(self.page().status_code, 404)

    def test_the_keeper_still_sees_a_merged_account(self) -> None:
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        second_token = ClusterMember.objects.get(cluster=self.cluster, user=self.second).claim_token
        self.confirm(self.token, self.second.id)
        # The absorbed address now signs in to the keeper; its old link still works.
        for token in (self.token, second_token):
            rows = {row["email"]: row for row in self.page(token).json()["rows"]}
            self.assertEqual(rows["second@x.com"]["state"], ClusterMember.State.MERGED)
            self.assertTrue(rows["second@x.com"]["merged_into_you"])

    def test_others_see_a_merged_group_as_one_sentence(self) -> None:
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        self.confirm(self.token, self.second.id)
        self.client.logout()
        data = self.page().json()
        self.assertEqual(data["status"], DuplicateCluster.Status.RESOLVED)
        self.assertEqual(data["rows"], [])
        self.assertTrue(data["anything_merged"])

    def test_a_dismissed_group_shows_only_your_own_row(self) -> None:
        self.client.force_login(self.first)
        self.client.post(f"{BASE}/{self.token}/dismiss")
        rows = self.page().json()["rows"]
        self.assertEqual([row["email"] for row in rows], ["first@x.com"])

    def test_a_deleted_account_shows_as_gone(self) -> None:
        self.second.delete()
        self.client.force_login(self.first)
        states = [row["state"] for row in self.page().json()["rows"]]
        self.assertIn("gone", states)

    def test_a_group_resolved_by_deletion_did_not_merge(self) -> None:
        """Deletion, not a merge, closed this group (spec §13): the page's
        payload must say so, even to an outsider who sees no rows at all."""
        self.second.delete()
        close_finished()
        data = self.page().json()
        self.assertEqual(data["status"], DuplicateCluster.Status.RESOLVED)
        self.assertEqual(data["rows"], [])
        self.assertFalse(data["anything_merged"])

    def test_since_is_the_row_s_latest_event(self) -> None:
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        row = ClusterMember.objects.get(cluster=self.cluster, user=self.second)
        event = log(self.cluster, ClusterEvent.Kind.CODE_VERIFIED, member=row)
        self.assertEqual(self.rows()["second@x.com"]["since"][:19], event.at.isoformat()[:19])

    def test_an_unknown_token_is_not_found(self) -> None:
        self.assertEqual(self.page("nope").status_code, 404)

    def test_a_member_sees_when_the_other_account_last_signed_in(self) -> None:
        """How someone recognises their own old account in a detected group."""
        self.client.force_login(self.second)
        row = self.rows()["first@x.com"]
        self.assertEqual(row["last_seen"], now().strftime("%b %Y"))

    def test_nobody_can_change_an_address_or_password_here(self) -> None:
        """Same-inbox proof trusts that nobody can edit their own email: an
        account on the keeper's address is verified on sight. If the review
        step or the profile form ever took an email, that proof would be
        anyone's to forge."""
        user_fields, player_fields = resolvable_fields()
        for name in ("email", "password"):
            self.assertNotIn(name, user_fields | player_fields)
        self.assertNotIn("email", UserFormSchema.__fields__)
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        profiles = [row["profile"] for row in self.page().json()["rows"] if row["profile"]]
        self.assertEqual(len(profiles), 2)
        for profile in profiles:
            self.assertNotIn("email", profile)
            self.assertNotIn("password", profile)


class TestWhereYouStand(MergeFlowTestCase):
    def test_a_signed_in_outsider_is_told_which_account_they_are_in(self) -> None:
        outsider = self.make_account("zoya@x.com", first="Zoya", last="Khan")
        self.client.force_login(outsider)
        page = self.client.get(f"{BASE}/{self.token}").json()
        self.assertEqual(page["signed_in_elsewhere"], "zoya@x.com")
        self.assertIsNone(page["signed_in_as"])

    def test_members_and_signed_out_viewers_get_no_such_line(self) -> None:
        self.assertIsNone(self.client.get(f"{BASE}/{self.token}").json()["signed_in_elsewhere"])
        self.client.force_login(self.first)
        self.assertIsNone(self.client.get(f"{BASE}/{self.token}").json()["signed_in_elsewhere"])


class TestConfirmMerge(MergeFlowTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.first)

    def test_an_unconfirmed_account_cannot_be_taken(self) -> None:
        """The takeover: being in the group used to be enough to absorb and
        delete someone else's account, after which their own address signed
        in to yours."""
        response = self.confirm(self.token, self.second.id)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(id=self.second.id).exists())
        self.assertEqual(resolve_login_user("second@x.com"), self.second)

    def test_a_confirmed_account_merges(self) -> None:
        self.confirmed(self.first, self.second)
        second_id = self.second.id
        response = self.confirm(self.token, second_id)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(id=second_id).exists())
        merge = AccountMerge.objects.get()
        self.assertEqual(merge.cluster, self.cluster)
        self.assertEqual(merge.record["proof"]["method"], ClusterMember.Proof.EMAIL_CODE)
        self.cluster.refresh_from_db()
        self.assertEqual(self.cluster.status, DuplicateCluster.Status.RESOLVED)
        self.assertTrue(self.cluster.events.filter(kind=ClusterEvent.Kind.CLOSED).exists())

    def test_someone_else_s_confirmation_does_not_count(self) -> None:
        ClusterMember.objects.filter(cluster=self.cluster, user=self.second).update(
            state=ClusterMember.State.VERIFIED, verified_by_id=999_999
        )
        self.assertEqual(self.confirm(self.token, self.second.id).status_code, 403)

    def test_merging_twice_is_a_message_not_a_500(self) -> None:
        self.confirmed(self.first, self.second)
        second_id = self.second.id
        self.confirm(self.token, second_id)
        self.assertEqual(self.confirm(self.token, second_id).status_code, 400)

    def test_signed_out_cannot_confirm(self) -> None:
        self.client.logout()
        self.assertEqual(self.confirm(self.token, self.second.id).status_code, 401)

    def test_an_outsider_cannot_confirm(self) -> None:
        self.client.force_login(self.make_account("out@x.com", first="Kavya", last="Iyer"))
        self.assertEqual(self.confirm(self.token, self.second.id).status_code, 403)

    def test_an_expired_link_cannot_merge(self) -> None:
        ClusterMember.objects.filter(cluster=self.cluster, user=self.first).update(
            expires_at=now() - datetime.timedelta(days=1)
        )
        self.confirmed(self.first, self.second)
        self.assertEqual(self.confirm(self.token, self.second.id).status_code, 400)

    def test_a_three_account_group_is_two_merges(self) -> None:
        third = self.make_account("third@x.com")
        ClusterMember.of(self.cluster, third).save()
        for other in (self.second, third):
            self.confirmed(self.first, other)
            self.assertEqual(self.confirm(self.token, other.id).status_code, 200)
            self.cluster.refresh_from_db()
            if other is self.second:
                self.assertTrue(self.cluster.is_open)
        self.assertEqual(AccountMerge.objects.filter(cluster=self.cluster).count(), 2)
        self.assertEqual(self.cluster.members.count(), 3)
        self.assertEqual(self.cluster.status, DuplicateCluster.Status.RESOLVED)

    def test_a_blocked_merge_offers_our_team(self) -> None:
        User.objects.filter(id=self.second.id).update(first_name="Kavya", last_name="Iyer")
        self.confirmed(self.first, self.second)
        response = self.confirm(self.token, self.second.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("ask our team", response.json()["message"])

    def test_a_staff_account_is_never_merged_away_here(self) -> None:
        """is_staff does not travel with a merge, so absorbing a staff
        account would quietly delete it. Staff are merged by hand."""
        for flag in ("is_staff", "is_superuser"):
            User.objects.filter(id=self.second.id).update(**{flag: True})
            self.confirmed(self.first, self.second)
            response = self.confirm(self.token, self.second.id)
            self.assertEqual(response.status_code, 403)
            self.assertTrue(User.objects.filter(id=self.second.id).exists())
            User.objects.filter(id=self.second.id).update(**{flag: False})

    def test_who_merged_stays_true_after_they_are_merged_away(self) -> None:
        self.confirmed(self.first, self.second)
        self.confirm(self.token, self.second.id)
        third = self.make_account("third@x.com")
        first_id = self.first.id
        merge_accounts(third, [self.first], actor=third, dry_run=False)
        first = AccountMerge.objects.get(cluster=self.cluster)
        self.assertEqual(first.merged_by, third)
        self.assertEqual(first.actor_id, first_id)
        self.assertEqual(first.actor_email, "first@x.com")

    def test_the_keeper_is_told_at_their_address_now(self) -> None:
        """The row's frozen address is history; mail goes where the account
        is now."""
        User.objects.filter(id=self.first.id).update(email="first.new@x.com")
        self.first.refresh_from_db()
        self.confirmed(self.first, self.second)
        self.confirm(self.token, self.second.id)
        recipients = {task.data["to"][0] for task in Task.objects.all()}
        self.assertIn("first.new@x.com", recipients)
        self.assertNotIn("first@x.com", recipients)

    def test_both_addresses_are_told(self) -> None:
        self.confirmed(self.first, self.second)
        self.confirm(self.token, self.second.id)
        recipients = {tuple(task.data["to"]) for task in Task.objects.all()}
        self.assertIn(("first@x.com",), recipients)
        self.assertIn(("second@x.com",), recipients)


class TestConfirmMergeWithResolvedFields(MergeFlowTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.first)

    def test_the_chosen_value_lands_on_the_surviving_account(self) -> None:
        # Not a name field: differing first or last names would trip the
        # merge's own name-mismatch blocker, unrelated to what this checks.
        # Both non-blank so only the resolved choice, not _fill_blanks, can
        # produce the asserted phone.
        User.objects.filter(id=self.first.id).update(phone="1111111111")
        User.objects.filter(id=self.second.id).update(phone="9876543210")
        self.confirmed(self.first, self.second)
        response = self.confirm(self.token, self.second.id, {"phone": "9876543210"})

        self.assertEqual(response.status_code, 200)
        self.first.refresh_from_db()
        self.assertEqual(self.first.phone, "9876543210")

    def test_a_field_outside_the_form_is_a_bad_request(self) -> None:
        self.confirmed(self.first, self.second)
        response = self.confirm(self.token, self.second.id, {"is_staff": True})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(id=self.second.id).count(), 1)
        self.first.refresh_from_db()
        self.assertFalse(self.first.is_staff)


class TestConfirmMergeEdges(MergeFlowTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.first)

    def test_a_boolean_field_can_be_resolved(self) -> None:
        """Sent as a real boolean, not "true": Django rejects the string."""
        Player.objects.filter(user=self.second).update(not_in_india=True)
        self.confirmed(self.first, self.second)
        response = self.confirm(self.token, self.second.id, {"not_in_india": True})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(Player.objects.get(user=self.first).not_in_india)

    def test_a_stringified_boolean_is_a_bad_request_not_a_crash(self) -> None:
        self.confirmed(self.first, self.second)
        response = self.confirm(self.token, self.second.id, {"not_in_india": "false"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(id=self.second.id).count(), 1)

    def test_a_refused_merge_is_a_message_not_a_500(self) -> None:
        from server.duplicates.merge import MergeIncompleteError

        self.confirmed(self.first, self.second)
        with mock.patch(
            "server.duplicates.flow.merge_accounts",
            side_effect=MergeIncompleteError({"server.Thing.user": 1}),
        ):
            response = self.confirm(self.token, self.second.id)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(id=self.second.id).count(), 1)

    def test_an_address_held_elsewhere_is_a_message_not_a_500(self) -> None:
        """second@x.com already signs a live third account in - a race the
        merge cannot resolve for itself, so it must refuse rather than take
        away that account's way in."""
        bystander = self.make_account("bystander@x.com")
        EmailAlias.objects.create(email="second@x.com", user=bystander)
        self.confirmed(self.first, self.second)

        response = self.confirm(self.token, self.second.id)

        self.assertEqual(response.status_code, 400)
        self.assertIn("second@x.com", response.json()["message"])
        self.assertIn("nothing was changed", response.json()["message"])
        self.assertTrue(User.objects.filter(id=self.second.id).exists())
        self.assertEqual(EmailAlias.objects.get(email="second@x.com").user_id, bystander.id)


class TestDismiss(MergeFlowTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.first)

    def test_a_link_alone_cannot_dismiss(self) -> None:
        self.client.logout()
        self.assertEqual(self.client.post(f"{BASE}/{self.token}/dismiss").status_code, 401)
        self.cluster.refresh_from_db()
        self.assertTrue(self.cluster.is_open)

    def test_an_outsider_cannot_dismiss(self) -> None:
        self.client.force_login(self.make_account("out@x.com", first="Kavya", last="Iyer"))
        self.assertEqual(self.client.post(f"{BASE}/{self.token}/dismiss").status_code, 403)

    def test_dismissing_closes_a_pending_staff_request(self) -> None:
        request = ServiceRequest.objects.create(
            user=self.first, type=ServiceRequestType.REQUEST_ACCOUNT_MERGE, message="x"
        )
        ClusterMember.objects.filter(cluster=self.cluster, user=self.second).update(
            state=ClusterMember.State.PENDING_STAFF, staff_request=request
        )
        self.client.post(f"{BASE}/{self.token}/dismiss")
        request.refresh_from_db()
        self.assertEqual(request.status, ServiceRequestStatus.REJECTED)

    def test_dismissing_is_an_event(self) -> None:
        self.client.post(f"{BASE}/{self.token}/dismiss")
        self.assertTrue(self.cluster.events.filter(kind=ClusterEvent.Kind.DISMISSED).exists())

    def test_a_dismissal_does_not_hide_a_different_grouping(self) -> None:
        """ "These two are not the same person" says nothing about a third
        account turning up later, which used to be hidden for good."""
        self.client.post(f"{BASE}/{self.token}/dismiss")
        self.assertEqual(DuplicateCluster.objects.get().status, DuplicateCluster.Status.DISMISSED)

        self.make_account("third@x.com")
        created = detect_and_create()

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].members.count(), 3)

    def test_the_same_group_is_not_recreated_after_a_dismissal(self) -> None:
        self.client.post(f"{BASE}/{self.token}/dismiss")
        self.assertEqual(detect_and_create(), [])

    def test_it_expires_every_link_in_the_group(self) -> None:
        """One member settles it for all of them, so nobody can still merge
        with a link they are already holding."""
        other = ClusterMember.objects.get(cluster=self.cluster, user=self.second)

        self.client.post(f"{BASE}/{self.token}/dismiss")

        self.assertFalse(self.cluster.members.filter(expires_at__gt=now()).exists())
        self.client.force_login(self.second)
        response = self.confirm(other.claim_token, self.first.id)
        # require_keeper checks the cluster before the link's own expiry, so
        # a dismissed group answers "already sorted out" here too, the same
        # as the /code and /verify routes already did.
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(id=self.first.id).count(), 1)

    def test_it_records_whose_link_was_used(self) -> None:
        member = ClusterMember.objects.get(cluster=self.cluster, user=self.first)
        self.client.post(f"{BASE}/{self.token}/dismiss")

        self.cluster.refresh_from_db()
        self.assertEqual(self.cluster.dismissed_by_id, member.id)

    def test_the_page_still_explains_itself_afterwards(self) -> None:
        """Expiring the links must not turn everyone else's email into a
        dead end with no reason given."""
        other = ClusterMember.objects.get(cluster=self.cluster, user=self.second)
        self.client.post(f"{BASE}/{self.token}/dismiss")

        response = self.client.get(f"{BASE}/{other.claim_token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DuplicateCluster.Status.DISMISSED)

    def test_saying_they_are_not_me_closes_the_cluster(self) -> None:
        response = self.client.post(f"{BASE}/{self.token}/dismiss")
        self.assertEqual(response.status_code, 200)
        self.cluster.refresh_from_db()
        self.assertEqual(self.cluster.status, DuplicateCluster.Status.DISMISSED)
        self.assertEqual(User.objects.count(), 2)


class TestMergedElsewhere(MergeFlowTestCase):
    """A merge in one group can leave another with nothing to merge."""

    def setUp(self) -> None:
        super().setUp()
        self.other = DuplicateCluster.objects.create(
            origin=DuplicateCluster.Origin.REQUESTED, status=DuplicateCluster.Status.NOTIFIED
        )
        self.third = self.make_account("third@x.com")
        for user in (self.third, self.second):
            ClusterMember.of(self.other, user).save()

    def test_a_group_left_with_one_account_is_closed(self) -> None:
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        self.assertEqual(self.confirm(self.token, self.second.id).status_code, 200)
        self.other.refresh_from_db()
        self.assertEqual(self.other.status, DuplicateCluster.Status.RESOLVED)
        self.assertTrue(self.other.events.filter(kind=ClusterEvent.Kind.CLOSED).exists())
        self.client.force_login(self.third)
        # /mine now shows history too, so the closed group still turns up -
        # closed for lack of two live accounts, not because of a merge.
        groups = self.client.get(f"{BASE}/mine").json()
        self.assertEqual([g["status"] for g in groups], ["Resolved"])

    def test_mine_says_whether_anything_merged(self) -> None:
        """Both groups end Resolved, but only the one the merge happened in
        merged anything; the other closed because its account went."""
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        self.confirm(self.token, self.second.id)
        merged = self.client.get(f"{BASE}/mine").json()
        self.assertEqual(
            [(g["status"], g["anything_merged"]) for g in merged], [("Resolved", True)]
        )
        self.client.force_login(self.third)
        closed = self.client.get(f"{BASE}/mine").json()
        self.assertEqual(
            [(g["status"], g["anything_merged"]) for g in closed], [("Resolved", False)]
        )

    def test_a_group_with_two_accounts_left_stays_open(self) -> None:
        ClusterMember.of(self.other, self.make_account("fourth@x.com")).save()
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        self.confirm(self.token, self.second.id)
        self.other.refresh_from_db()
        self.assertTrue(self.other.is_open)

    def test_a_group_busy_at_the_time_is_closed_just_after(self) -> None:
        """Waiting for its lock while holding the accounts' could deadlock,
        so a group somebody else holds is closed once the merge commits."""
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        with mock.patch("server.duplicates.clusters._lock_if_free", return_value=None):
            self.confirm(self.token, self.second.id)
        self.other.refresh_from_db()
        self.assertEqual(self.other.status, DuplicateCluster.Status.RESOLVED)

    def test_a_close_that_fails_after_the_merge_does_not_stop_its_emails(self) -> None:
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        with (
            mock.patch("server.duplicates.clusters._lock_if_free", return_value=None),
            mock.patch("server.duplicates.clusters._close", side_effect=RuntimeError("down")),
            self.assertLogs("django", "ERROR"),
        ):
            response = self.confirm(self.token, self.second.id)
        self.assertEqual(response.status_code, 200)
        recipients = {task.data["to"][0] for task in Task.objects.all()}
        self.assertEqual(recipients, {"first@x.com", "second@x.com"})

    def left_open(self) -> None:
        """As if a merge had emptied the other group and its close after the
        commit had never happened."""
        ClusterMember.objects.filter(cluster=self.other, user=self.second).update(
            user=None, state=ClusterMember.State.MERGED_ELSEWHERE
        )

    def assert_closed_by_detection(self) -> None:
        self.other.refresh_from_db()
        self.assertEqual(self.other.status, DuplicateCluster.Status.RESOLVED)
        self.assertTrue(self.other.events.filter(kind=ClusterEvent.Kind.CLOSED).exists())

    def test_detection_closes_a_group_left_open(self) -> None:
        self.left_open()
        detect_and_create()
        self.assert_closed_by_detection()

    def test_the_detection_command_closes_a_group_left_open(self) -> None:
        self.left_open()
        call_command("find_duplicate_accounts", "--create", stdout=StringIO())
        self.assert_closed_by_detection()
        # Swept by the command and again by create_clusters, closed once.
        self.assertEqual(self.other.events.filter(kind=ClusterEvent.Kind.CLOSED).count(), 1)
        self.cluster.refresh_from_db()
        self.assertTrue(self.cluster.is_open)

    def test_the_command_sweeps_even_when_it_detects_nothing(self) -> None:
        """The day with no new duplicates is the day the backlog is empty,
        and the day a group left open most needs closing."""
        self.left_open()
        with mock.patch(
            "server.management.commands.find_duplicate_accounts.find_clusters", return_value=[]
        ):
            out = StringIO()
            call_command("find_duplicate_accounts", "--create", stdout=out)
        self.assert_closed_by_detection()
        self.assertIn("Closed 1 group", out.getvalue())

    def test_a_dismissed_group_is_remembered_by_its_accounts_ids(self) -> None:
        """user is cleared by a merge; the frozen account id is not."""
        DuplicateCluster.objects.filter(pk=self.other.pk).update(
            status=DuplicateCluster.Status.DISMISSED
        )
        second_id = self.second.id
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        self.confirm(self.token, second_id)
        self.assertIn(frozenset({self.third.id, second_id}), _dismissed_groups())


class TestTimeline(MergeFlowTestCase):
    def test_detection_is_the_first_event(self) -> None:
        kinds = list(self.cluster.events.values_list("kind", flat=True))
        self.assertEqual(kinds, [ClusterEvent.Kind.DETECTED])

    def test_emailing_the_group_is_an_event(self) -> None:
        notify(self.cluster)
        self.assertTrue(self.cluster.events.filter(kind=ClusterEvent.Kind.EMAILED).exists())

    def test_a_group_another_worker_emailed_is_not_emailed_again(self) -> None:
        # unnotified() reads the status outside notify's transaction, so two
        # workers can both hold this group as Detected. `stale` is the second
        # one's copy, read before the first ran. It must queue nothing.
        stale = DuplicateCluster.objects.get(pk=self.cluster.pk)
        self.assertEqual(notify(self.cluster), 2)
        sent = Task.objects.filter(type=Task.TaskType.SEND_EMAIL).count()

        self.assertEqual(notify(stale), 0)

        self.assertEqual(Task.objects.filter(type=Task.TaskType.SEND_EMAIL).count(), sent)
        self.assertEqual(self.cluster.events.filter(kind=ClusterEvent.Kind.EMAILED).count(), 1)

    def test_a_group_with_history_cannot_be_deleted(self) -> None:
        with self.assertRaises(ProtectedError):
            self.cluster.delete()

    def test_an_account_deleted_outside_a_merge_is_an_event(self) -> None:
        second_id = self.second.id
        self.second.delete()
        row = ClusterMember.objects.get(cluster=self.cluster, account_id=second_id)
        self.assertIsNone(row.user_id)
        self.assertTrue(row.is_gone)
        self.assertTrue(
            self.cluster.events.filter(kind=ClusterEvent.Kind.ACCOUNT_DELETED, member=row).exists()
        )


class RowActions(MergeFlowTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.first)

    def act(self, action: str, **payload: Any) -> Any:
        return self.client.post(
            f"{BASE}/{self.token}/{action}",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def row(self, user: User) -> ClusterMember:
        return ClusterMember.objects.get(cluster=self.cluster, account_id=user.id)

    def last_code(self) -> str:
        match = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
        if match is None:
            raise AssertionError("no code found in the last email")
        return match.group(1)


class TestCodesOnThePage(RowActions):
    def test_the_code_goes_to_the_other_account_and_names_who_asked(self) -> None:
        response = self.act("code", user_id=self.second.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox[-1].to, ["second@x.com"])
        self.assertIn(mask_email("first@x.com"), mail.outbox[-1].body)
        self.assertTrue(self.cluster.events.filter(kind=ClusterEvent.Kind.CODE_SENT).exists())

    def test_the_code_is_never_written_to_the_database(self) -> None:
        self.act("code", user_id=self.second.id)
        code = self.last_code()
        # `__contains` on a JSON key transform is Postgres/MySQL-only
        # containment and raises on SQLite; `__icontains` is the portable
        # text lookup and is exact enough for a 6-digit numeric code.
        self.assertFalse(Task.objects.filter(data__body__icontains=code).exists())
        self.assertNotIn(code, str(list(self.cluster.events.values_list("detail", flat=True))))

    def test_the_right_code_confirms_the_account_for_this_keeper(self) -> None:
        self.act("code", user_id=self.second.id)
        response = self.act("verify", user_id=self.second.id, code=self.last_code())
        self.assertEqual(response.status_code, 200)
        row = self.row(self.second)
        self.assertEqual(row.state, ClusterMember.State.VERIFIED)
        self.assertEqual(row.verified_by_id, self.first.id)
        self.assertEqual(row.proof, ClusterMember.Proof.EMAIL_CODE)

    def test_a_wrong_code_is_refused_and_logged(self) -> None:
        self.act("code", user_id=self.second.id)
        response = self.act("verify", user_id=self.second.id, code="nope")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.cluster.events.filter(kind=ClusterEvent.Kind.CODE_FAILED).exists())

    def test_the_fifth_wrong_code_is_a_lock_event(self) -> None:
        self.act("code", user_id=self.second.id)
        for _ in range(5):
            self.act("verify", user_id=self.second.id, code="nope")
        self.assertTrue(self.cluster.events.filter(kind=ClusterEvent.Kind.CODE_LOCKED).exists())

    def test_codes_are_capped_per_day(self) -> None:
        for _ in range(MAX_CODES_PER_DAY):
            self.assertEqual(self.act("code", user_id=self.second.id).status_code, 200)
            self.wait_a_minute()
        self.assertEqual(self.act("code", user_id=self.second.id).status_code, 400)

    def test_a_second_code_within_a_minute_is_refused(self) -> None:
        self.assertEqual(self.act("code", user_id=self.second.id).status_code, 200)
        response = self.act("code", user_id=self.second.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Wait a minute", response.json()["message"])

    def test_signed_out_cannot_ask_for_a_code(self) -> None:
        self.client.logout()
        self.assertEqual(self.act("code", user_id=self.second.id).status_code, 401)

    def test_an_outsider_cannot_ask_for_a_code(self) -> None:
        outsider = self.make_account("out@x.com", first="Kavya", last="Iyer")
        self.client.force_login(outsider)
        self.assertEqual(self.act("code", user_id=self.second.id).status_code, 403)

    def test_a_code_for_yourself_is_refused(self) -> None:
        self.assertEqual(self.act("code", user_id=self.first.id).status_code, 400)

    def test_a_code_for_an_already_confirmed_account_is_refused(self) -> None:
        self.act("code", user_id=self.second.id)
        self.act("verify", user_id=self.second.id, code=self.last_code())
        self.assertEqual(self.row(self.second).state, ClusterMember.State.VERIFIED)
        # Otherwise the one-a-minute resend cooldown also answers 400, and
        # the assertion below would pass whether or not this guard exists.
        self.wait_a_minute()
        self.assertEqual(self.act("code", user_id=self.second.id).status_code, 400)


class TestCodeBudget(MergeFlowTestCase):
    """The limits on codes belong to the account and to whoever asks, not to
    one group row: cancelling a request and asking again makes a new row, and
    used to start every count again."""

    def setUp(self) -> None:
        # Not super().setUp(): these tests build their own groups.
        self.victim = self.make_account("victim@x.com", first="Vic", last="Tim")

    def post(self, url: str, **payload: Any) -> Any:
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    def cycle(self, attacker: User) -> Any:
        """Ask to merge the victim, send a code, cancel. Returns the code
        response."""
        self.client.force_login(attacker)
        response = self.post(BASE, email="victim@x.com", note="")
        self.assertEqual(response.status_code, 200, response.content)
        token = response.json()["token"]
        sent = self.post(f"{BASE}/{token}/code", user_id=self.victim.id)
        self.assertEqual(self.post(f"{BASE}/{token}/dismiss").status_code, 200)
        self.wait_a_minute()
        return sent

    def test_cancelling_and_asking_again_does_not_reset_the_daily_cap(self) -> None:
        eve = self.make_account("eve@x.com", first="Eve", last="Bad")
        for _ in range(MAX_CODES_PER_DAY):
            self.assertEqual(self.cycle(eve).status_code, 200)
        # Eve has also used up her requests for the day, so a second account
        # asks: the cap is the victim's, whoever is asking.
        refused = self.cycle(self.make_account("mal@x.com", first="Mal", last="Lory"))
        self.assertEqual(refused.status_code, 400)
        self.assertIn("Too many codes today", refused.json()["message"])
        to_victim = [message for message in mail.outbox if message.to == ["victim@x.com"]]
        self.assertEqual(len(to_victim), MAX_CODES_PER_DAY)

    def test_the_resend_wait_carries_across_groups(self) -> None:
        self.client.force_login(self.make_account("eve@x.com", first="Eve", last="Bad"))
        token = self.post(BASE, email="victim@x.com").json()["token"]
        self.assertEqual(self.post(f"{BASE}/{token}/code", user_id=self.victim.id).status_code, 200)
        self.post(f"{BASE}/{token}/dismiss")
        token = self.post(BASE, email="victim@x.com").json()["token"]
        refused = self.post(f"{BASE}/{token}/code", user_id=self.victim.id)
        self.assertEqual(refused.status_code, 400)
        self.assertIn("Wait a minute", refused.json()["message"])

    def test_one_person_can_send_only_so_many_codes_a_day(self) -> None:
        eve = self.make_account("eve@x.com", first="Eve", last="Bad")
        self.client.force_login(eve)
        responses = []
        for n in range(MAX_CODES_PER_ACTOR_PER_DAY + 1):
            target = self.make_account(f"t{n}@x.com")
            cluster = DuplicateCluster.objects.create()
            mine = ClusterMember.of(cluster, eve)
            mine.save()
            ClusterMember.of(cluster, target).save()
            responses.append(self.post(f"{BASE}/{mine.claim_token}/code", user_id=target.id))
        self.assertEqual(
            [r.status_code for r in responses[:-1]], [200] * MAX_CODES_PER_ACTOR_PER_DAY
        )
        self.assertEqual(responses[-1].status_code, 400)
        self.assertIn("too many codes today", responses[-1].json()["message"])

    def test_cancelled_requests_still_count_towards_the_day(self) -> None:
        self.client.force_login(self.make_account("me@x.com"))
        for n in range(MAX_REQUESTS_PER_DAY):
            self.make_account(f"o{n}@x.com")
            token = self.post(BASE, email=f"o{n}@x.com").json()["token"]
            self.assertEqual(self.post(f"{BASE}/{token}/dismiss").status_code, 200)
        self.make_account("o9@x.com")
        refused = self.post(BASE, email="o9@x.com")
        self.assertEqual(refused.status_code, 400)
        self.assertIn("today", refused.json()["message"])
        self.assertEqual(DuplicateCluster.objects.count(), MAX_REQUESTS_PER_DAY)


class TestOneChangeAtATime(RowActions):
    """Each action reads the group again once it holds the lock, and writes
    its change and its event together. SQLite ignores the lock itself, so
    these check the re-read and the transaction; the race is Postgres's."""

    def test_a_dismissal_read_before_a_merge_does_not_undo_it(self) -> None:
        stale = DuplicateCluster.objects.get(pk=self.cluster.pk)
        self.confirmed(self.first, self.second)
        self.confirm(self.token, self.second.id)
        with self.assertRaises(FlowError):
            dismiss(stale, self.first)
        self.cluster.refresh_from_db()
        self.assertEqual(self.cluster.status, DuplicateCluster.Status.RESOLVED)
        self.assertFalse(self.cluster.events.filter(kind=ClusterEvent.Kind.DISMISSED).exists())

    def test_a_merged_group_cannot_be_dismissed(self) -> None:
        self.confirmed(self.first, self.second)
        self.confirm(self.token, self.second.id)
        response = self.client.post(f"{BASE}/{self.token}/dismiss")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.cluster.events.filter(kind=ClusterEvent.Kind.CLOSED).count(), 1)

    def test_the_other_owner_can_say_no_while_our_team_is_still_deciding(self) -> None:
        """A request waiting on staff never expires, so neither can the
        other owner's way to stop it (spec §12)."""
        with self.captureOnCommitCallbacks(execute=True):
            self.act("staff", user_id=self.second.id, note="lost it")
        ClusterMember.objects.filter(cluster=self.cluster).update(
            expires_at=now() - datetime.timedelta(days=1)
        )
        self.client.force_login(self.second)
        theirs = self.row(self.second).claim_token
        self.assertEqual(self.client.post(f"{BASE}/{theirs}/dismiss").status_code, 200)
        request = ServiceRequest.objects.get()
        self.assertEqual(request.status, ServiceRequestStatus.REJECTED)

    def test_same_inbox_is_not_verified_without_its_event(self) -> None:
        User.objects.filter(id=self.second.id).update(email="first@x.com")
        with (
            mock.patch("server.duplicates.flow.log", side_effect=RuntimeError("down")),
            self.assertRaises(RuntimeError),
        ):
            verify_same_inbox(self.cluster, self.first)
        self.assertEqual(self.row(self.second).state, ClusterMember.State.OPEN)

    def test_a_code_is_not_issued_without_its_event(self) -> None:
        with (
            mock.patch("server.duplicates.flow.log", side_effect=RuntimeError("down")),
            self.assertRaises(RuntimeError),
        ):
            self.act("code", user_id=self.second.id)
        self.assertEqual(self.row(self.second).code_hash, "")
        self.assertEqual(len(mail.outbox), 0)

    def test_a_wrong_code_is_not_counted_without_its_event(self) -> None:
        self.act("code", user_id=self.second.id)
        with (
            mock.patch("server.duplicates.flow.log", side_effect=RuntimeError("down")),
            self.assertRaises(RuntimeError),
        ):
            self.act("verify", user_id=self.second.id, code="nope")
        self.assertEqual(self.row(self.second).code_attempts, 0)

    def test_a_wrong_code_stays_counted_after_the_error_that_reports_it(self) -> None:
        self.act("code", user_id=self.second.id)
        self.assertEqual(self.act("verify", user_id=self.second.id, code="nope").status_code, 400)
        self.assertEqual(self.row(self.second).code_attempts, 1)
        self.assertTrue(self.cluster.events.filter(kind=ClusterEvent.Kind.CODE_FAILED).exists())

    def test_a_code_email_that_fails_to_send_is_a_message_and_still_counts(self) -> None:
        """Not refunded: the code exists and can be guessed at whether or not
        its email arrived, so it has to count against the day's limit."""
        with mock.patch(
            "server.duplicates.flow.send_code_email", side_effect=SMTPException("down")
        ):
            response = self.act("code", user_id=self.second.id)
        self.assertEqual(response.status_code, 503)
        self.assertIn("couldn't send", response.json()["message"])
        self.assertTrue(self.cluster.events.filter(kind=ClusterEvent.Kind.CODE_SENT).exists())


class TestCodeEmailAfterCommit(TransactionTestCase):
    """No outer test transaction here, so "after commit" is observable."""

    def test_the_code_email_is_sent_once_the_code_and_its_event_are_committed(self) -> None:
        keeper, other = (
            User.objects.create(username=address, email=address)
            for address in ("k@x.com", "o@x.com")
        )
        cluster = DuplicateCluster.objects.create()
        mine = ClusterMember.of(cluster, keeper)
        mine.save()
        ClusterMember.of(cluster, other).save()
        seen: list[tuple[bool, bool]] = []

        def record(*args: Any) -> None:
            seen.append(
                (
                    connection.in_atomic_block,
                    ClusterEvent.objects.filter(kind=ClusterEvent.Kind.CODE_SENT).exists(),
                )
            )

        self.client.force_login(keeper)
        with mock.patch("server.duplicates.flow.send_code_email", side_effect=record):
            response = self.client.post(
                f"{BASE}/{mine.claim_token}/code",
                data=json.dumps({"user_id": other.id}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen, [(False, True)])


@skipUnless(connection.vendor == "postgresql", "SQLite has no row locks to race on")
class TestRacingAMergeOnPostgres(TransactionTestCase):
    """A merge absorbing X in one group while another group acts on X.

    The merge writes the other group's merged-elsewhere event, and on
    Postgres that foreign key is checked at COMMIT with FOR KEY SHARE on the
    other group. The other action holds that group's lock while it waits for
    X, which the merge holds, so a plain FOR UPDATE there is a deadlock.
    Spec §13: the second finds the account merged elsewhere, not an error.
    """

    def account(self, address: str) -> User:
        user = User.objects.create(
            username=address, email=address, first_name="Rahul", last_name="Sharma"
        )
        Player.objects.create(
            user=user,
            date_of_birth=datetime.date(1995, 6, 15),
            gender=Player.GenderTypes.MALE,
            match_up=Player.MatchupTypes.MALE,
        )
        return user

    def setUp(self) -> None:
        self.k1, self.k2, self.x = (self.account(f"{n}@x.com") for n in ("k1", "k2", "x"))
        self.g1, self.g2 = (DuplicateCluster.objects.create() for _ in range(2))
        for cluster, keeper in ((self.g1, self.k1), (self.g2, self.k2)):
            for user in (keeper, self.x):
                ClusterMember.of(cluster, user).save()
            ClusterMember.objects.filter(cluster=cluster, user=self.x).update(
                state=ClusterMember.State.VERIFIED,
                verified_by_id=keeper.pk,
                verified_at=now(),
                proof=ClusterMember.Proof.EMAIL_CODE,
            )

    def race(
        self,
        other: Callable[[], object],
        at: str = "_release_keeper",
        merge_x: Callable[[], object] | None = None,
    ) -> dict[str, str]:
        """Run the merge (by default, of X into K1) until it holds its
        accounts and reaches `at`, start `other`, wait until Postgres says it
        is blocked, then let the merge finish."""
        from server.duplicates import merge

        holding, go = threading.Event(), threading.Event()
        real = getattr(merge, at)
        results: dict[str, str] = {}

        def paused(*args: Any) -> None:
            if threading.current_thread().name == "merge":
                holding.set()
                go.wait(10)
            real(*args)

        def run(name: str, action: Callable[[], object]) -> None:
            try:
                action()
                results[name] = "ok"
            except Exception as error:  # — recorded for the assertion
                results[name] = f"{type(error).__name__}: {str(error).splitlines()[0]}"
            finally:
                connections.close_all()

        if merge_x is None:

            def merge_x() -> None:
                flow.merge_pair(self.g1, self.k1, self.x.pk, actor=self.k1)

        threads = [
            threading.Thread(target=run, args=("merge", merge_x), name="merge"),
            threading.Thread(target=run, args=("other", other), name="other"),
        ]
        with (
            mock.patch(f"server.duplicates.merge.{at}", side_effect=paused),
            mock.patch("server.duplicates.flow.send_code_email"),
            mock.patch("server.duplicates.flow.notify_kept"),
            mock.patch("server.duplicates.flow.notify_merged"),
        ):
            threads[0].start()
            self.assertTrue(holding.wait(10))
            threads[1].start()
            with connection.cursor() as cursor:
                for _ in range(200):
                    # Waiting locks in this test database only: on a shared
                    # server anyone else's would open the gate too early.
                    cursor.execute(
                        "SELECT count(*) FROM pg_locks WHERE NOT granted AND pid IN "
                        "(SELECT pid FROM pg_stat_activity WHERE datname = current_database()) "
                        "AND pid <> pg_backend_pid()"
                    )
                    if cursor.fetchone()[0]:
                        break
                    time.sleep(0.05)
            go.set()
            for thread in threads:
                thread.join(20)
        return results

    def assert_merged_elsewhere(self, results: dict[str, str]) -> None:
        self.assertEqual(
            results,
            {
                "merge": "ok",
                "other": "FlowError: That account is not part of this group any more",
            },
        )
        self.assertFalse(User.objects.filter(pk=self.x.pk).exists())
        self.g2.refresh_from_db()
        self.assertEqual(self.g2.status, DuplicateCluster.Status.RESOLVED)

    def test_a_code_for_the_absorbed_account(self) -> None:
        self.assert_merged_elsewhere(self.race(lambda: flow.send_code(self.g2, self.k2, self.x.pk)))

    def test_two_keepers_for_one_account(self) -> None:
        self.assert_merged_elsewhere(
            self.race(lambda: flow.merge_pair(self.g2, self.k2, self.x.pk, actor=self.k2))
        )

    def test_a_request_by_the_absorbed_account(self) -> None:
        """X, still signed in, asks to merge an account into itself. The
        request waits for X's lock while the merge deletes X, and then used
        to write a group row for X that failed its foreign key at COMMIT."""
        results = self.race(lambda: flow.request_merge(self.x, "k2@x.com", ""))
        self.assertEqual(
            results,
            {
                "merge": "ok",
                "other": "FlowError: This account was just merged into another. "
                "Sign in again and try once more.",
            },
        )
        self.assertFalse(DuplicateCluster.objects.filter(origin="requested").exists())

    def test_a_staff_approval_while_the_approver_is_locked_elsewhere(self) -> None:
        """The approval writes AccountMerge.merged_by, a foreign key to the
        approver checked at COMMIT with FOR KEY SHARE. A code sent in another
        group to the approver's account locks it (lower pk, so first) and
        then waits for the keeper, which the approval holds: a deadlock
        unless the approval takes the approver in its own pk-ordered lock."""
        staff = User.objects.create_superuser("s@x.com", "s@x.com", "pw")
        keeper, y = self.account("k3@x.com"), self.account("y@x.com")
        mine = self.group((keeper, None), (y, None))
        request = ServiceRequest.objects.create(
            user=keeper, type=ServiceRequestType.REQUEST_ACCOUNT_MERGE, message="lost it"
        )
        ClusterMember.objects.filter(cluster=mine, user=y).update(
            state=ClusterMember.State.PENDING_STAFF, staff_request=request
        )
        elsewhere = self.group((keeper, None), (staff, None))
        self.assertLess(staff.pk, keeper.pk)  # so send_code takes the approver first

        results = self.race(
            lambda: flow.send_code(elsewhere, keeper, staff.pk),
            merge_x=lambda: flow.approve_staff(request, staff),
        )

        self.assertEqual(results, {"merge": "ok", "other": "ok"})
        self.assertFalse(User.objects.filter(pk=y.pk).exists())
        self.assertEqual(AccountMerge.objects.get().merged_by, staff)

    def group(self, *members: tuple[User, User | None]) -> DuplicateCluster:
        """A group of (account, the keeper it is verified for, or None)."""
        cluster = DuplicateCluster.objects.create()
        for user, keeper in members:
            row = ClusterMember.of(cluster, user)
            if keeper is not None:
                row.state = ClusterMember.State.VERIFIED
                row.verified_by_id = keeper.pk
                row.verified_at = now()
                row.proof = ClusterMember.Proof.EMAIL_CODE
            row.save()
        return cluster

    # The merge used to lock the absorbed account's rows in other groups in
    # two passes, neither in pk order: first the rows it had verified, then
    # its own. Paused between the two, it holds the first and anyone taking
    # the same group's rows in another order deadlocks with it.

    def test_a_dismissal_of_another_group_the_account_is_in(self) -> None:
        y = self.account("y@x.com")
        self.g2.members.create(user=y, account_id=y.pk, account_email=y.email)
        ClusterMember.objects.filter(cluster=self.g2, user=y).update(
            state=ClusterMember.State.VERIFIED, verified_by_id=self.x.pk, verified_at=now()
        )
        results = self.race(lambda: flow.dismiss(self.g2, self.k2), at="_settle_group_rows")
        self.assertEqual(results, {"merge": "ok", "other": "ok"})
        self.assertFalse(User.objects.filter(pk=self.x.pk).exists())
        self.g2.refresh_from_db()
        self.assertEqual(self.g2.status, DuplicateCluster.Status.DISMISSED)

    def test_two_merges_of_accounts_that_verified_each_other(self) -> None:
        z = self.account("z@x.com")
        self.group((self.x, None), (z, self.x))
        self.group((self.x, z), (z, None))
        mine = self.group((self.k2, None), (z, self.k2))
        results = self.race(
            lambda: flow.merge_pair(mine, self.k2, z.pk, actor=self.k2), at="_settle_group_rows"
        )
        self.assertEqual(results, {"merge": "ok", "other": "ok"})
        self.assertFalse(User.objects.filter(pk__in=[self.x.pk, z.pk]).exists())


class TestSameInbox(MergeFlowTestCase):
    def pair(self, kept: str, other: str) -> tuple[DuplicateCluster, User, ClusterMember]:
        """A group of two accounts on these addresses. The addresses are set
        after creation, so they can be blank or hold no @ at all."""
        n = User.objects.count()
        keeper, twin = self.make_account(f"keeper-{n}"), self.make_account(f"twin-{n}")
        User.objects.filter(pk=keeper.pk).update(email=kept)
        User.objects.filter(pk=twin.pk).update(email=other)
        keeper.refresh_from_db()
        twin.refresh_from_db()
        cluster = DuplicateCluster.objects.create()
        ClusterMember.of(cluster, keeper).save()
        row = ClusterMember.of(cluster, twin)
        row.save()
        return cluster, keeper, row

    def test_an_account_on_the_keeper_s_inbox_is_confirmed_on_sight(self) -> None:
        cluster, keeper, row = self.pair("ra.hul@gmail.com", "rahul@gmail.com")

        verify_same_inbox(cluster, keeper)

        row.refresh_from_db()
        self.assertEqual(row.state, ClusterMember.State.VERIFIED)
        self.assertEqual(row.proof, ClusterMember.Proof.SAME_INBOX)

    def test_an_address_that_cannot_receive_mail_never_matches_another(self) -> None:
        # register_ward and import_players leave an account with no address,
        # or a name slug where one should be, and normalize_email folds two
        # of those equal. Equal is not proof that anyone holds an inbox.
        for address in ["", "rahul-sharma"]:
            with self.subTest(address=address):
                cluster, keeper, row = self.pair(address, address)

                verify_same_inbox(cluster, keeper)

                row.refresh_from_db()
                self.assertEqual(row.state, ClusterMember.State.OPEN)
                self.assertEqual(row.proof, "")


class TestStaffReview(RowActions):
    def ask(self, note: str = "I lost that inbox") -> Any:
        # request_staff emails on_commit, like confirm() above.
        with self.captureOnCommitCallbacks(execute=True):
            return self.act("staff", user_id=self.second.id, note=note)

    def request(self) -> ServiceRequest:
        return ServiceRequest.objects.get(type=ServiceRequestType.REQUEST_ACCOUNT_MERGE)

    def staff(self) -> User:
        return User.objects.create_superuser("admin@x.com", "admin@x.com", "pw")

    def test_asking_creates_one_request_and_waits(self) -> None:
        self.assertEqual(self.ask().status_code, 200)
        request = self.request()
        self.assertEqual(request.user, self.first)
        self.assertEqual(list(request.service_players.all()), [self.second.player_profile])
        row = self.row(self.second)
        self.assertEqual(row.state, ClusterMember.State.PENDING_STAFF)
        self.assertEqual(row.staff_request, request)
        self.assertEqual(
            {task.data["to"][0] for task in Task.objects.all()}, {"first@x.com", "second@x.com"}
        )

    def test_approving_merges_and_names_the_staff_member(self) -> None:
        self.ask()
        staff = self.staff()
        second_id = self.second.id
        approve_staff(self.request(), staff)
        self.assertFalse(User.objects.filter(id=second_id).exists())
        merge = AccountMerge.objects.get()
        self.assertEqual(merge.merged_by, staff)
        self.assertEqual(merge.record["proof"]["method"], ClusterMember.Proof.STAFF)
        self.assertEqual(self.request().status, ServiceRequestStatus.APPROVED)

    def test_approving_makes_the_absorbed_address_sign_in_to_the_keeper(self) -> None:
        """Staff confirming the two accounts are one person is enough: both
        logins reach the kept account, even though the keeper said they
        cannot read that inbox (the owner's accepted cost, see
        merge_accounts). Without the alias, signing in with it would make
        a fresh empty account, the duplicate just removed."""
        self.ask()
        with self.captureOnCommitCallbacks(execute=True):
            approve_staff(self.request(), self.staff())
        merge = AccountMerge.objects.get()
        self.assertEqual(
            EmailAlias.objects.get(email="second@x.com").user_id, merge.primary_user_id
        )
        self.assertEqual(find_login_user("second@x.com"), merge.primary_user)
        self.assertEqual(merge.duplicate_emails, ["second@x.com"])
        # And the notice to that inbox says so.
        notice = " ".join(Task.objects.get(data__subject=MERGED_SUBJECT).data["body"].split())
        self.assertIn("approved by our team", notice)
        self.assertIn("this address now signs you in", notice)

    def test_approving_a_closed_request_merges_nothing(self) -> None:
        self.ask()
        self.client.post(f"{BASE}/{self.token}/dismiss")
        with self.assertRaises(FlowError):
            approve_staff(self.request(), self.staff())
        self.assertTrue(User.objects.filter(id=self.second.id).exists())

    def test_approving_a_request_someone_already_decided_merges_nothing(self) -> None:
        """A staff member can edit ServiceRequest.status directly in the admin
        form, outside the approve/reject actions. The cluster stays open and
        the row stays pending, so only _staff_row's status check refuses."""
        self.ask()
        request = self.request()
        request.status = ServiceRequestStatus.REJECTED
        request.save(update_fields=["status"])

        with self.assertRaises(FlowError):
            approve_staff(self.request(), self.staff())

        self.assertTrue(User.objects.filter(id=self.second.id).exists())

    def test_a_blocked_approval_leaves_the_request_waiting(self) -> None:
        self.ask()
        User.objects.filter(id=self.second.id).update(first_name="Kavya", last_name="Iyer")
        with self.assertRaises(MergeBlockedError):
            approve_staff(self.request(), self.staff())
        self.assertEqual(self.request().status, ServiceRequestStatus.PENDING)

    def mail_to(self, address: str) -> str:
        return " ".join(
            str(task.data) for task in Task.objects.all() if task.data["to"] == [address]
        )

    def test_the_team_emails_keep_the_other_address_masked(self) -> None:
        """In a detected group the keeper is only a name and birthday match;
        the page masks the other address, and so must every email."""
        self.assertEqual(self.ask(note="").status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            reject_staff(self.request(), self.staff())
        to_keeper = self.mail_to("first@x.com")
        self.assertIn(mask_email("second@x.com"), to_keeper)
        self.assertNotIn("second@x.com", to_keeper)

    def test_the_team_emails_go_to_the_keeper_s_address_now(self) -> None:
        User.objects.filter(id=self.first.id).update(email="first.new@x.com")
        self.ask()
        with self.captureOnCommitCallbacks(execute=True):
            reject_staff(self.request(), self.staff())
        self.assertEqual(self.mail_to("first@x.com"), "")
        self.assertIn("couldn't confirm", self.mail_to("first.new@x.com"))
        self.assertIn("reviewing", self.mail_to("first.new@x.com"))

    def test_rejecting_marks_the_account_rejected(self) -> None:
        self.ask()
        reject_staff(self.request(), self.staff())
        self.assertEqual(self.row(self.second).state, ClusterMember.State.REJECTED)
        self.assertEqual(self.request().status, ServiceRequestStatus.REJECTED)

    def test_a_code_after_asking_closes_the_request(self) -> None:
        self.ask()
        self.act("code", user_id=self.second.id)
        self.act("verify", user_id=self.second.id, code=self.last_code())
        self.assertEqual(self.request().status, ServiceRequestStatus.REJECTED)
        self.assertEqual(self.row(self.second).state, ClusterMember.State.VERIFIED)

    def test_a_requested_group_needs_a_note(self) -> None:
        DuplicateCluster.objects.filter(pk=self.cluster.pk).update(
            origin=DuplicateCluster.Origin.REQUESTED
        )
        self.assertEqual(self.ask(note="  ").status_code, 400)

    def test_staff_cannot_approve_their_own_request(self) -> None:
        """A second person decides: the one asking is not a check on
        themselves."""
        User.objects.filter(id=self.first.id).update(is_staff=True)
        self.ask()
        with self.assertRaises(FlowError) as refused:
            approve_staff(self.request(), User.objects.get(id=self.first.id))
        self.assertEqual(refused.exception.status, 403)
        self.assertEqual(self.request().status, ServiceRequestStatus.PENDING)
        self.assertTrue(User.objects.filter(id=self.second.id).exists())

    def test_approval_never_merges_away_a_staff_account(self) -> None:
        self.ask()
        User.objects.filter(id=self.second.id).update(is_superuser=True)
        with self.assertRaises(FlowError) as refused:
            approve_staff(self.request(), self.staff())
        self.assertEqual(refused.exception.status, 403)
        self.assertTrue(User.objects.filter(id=self.second.id).exists())
        self.assertEqual(self.request().status, ServiceRequestStatus.PENDING)

    @override_settings(
        # A view-only user gets the change list back, whose templates need
        # static files; as in test_merge.TestMergeAdmin, no manifest in tests.
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    )
    def test_staff_who_can_only_view_requests_cannot_merge(self) -> None:
        self.ask()
        viewer = User.objects.create(username="viewer@x.com", email="viewer@x.com", is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename="view_servicerequest"))
        self.client.force_login(viewer)
        for action in ("approve_and_merge", "reject_merge"):
            self.client.post(
                "/admin/server/servicerequest/",
                {"action": action, "_selected_action": [self.request().pk]},
            )
        self.assertEqual(self.request().status, ServiceRequestStatus.PENDING)
        self.assertTrue(User.objects.filter(id=self.second.id).exists())

    def test_the_admin_action_approves_and_merges(self) -> None:
        self.ask()
        self.client.force_login(self.staff())
        response = self.client.post(
            "/admin/server/servicerequest/",
            {"action": "approve_and_merge", "_selected_action": [self.request().pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.request().status, ServiceRequestStatus.APPROVED)


class TestRequestingAMerge(MergeFlowTestCase):
    def setUp(self) -> None:
        # Not super().setUp(): these tests start with no group at all.
        self.me = self.make_account("me@gmail.com")
        self.old = self.make_account("me.old@example.com")
        self.client.force_login(self.me)

    def start(self, email: str, note: str = "") -> Any:
        return self.client.post(
            BASE, data=json.dumps({"email": email, "note": note}), content_type="application/json"
        )

    def test_an_address_with_no_account_is_refused(self) -> None:
        response = self.start("nobody@x.com")
        self.assertEqual(response.status_code, 404)
        self.assertIn("couldn't find an account", response.json()["message"])
        self.assertEqual(DuplicateCluster.objects.count(), 0)

    def test_your_own_address_is_refused(self) -> None:
        self.assertEqual(self.start("me@gmail.com").status_code, 400)

    def test_a_name_slug_is_not_an_address(self) -> None:
        """An account registered without an address has a name slug for a
        username (`register_ward`, `import_players`), and sign in resolves a
        username exactly. Typing a stranger's name would otherwise make the
        caller a member of that stranger's group — and a ward's account
        carries a guardian's inbox. Refused in the same words as an unknown
        address, so this stays a non-oracle."""
        User.objects.create(
            username="meera-kumar",
            email="guardian.private@gmail.com",
            first_name="Meera",
            last_name="Kumar",
        )
        response = self.start("meera-kumar")
        self.assertEqual(response.status_code, 404)
        self.assertIn("couldn't find an account", response.json()["message"])
        self.assertEqual(DuplicateCluster.objects.count(), 0)

    def test_a_request_creates_a_group_you_keep(self) -> None:
        response = self.start("me.old@example.com")
        self.assertEqual(response.status_code, 200)
        cluster = DuplicateCluster.objects.get()
        self.assertEqual(cluster.origin, DuplicateCluster.Origin.REQUESTED)
        self.assertEqual(cluster.requested_by_id, self.me.id)
        mine = ClusterMember.objects.get(cluster=cluster, user=self.me)
        self.assertEqual(response.json()["token"], mine.claim_token)
        self.assertTrue(cluster.events.filter(kind=ClusterEvent.Kind.REQUESTED).exists())

    def test_creating_a_request_sends_no_email(self) -> None:
        self.start("me.old@example.com")
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_the_address_is_matched_the_way_sign_in_matches_it(self) -> None:
        self.assertEqual(self.start("  ME.OLD@example.com ").status_code, 200)

    def test_an_address_merged_before_finds_where_it_lives_now(self) -> None:
        EmailAlias.objects.create(email="gone@x.com", user=self.old)
        self.start("gone@x.com")
        cluster = DuplicateCluster.objects.get()
        self.assertTrue(cluster.members.filter(user=self.old).exists())

    def test_an_account_absorbed_while_we_waited_is_not_grouped(self) -> None:
        """The other account is found before the lock is taken, and a merge
        can absorb it while we wait, so it is read again once we have the
        lock. A stale instance with no row behind it stands in for that: a
        group built on it would point at an account that is gone."""
        stale = User.objects.get(pk=self.old.pk)
        self.old.delete()

        with (
            mock.patch("server.duplicates.flow.find_login_user", return_value=stale),
            self.assertRaises(FlowError) as refused,
        ):
            flow.request_merge(self.me, "me.old@example.com", "")

        self.assertEqual(refused.exception.status, 404)
        self.assertEqual(DuplicateCluster.objects.count(), 0)

    def test_a_keeper_absorbed_while_we_waited_is_refused(self) -> None:
        """The keeper is the signed-in account, loaded before the lock, and
        a merge elsewhere can absorb it while we wait, just like the other
        account. A stale instance with no row behind it stands in for that:
        a group row pointing at it failed its foreign key at COMMIT, a 500.
        Through the endpoint, so the refusal's status is one it may send."""

        def absorbed_first(keeper: User, email: str, note: str) -> ClusterMember:
            User.objects.filter(pk=keeper.pk).delete()
            return flow.request_merge(keeper, email, note)

        with mock.patch("server.duplicates.api.request_merge", side_effect=absorbed_first):
            response = self.start("me.old@example.com")

        self.assertEqual(response.status_code, 403)
        self.assertIn("Sign in again", response.json()["message"])
        self.assertEqual(DuplicateCluster.objects.count(), 0)

    def test_an_existing_shared_group_is_reused(self) -> None:
        self.start("me.old@example.com")
        self.start("me.old@example.com")
        self.assertEqual(DuplicateCluster.objects.count(), 1)

    def expire(self, token: str) -> None:
        ClusterMember.objects.filter(claim_token=token).update(
            expires_at=now() - datetime.timedelta(minutes=1)
        )

    def test_asking_again_after_the_link_expired_starts_afresh(self) -> None:
        """An expired group lets nobody act, so handing it back again was a
        dead end."""
        old = self.start("me.old@example.com").json()["token"]
        self.expire(old)
        response = self.start("me.old@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["token"], old)
        self.assertEqual(DuplicateCluster.objects.count(), 2)

    def test_mine_says_which_open_groups_have_expired(self) -> None:
        stale = self.start("me.old@example.com").json()["token"]
        self.expire(stale)
        self.make_account("third@x.com")
        live = self.start("third@x.com").json()["token"]
        self.make_account("fourth@x.com")
        dismissed = self.start("fourth@x.com").json()["token"]
        # Dismissing expires every link, but the group is finished, not
        # stuck: expired is only ever said of an open one.
        self.client.post(f"{BASE}/{dismissed}/dismiss")
        groups = {g["token"]: g["expired"] for g in self.client.get(f"{BASE}/mine").json()}
        self.assertEqual(groups, {stale: True, live: False, dismissed: False})

    def test_a_fourth_open_request_is_refused(self) -> None:
        for n in range(3):
            other = self.make_account(f"o{n}@x.com")
            self.assertEqual(self.start(other.email).status_code, 200)
        fourth = self.make_account("o9@x.com")
        self.assertEqual(self.start(fourth.email).status_code, 400)

    def test_over_the_limit_a_real_address_and_an_unknown_one_look_the_same(self) -> None:
        """The endpoint says whether an account exists, which is accepted
        only because it is rate limited. Once over the limit, answering an
        unknown address differently from a real one made the lookup free."""
        for n in range(3):
            self.assertEqual(self.start(self.make_account(f"o{n}@x.com").email).status_code, 200)
        self.make_account("real@x.com")
        answers = {
            (response.status_code, response.content)
            for response in map(self.start, ("real@x.com", "nobody@x.com", "no-at-sign"))
        }
        self.assertEqual(len(answers), 1, answers)
        self.assertEqual(next(iter(answers))[0], 400)
        self.assertEqual(DuplicateCluster.objects.count(), 3)

    def test_a_worker_cannot_fold_two_children_together(self) -> None:
        """Codes alone would allow it: one adult reads every +tag inbox."""
        worker = self.make_account("worker@gmail.com", first="Anita")
        arjun = self.make_account("worker+arjun@gmail.com", first="Arjun", last="Kumar")
        meera = self.make_account("worker+meera@gmail.com", first="Meera", last="Devi")
        for child in (arjun, meera):
            Guardianship.objects.create(user=worker, player=child.player_profile, relation="LG")
        self.client.force_login(arjun)
        token = self.start("worker+meera@gmail.com").json()["token"]
        cluster = DuplicateCluster.objects.get(origin=DuplicateCluster.Origin.REQUESTED)
        ClusterMember.objects.filter(cluster=cluster, user=meera).update(
            state=ClusterMember.State.VERIFIED, verified_by_id=arjun.id
        )
        response = self.client.post(
            f"{BASE}/{token}/confirm",
            data=json.dumps({"absorb_user_id": meera.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(id=meera.id).exists())

    def test_the_requester_can_cancel(self) -> None:
        token = self.start("me.old@example.com").json()["token"]
        self.assertIn("cancelled", self.client.post(f"{BASE}/{token}/dismiss").json()["message"])
        self.assertTrue(
            DuplicateCluster.objects.get().events.filter(kind=ClusterEvent.Kind.CANCELLED).exists()
        )

    def test_cancelled_by_you_is_true_for_the_canceller(self) -> None:
        token = self.start("me.old@example.com").json()["token"]
        self.client.post(f"{BASE}/{token}/dismiss")
        self.assertTrue(self.client.get(f"{BASE}/{token}").json()["cancelled_by_you"])

    def test_cancelled_by_you_is_false_when_the_other_owner_dismisses(self) -> None:
        """is_requester is true for the requester whether they cancelled or
        the other owner said no; cancelled_by_you must tell those apart, or
        the requester would be wrongly told they cancelled their own
        request."""
        token = self.start("me.old@example.com").json()["token"]
        self.client.force_login(self.old)
        theirs = ClusterMember.objects.get(user=self.old).claim_token
        self.client.post(f"{BASE}/{theirs}/dismiss")

        self.client.force_login(self.me)
        data = self.client.get(f"{BASE}/{token}").json()
        self.assertTrue(data["is_requester"])
        self.assertFalse(data["cancelled_by_you"])

    def test_a_requested_group_never_shows_when_the_other_signed_in(self) -> None:
        """The requester typed the address; nothing about it is theirs to
        recognise, and anyone could type anyone's."""
        User.objects.filter(id=self.old.id).update(last_login=now())
        token = self.start("me.old@example.com").json()["token"]
        rows = self.client.get(f"{BASE}/{token}").json()["rows"]
        self.assertEqual([row["last_seen"] for row in rows], [None, None])

    def test_only_the_requester_is_told_they_asked(self) -> None:
        """is_requester is what the page's intro line keys off, along with
        origin, to tell the requester, the other member and a detected
        group's members apart. matched_on used to carry this distinction as
        a sentence, but nothing rendered it once the intro copy moved to
        reading these fields directly, so it was removed rather than kept
        as a second, unread source of the same signal."""
        token = self.start("me.old@example.com").json()["token"]
        self.assertTrue(self.client.get(f"{BASE}/{token}").json()["is_requester"])
        self.client.force_login(self.old)
        theirs = ClusterMember.objects.get(user=self.old).claim_token
        self.assertFalse(self.client.get(f"{BASE}/{theirs}").json()["is_requester"])

    def test_a_signed_in_requester_now_sees_where_an_old_address_lives(self) -> None:
        """The requester picks the other member by typing an address, and an
        address that was absorbed resolves to an account whose own address
        they never typed. The owner chose to show it anyway (spec §4): a
        signed-in viewer sees every row's address on a requested group the
        same as a detected one, so the requester reads back the account's
        current address, not the "gone@x.com" they typed. Accepted cost,
        not an oversight — masking a string they just typed reads as a bug."""
        EmailAlias.objects.create(email="gone@x.com", user=self.old)
        token = self.start("gone@x.com").json()["token"]
        rows = {row["user_id"]: row for row in self.client.get(f"{BASE}/{token}").json()["rows"]}
        self.assertEqual(rows[self.old.id]["email"], "me.old@example.com")
        # Their own row is still their own address (spec §4).
        self.assertEqual(rows[self.me.id]["email"], "me@gmail.com")

    def test_a_signed_out_link_holder_still_sees_it_masked(self) -> None:
        """The tradeoff above is for a signed-in viewer only: a link holder
        with no account in this group at all still can't read where an old
        address lives now."""
        EmailAlias.objects.create(email="gone@x.com", user=self.old)
        token = self.start("gone@x.com").json()["token"]
        self.client.logout()
        rows = {row["user_id"]: row for row in self.client.get(f"{BASE}/{token}").json()["rows"]}
        self.assertEqual(rows[self.old.id]["email"], mask_email("me.old@example.com"))

    def test_a_team_email_does_not_show_where_an_old_address_lives_now(self) -> None:
        """Typed through an alias, the other account's address is not the one
        the requester typed, so it is masked like any other."""
        EmailAlias.objects.create(email="gone@x.com", user=self.old)
        token = self.start("gone@x.com").json()["token"]
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                f"{BASE}/{token}/staff",
                data=json.dumps({"user_id": self.old.id, "note": "my old inbox"}),
                content_type="application/json",
            )
        to_me = " ".join(
            str(task.data) for task in Task.objects.all() if task.data["to"] == ["me@gmail.com"]
        )
        self.assertIn("reviewing", to_me)
        self.assertNotIn("me.old@example.com", to_me)

    def test_mine_lists_open_groups_for_the_dashboard(self) -> None:
        token = self.start("me.old@example.com").json()["token"]
        groups = self.client.get(f"{BASE}/mine").json()
        self.assertEqual([g["token"] for g in groups], [token])
        self.assertEqual(groups[0]["waiting"], 1)

    def test_mine_labels_the_row_with_the_group_s_status_and_other_side(self) -> None:
        self.start("me.old@example.com")
        group = self.client.get(f"{BASE}/mine").json()[0]
        self.assertEqual(group["status"], DuplicateCluster.Status.NOTIFIED)
        self.assertTrue(group["started_at"])
        self.assertEqual(group["other_email"], "me.old@example.com")
        self.assertEqual(group["other_count"], 1)

    def test_mine_includes_a_dismissed_group_as_history(self) -> None:
        token = self.start("me.old@example.com").json()["token"]
        self.client.post(f"{BASE}/{token}/dismiss")
        groups = self.client.get(f"{BASE}/mine").json()
        self.assertEqual([g["status"] for g in groups], [DuplicateCluster.Status.DISMISSED])
        # Dismissed hides the other side even from a member (spec §5, the
        # same rule _visible_rows applies on the group page itself) - the
        # list can say a group was dismissed without naming who it was with.
        self.assertIsNone(groups[0]["other_email"])
        self.assertEqual(groups[0]["other_count"], 0)

    def test_mine_puts_live_groups_before_history(self) -> None:
        old_token = self.start("me.old@example.com").json()["token"]
        self.client.post(f"{BASE}/{old_token}/dismiss")
        self.make_account("third@x.com")
        live_token = self.start("third@x.com").json()["token"]
        groups = self.client.get(f"{BASE}/mine").json()
        self.assertEqual([g["token"] for g in groups], [live_token, old_token])

    def test_mine_orders_most_recent_first_within_a_tier(self) -> None:
        first_token = self.start("me.old@example.com").json()["token"]
        self.make_account("third@x.com")
        second_token = self.start("third@x.com").json()["token"]
        first_cluster = DuplicateCluster.objects.get(members__claim_token=first_token)
        first_cluster.created_at = now() - datetime.timedelta(days=1)
        first_cluster.save(update_fields=["created_at"])
        groups = self.client.get(f"{BASE}/mine").json()
        self.assertEqual([g["token"] for g in groups], [second_token, first_token])

    def test_mine_does_not_grow_its_query_count_with_more_groups(self) -> None:
        self.start("me.old@example.com")
        with CaptureQueriesContext(connection) as one_group:
            self.client.get(f"{BASE}/mine")

        self.make_account("third@x.com")
        self.start("third@x.com")
        self.make_account("fourth@x.com")
        self.start("fourth@x.com")
        with CaptureQueriesContext(connection) as three_groups:
            self.client.get(f"{BASE}/mine")

        self.assertEqual(len(three_groups.captured_queries), len(one_group.captured_queries))

    def test_detection_leaves_a_requested_pair_alone(self) -> None:
        self.start("me.old@example.com")
        detect_and_create()
        self.assertEqual(DuplicateCluster.objects.count(), 1)


class TestSameInboxAddress(MergeFlowTestCase):
    def setUp(self) -> None:
        # Its own accounts only: the shared setUp's pair has the same name and
        # birthday, and would join this group.
        self.keeper = self.make_account("rahul.sharma.demo@gmail.com")
        self.other = self.make_account("rahulsharmademo@gmail.com")
        [self.group] = detect_and_create()

    def test_the_absorbed_dot_variant_still_signs_in_to_the_keeper(self) -> None:
        verify_same_inbox(self.group, self.keeper)
        with self.captureOnCommitCallbacks(execute=True):
            merge_pair(self.group, self.keeper, self.other.id, actor=self.keeper)

        users = User.objects.count()
        self.assertEqual(resolve_login_user("rahulsharmademo@gmail.com").pk, self.keeper.pk)
        self.assertEqual(User.objects.count(), users)
        self.assertEqual(
            EmailAlias.objects.get(email="rahulsharmademo@gmail.com").user_id, self.keeper.pk
        )

    def test_the_keepers_own_address_is_not_made_an_alias(self) -> None:
        self.assertEqual(EmailAlias.remember([self.keeper.email], self.keeper), [])
        self.assertFalse(EmailAlias.objects.exists())


class TestBlockedMerge(MergeFlowTestCase):
    def test_a_blocked_merge_says_so_and_can_go_to_our_team(self) -> None:
        # Proven, then found to disagree on the given name: a blocker.
        User.objects.filter(pk=self.second.pk).update(first_name="Priya")
        self.confirmed(self.first, self.second)
        self.client.force_login(self.first)

        refused = self.confirm(self.token, self.second.id)
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(refused.json()["reason"], "blocked")
        self.assertTrue(User.objects.filter(pk=self.second.pk).exists())

        with self.captureOnCommitCallbacks(execute=True):
            asked = self.client.post(
                f"{BASE}/{self.token}/staff",
                data=json.dumps({"user_id": self.second.id, "note": "Priya is my legal name"}),
                content_type="application/json",
            )
        self.assertEqual(asked.status_code, 200)
        row = ClusterMember.objects.get(cluster=self.cluster, user=self.second)
        self.assertEqual(row.state, ClusterMember.State.PENDING_STAFF)


ADMIN_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=ADMIN_STORAGES)
class TestMergeAdminPages(MergeFlowTestCase):
    """The admin pages with a real history in them, not an empty group."""

    def setUp(self) -> None:
        super().setUp()
        self.staff = User.objects.create_superuser("admin@x.com", "admin@x.com", "pw")
        # A real code, issued and checked through flow.send_code/verify_code
        # - the only path that both verifies the row and logs CODE_VERIFIED
        # (flow._mark_verified) - not confirmed()'s raw row update, so the
        # group page's timeline is real history, not a planted event.
        flow.send_code(self.cluster, self.first, self.second.id)
        match = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
        if match is None:
            raise AssertionError("no code found in the last email")
        flow.verify_code(self.cluster, self.first, self.second.id, match.group(1))
        with self.captureOnCommitCallbacks(execute=True):
            merge_pair(self.cluster, self.first, self.second.id, actor=self.first)
        self.client.force_login(self.staff)

    def test_the_group_page_shows_its_rows_and_timeline(self) -> None:
        page = self.client.get(f"/admin/server/duplicatecluster/{self.cluster.pk}/change/")
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        # Choice fields render their display label in the admin, not the
        # raw stored value - so this asserts what actually renders.
        for text in ("second@x.com", "A code sent to it", "Merged", "Code Verified", "Closed"):
            self.assertIn(text, html)

    def test_the_merge_page_shows_its_record(self) -> None:
        merge = AccountMerge.objects.get(cluster=self.cluster)
        page = self.client.get(f"/admin/server/accountmerge/{merge.pk}/change/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("second@x.com", page.content.decode())

    def test_aliases_can_be_looked_up_but_not_edited(self) -> None:
        page = self.client.get("/admin/server/emailalias/?q=second")
        self.assertEqual(page.status_code, 200)
        self.assertIn("second@x.com", page.content.decode())
        alias = EmailAlias.objects.get(email="second@x.com")
        self.assertEqual(self.client.get("/admin/server/emailalias/add/").status_code, 403)
        self.assertEqual(
            self.client.get(f"/admin/server/emailalias/{alias.pk}/delete/").status_code, 403
        )


@override_settings(STORAGES=ADMIN_STORAGES)
class TestMergeRequestAdminActions(MergeFlowTestCase):
    def setUp(self) -> None:
        super().setUp()
        with self.captureOnCommitCallbacks(execute=True):
            self.request = request_staff(self.cluster, self.first, self.second.id, "lost inbox")

    def test_rejecting_through_the_admin(self) -> None:
        staff = User.objects.create_superuser("admin@x.com", "admin@x.com", "pw")
        self.client.force_login(staff)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                "/admin/server/servicerequest/",
                {"action": "reject_merge", "_selected_action": [self.request.pk]},
                follow=True,
            )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ServiceRequestStatus.REJECTED)
        row = ClusterMember.objects.get(cluster=self.cluster, user=self.second)
        self.assertEqual(row.state, ClusterMember.State.REJECTED)

    def test_an_address_held_elsewhere_is_a_message_not_a_500(self) -> None:
        """A staff approval aliases the absorbed address like any merge, so
        one another live account already signs in with must refuse it
        cleanly, and that account keeps it."""
        bystander = self.make_account("bystander@x.com")
        EmailAlias.objects.create(email="second@x.com", user=bystander)
        staff = User.objects.create_superuser("admin@x.com", "admin@x.com", "pw")
        self.client.force_login(staff)

        response = self.client.post(
            "/admin/server/servicerequest/",
            {"action": "approve_and_merge", "_selected_action": [self.request.pk]},
            follow=True,
        )

        self.assertContains(response, f"Request {self.request.pk} not merged")
        self.assertContains(response, "second@x.com")
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, ServiceRequestStatus.PENDING)
        self.assertTrue(User.objects.filter(id=self.second.id).exists())
        self.assertFalse(AccountMerge.objects.exists())
        self.assertEqual(EmailAlias.objects.get(email="second@x.com").user_id, bystander.id)

    def test_view_only_staff_are_not_offered_the_actions(self) -> None:
        viewer = User.objects.create(username="view@x.com", email="view@x.com", is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename="view_servicerequest"))
        self.client.force_login(viewer)
        html = self.client.get("/admin/server/servicerequest/").content.decode()
        self.assertNotIn("approve_and_merge", html)
        self.assertNotIn("reject_merge", html)


class TestAliasSignIn(MergeFlowTestCase):
    def test_an_absorbed_address_signs_in_to_the_keeper_through_the_endpoint(self) -> None:
        self.confirmed(self.first, self.second)
        with self.captureOnCommitCallbacks(execute=True):
            merge_pair(self.cluster, self.first, self.second.id, actor=self.first)
        users = User.objects.count()
        ts = 1_700_000_000  # the client supplies it; any value works
        otp = pyotp.TOTP(get_email_hash("second@x.com")).generate_otp(ts)
        response = self.client.post(
            "/api/otp-login",
            data=json.dumps(
                {"email": "second@x.com", "otp": otp, "otp_ts": ts, "forum_login": False}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "first@x.com")
        self.assertEqual(User.objects.count(), users)


@skipUnless(connection.vendor == "postgresql", "SQLite has no row locks to race on")
class TestRacingTwoRequestsOnPostgres(TransactionTestCase):
    """Two people asking to merge each other at the same moment.

    Each request used to lock its own keeper and nothing else, and then
    take a key-share lock on the other account by writing its group row.
    Two of them, in opposite orders, is either a group each - neither
    waited for the other, so neither saw the other's - or, as it falls out
    at this pause point, Postgres killing one of them for deadlock.
    Locking both accounts in pk order makes the second wait, and then find
    the group the first made.
    """

    def test_asking_at_the_same_moment_makes_one_group_not_two(self) -> None:
        first, second = (
            User.objects.create(username=address, email=address)
            for address in ("first@x.com", "second@x.com")
        )
        holding, go = threading.Event(), threading.Event()
        real = log  # patching flow.log below leaves this name the real one
        results: dict[str, object] = {}

        def paused(*args: Any, **kwargs: Any) -> Any:
            """The first request stops here, holding its locks and its open
            transaction, so the second has something to wait for."""
            if threading.current_thread().name == "first":
                holding.set()
                go.wait(10)
            return real(*args, **kwargs)

        def run(name: str, keeper: User, email: str) -> None:
            try:
                results[name] = flow.request_merge(keeper, email, "").cluster_id
            except Exception as error:  # — recorded for the assertion
                results[name] = f"{type(error).__name__}: {str(error).splitlines()[0]}"
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=run, args=("first", first, second.email), name="first"),
            threading.Thread(target=run, args=("second", second, first.email), name="second"),
        ]
        with mock.patch("server.duplicates.flow.log", side_effect=paused):
            threads[0].start()
            self.assertTrue(holding.wait(10))
            threads[1].start()
            with connection.cursor() as cursor:
                for _ in range(200):
                    # Waiting locks in this test database only, as above.
                    cursor.execute(
                        "SELECT count(*) FROM pg_locks WHERE NOT granted AND pid IN "
                        "(SELECT pid FROM pg_stat_activity WHERE datname = current_database()) "
                        "AND pid <> pg_backend_pid()"
                    )
                    if cursor.fetchone()[0]:
                        break
                    time.sleep(0.05)
            go.set()
            for thread in threads:
                thread.join(20)

        self.assertEqual(results["first"], results["second"])
        self.assertEqual(DuplicateCluster.objects.count(), 1)
