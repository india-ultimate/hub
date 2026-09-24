import datetime
from unittest import mock

from django.utils.timezone import now

from server.duplicates.codes import MAX_ATTEMPTS, check, issue
from server.duplicates.models import ClusterMember
from server.tests.test_merge_flow import MergeFlowTestCase


class TestCodes(MergeFlowTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.row = ClusterMember.objects.get(cluster=self.cluster, user=self.second)

    def test_a_code_is_six_digits_and_only_its_hash_is_kept(self) -> None:
        code = issue(self.row, self.first)
        self.assertRegex(code, r"^\d{6}$")
        self.row.refresh_from_db()
        self.assertNotIn(code, self.row.code_hash)
        self.assertEqual(self.row.code_for_id, self.first.id)

    def test_the_right_code_is_accepted_once(self) -> None:
        code = issue(self.row, self.first)
        self.assertIsNone(check(self.row, self.first, code))
        self.assertIsNotNone(check(self.row, self.first, code))

    def test_spaces_and_leading_zeros_are_fine(self) -> None:
        with mock.patch("server.duplicates.codes.secrets.randbelow", return_value=48213):
            code = issue(self.row, self.first)
        self.assertEqual(code, "048213")
        self.assertIsNone(check(self.row, self.first, " 048 213 "))

    def test_a_wrong_code_counts_an_attempt(self) -> None:
        issue(self.row, self.first)
        self.assertIsNotNone(check(self.row, self.first, "not-it"))
        self.row.refresh_from_db()
        self.assertEqual(self.row.code_attempts, 1)

    def test_it_locks_after_five_wrong_tries(self) -> None:
        code = issue(self.row, self.first)
        for _ in range(MAX_ATTEMPTS):
            self.assertIsNotNone(
                check(self.row, self.first, "000000" if code != "000000" else "111111")
            )
        error = check(self.row, self.first, code)
        self.assertTrue(error is not None and error.locked)

    def test_an_expired_code_is_refused(self) -> None:
        code = issue(self.row, self.first)
        self.row.code_expires_at = now() - datetime.timedelta(seconds=1)
        self.row.save()
        self.assertIsNotNone(check(self.row, self.first, code))

    def test_a_code_only_counts_for_who_asked(self) -> None:
        code = issue(self.row, self.first)
        self.assertIsNotNone(check(self.row, self.second, code))

    def test_a_new_code_replaces_the_old_one(self) -> None:
        old = issue(self.row, self.first)
        new = issue(self.row, self.first)
        if old != new:
            self.assertIsNotNone(check(self.row, self.first, old))
        self.assertIsNone(check(self.row, self.first, new))
