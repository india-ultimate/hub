import datetime
import json
import threading
import time
from collections.abc import Callable
from typing import Any
from unittest import mock, skipUnless

import pyotp
from django.db import connection, connections
from django.db.models import F, ProtectedError
from django.test import TestCase, TransactionTestCase
from django.utils.timezone import now

from server.api import get_email_hash
from server.core.accounts import resolve_login_user
from server.core.models import Guardianship, Player, User
from server.duplicates import flow
from server.duplicates.clusters import (
    create_clusters,
    detect_and_create,
)
from server.duplicates.codes import RESEND_AFTER
from server.duplicates.detect import find_clusters
from server.duplicates.emails import notify
from server.duplicates.flow import (
    merge_pair,
    verify_same_inbox,
)
from server.duplicates.models import (
    ClusterEvent,
    ClusterMember,
    DuplicateCluster,
    EmailAlias,
)

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


class TestTimeline(MergeFlowTestCase):
    def test_detection_is_the_first_event(self) -> None:
        kinds = list(self.cluster.events.values_list("kind", flat=True))
        self.assertEqual(kinds, [ClusterEvent.Kind.DETECTED])

    def test_emailing_the_group_is_an_event(self) -> None:
        notify(self.cluster)
        self.assertTrue(self.cluster.events.filter(kind=ClusterEvent.Kind.EMAILED).exists())

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

    def race(self, other: Callable[[], object]) -> dict[str, str]:
        """Run the merge until it holds both accounts, start `other`, wait
        until Postgres says it is blocked, then let the merge finish."""
        from server.duplicates import merge

        holding, go = threading.Event(), threading.Event()
        real = merge._release_keeper
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

        def merge_x() -> None:
            flow.merge_pair(self.g1, self.k1, self.x.pk, actor=self.k1)

        threads = [
            threading.Thread(target=run, args=("merge", merge_x), name="merge"),
            threading.Thread(target=run, args=("other", other), name="other"),
        ]
        with (
            mock.patch("server.duplicates.merge._release_keeper", side_effect=paused),
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


class TestSameInbox(MergeFlowTestCase):
    def test_an_account_on_the_keeper_s_inbox_is_confirmed_on_sight(self) -> None:
        keeper = self.make_account("ra.hul@gmail.com")
        twin = self.make_account("rahul@gmail.com")
        cluster = DuplicateCluster.objects.create()
        ClusterMember.of(cluster, keeper).save()
        ClusterMember.of(cluster, twin).save()

        verify_same_inbox(cluster, keeper)

        row = ClusterMember.objects.get(cluster=cluster, user=twin)
        self.assertEqual(row.state, ClusterMember.State.VERIFIED)
        self.assertEqual(row.proof, ClusterMember.Proof.SAME_INBOX)


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
