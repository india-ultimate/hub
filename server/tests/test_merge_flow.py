import datetime
import json
from typing import Any

from django.db.models import F
from django.test import TestCase
from django.utils.timezone import now

from server.core.models import Guardianship, Player, User
from server.duplicates.clusters import (
    create_clusters,
    detect_and_create,
)
from server.duplicates.codes import RESEND_AFTER
from server.duplicates.detect import find_clusters
from server.duplicates.models import (
    ClusterEvent,
    ClusterMember,
    DuplicateCluster,
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
