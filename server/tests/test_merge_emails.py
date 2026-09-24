from io import StringIO
from unittest.mock import patch

from django.core.management import call_command

from server.core.models import User
from server.duplicates.emails import MERGED_SUBJECT, build_messages, notify, notify_merged
from server.duplicates.models import ClusterMember, DuplicateCluster
from server.task.models import Task
from server.tests.test_merge_flow import MergeFlowTestCase


class TestDuplicateAccountEmail(MergeFlowTestCase):
    def test_one_message_per_reachable_account(self) -> None:
        messages = build_messages(self.cluster)
        self.assertEqual([m.to for m in messages], [["first@x.com"], ["second@x.com"]])

    def test_the_recipient_sees_their_own_address_and_the_others_masked(self) -> None:
        message = build_messages(self.cluster)[0]
        html = str(message.alternatives[0][0])
        self.assertIn("first@x.com", html)
        self.assertNotIn("second@x.com", html)
        self.assertIn("@x.com", html)

    def test_the_email_carries_that_account_s_own_link(self) -> None:
        member = ClusterMember.objects.get(cluster=self.cluster, user=self.first)
        html = str(build_messages(self.cluster)[0].alternatives[0][0])
        self.assertIn(f"/merge-accounts/{member.claim_token}", html)

    def test_it_says_what_matched(self) -> None:
        html = str(build_messages(self.cluster)[0].alternatives[0][0])
        self.assertIn("a name and date of birth", html)

    def test_it_explains_codes_and_the_status_page(self) -> None:
        body = build_messages(self.cluster)[0].body
        self.assertIn("code", body)
        self.assertIn("see where", body.lower())
        self.assertNotIn("?dismiss=1", body)  # the page asks before acting
        # The link keeps showing status after expiration, just disables actions
        self.assertNotIn("works for", body.lower())
        self.assertIn("days to confirm and merge", body)
        self.assertIn("still shows where", body)

    def test_an_account_with_no_address_is_skipped(self) -> None:
        User.objects.filter(pk=self.second.pk).update(email="", username="rahul-sharma")
        self.assertEqual([m.to for m in build_messages(self.cluster)], [["first@x.com"]])

    def test_a_deleted_account_does_not_break_the_email_run(self) -> None:
        self.second.delete()
        messages = build_messages(self.cluster)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].to, ["first@x.com"])
        html = str(messages[0].alternatives[0][0])
        self.assertIn("first@x.com", html)
        self.assertIn("@x.com", html)
        self.assertNotIn("second@x.com", html)

    def test_notifying_queues_the_emails_and_marks_the_cluster(self) -> None:
        self.assertEqual(notify(self.cluster), 2)
        self.assertEqual(Task.objects.filter(type=Task.TaskType.SEND_EMAIL).count(), 2)
        self.cluster.refresh_from_db()
        self.assertEqual(self.cluster.status, DuplicateCluster.Status.NOTIFIED)
        self.assertIsNotNone(self.cluster.notified_at)

    def test_the_command_only_notifies_once(self) -> None:
        out = StringIO()
        call_command("notify_duplicate_clusters", stdout=out)
        self.assertIn("Queued 2 emails", out.getvalue())

        out = StringIO()
        call_command("notify_duplicate_clusters", stdout=out)
        self.assertIn("No clusters waiting", out.getvalue())

    def test_a_dry_run_sends_nothing(self) -> None:
        out = StringIO()
        call_command("notify_duplicate_clusters", dry_run=True, stdout=out)
        self.assertIn("Would notify 1 clusters", out.getvalue())
        self.assertEqual(Task.objects.count(), 0)

    def test_the_group_is_not_marked_notified_without_its_event(self) -> None:
        with patch("server.duplicates.emails.log") as mock_log:
            mock_log.side_effect = RuntimeError("Simulated log failure")
            with self.assertRaises(RuntimeError):
                notify(self.cluster)
        # After rollback, the cluster should still be in DETECTED state
        self.cluster.refresh_from_db()
        self.assertEqual(self.cluster.status, DuplicateCluster.Status.DETECTED)
        self.assertIsNone(self.cluster.notified_at)


class TestMergedNotice(MergeFlowTestCase):
    def test_the_absorbed_address_is_told(self) -> None:
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        self.confirm(self.token, self.second.id)

        notices = Task.objects.filter(data__subject=MERGED_SUBJECT)
        self.assertEqual([task.data["to"] for task in notices], [["second@x.com"]])

    def test_a_code_proved_merge_says_the_address_signs_in(self) -> None:
        self.client.force_login(self.first)
        self.confirmed(self.first, self.second)
        self.confirm(self.token, self.second.id)
        body = " ".join(Task.objects.get(data__subject=MERGED_SUBJECT).data["body"].split())
        self.assertIn("this address now signs you in", body)

    def test_the_notice_masks_the_surviving_address(self) -> None:
        self.assertEqual(notify_merged("rahul.sharma@gmail.com", ["old@x.com"]), 1)
        body = Task.objects.get(data__subject=MERGED_SUBJECT).data["body"]
        self.assertNotIn("rahul.sharma@gmail.com", body)
        self.assertIn("@gmail.com", body)

    def test_an_address_that_cannot_receive_mail_is_skipped(self) -> None:
        self.assertEqual(notify_merged("keep@x.com", ["rahul-sharma"]), 0)

    def test_the_notice_no_longer_promises_to_undo_it(self) -> None:
        notify_merged("first@x.com", ["second@x.com"])
        body = Task.objects.get(data__subject=MERGED_SUBJECT).data["body"]
        self.assertNotIn("put it back", body)
        self.assertIn("look into it", body)
