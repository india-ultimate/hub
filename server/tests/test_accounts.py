from importlib import import_module
from unittest import mock

from django.apps import apps
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from server.core.accounts import find_login_user, resolve_login_user
from server.core.models import User
from server.duplicates.models import EmailAlias


class TestFindLoginUser(TestCase):
    def test_it_never_creates_an_account(self) -> None:
        self.assertIsNone(find_login_user("nobody@x.com"))
        self.assertFalse(User.objects.filter(username="nobody@x.com").exists())


class TestResolveLoginUser(TestCase):
    def test_finds_an_account_whose_username_is_its_address(self) -> None:
        user = User.objects.create(username="jane@example.com", email="jane@example.com")
        self.assertEqual(resolve_login_user("Jane@Example.com "), user)
        self.assertEqual(User.objects.count(), 1)

    def test_case_mismatched_email_does_not_collide_on_username(self) -> None:
        user = User.objects.create(username="bob@example.com", email="Bob@Example.com")
        self.assertEqual(resolve_login_user("bob@example.com"), user)
        self.assertEqual(User.objects.count(), 1)

    def test_unknown_email_creates_exactly_one_account(self) -> None:
        user = resolve_login_user("new@example.com")
        self.assertEqual(user.username, "new@example.com")
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(User.objects.count(), 1)

    def test_a_gmail_dot_variant_is_a_new_account(self) -> None:
        # Resolving it would mean normalizing the table on every sign in. The
        # duplicate it leaves is found by name and date of birth instead.
        User.objects.create(username="ra.hul@gmail.com", email="ra.hul@gmail.com")
        self.assertEqual(resolve_login_user("rahul@gmail.com").username, "rahul@gmail.com")
        self.assertEqual(User.objects.count(), 2)

    def test_an_absorbed_address_still_resolves_through_its_alias(self) -> None:
        keep = User.objects.create(username="new@example.com", email="new@example.com")
        EmailAlias.objects.create(email="old@example.com", user=keep)
        self.assertEqual(resolve_login_user("Old@Example.com"), keep)
        self.assertEqual(User.objects.count(), 1)

    def test_an_account_created_between_the_lookup_and_the_insert(self) -> None:
        """Two requests for an address neither of them found both reach the
        insert, and only one can hold the username. The loser used to raise
        IntegrityError at whoever was signing in."""
        winner = User.objects.create(username="race@example.com", email="race@example.com")
        with mock.patch(
            "server.core.accounts.find_login_user", side_effect=[None, winner]
        ) as lookup:
            self.assertEqual(resolve_login_user("race@example.com"), winner)
        self.assertEqual(lookup.call_count, 2)
        self.assertEqual(User.objects.count(), 1)

    def test_a_duplicate_is_reached_by_its_own_username(self) -> None:
        # Two accounts can share an address but never a username, so each
        # resolves to exactly one row until the merge joins them.
        first = User.objects.create(username="dup@example.com", email="dup@example.com")
        second = User.objects.create(username="dup-2", email="dup@example.com")
        self.assertEqual(resolve_login_user("dup@example.com"), first)
        self.assertEqual(resolve_login_user("dup-2"), second)
        self.assertEqual(User.objects.count(), 2)


class TestAlignUsernamesMigration(TestCase):
    def migrate(self) -> None:
        import_module("server.migrations.0142_align_usernames").align_usernames(apps, None)

    def test_it_lowercases_usernames(self) -> None:
        User.objects.create(username="Rahul@Example.COM", email="Rahul@Example.COM")
        self.migrate()
        self.assertEqual(User.objects.get().username, "rahul@example.com")

    def test_it_aligns_a_username_that_drifted_from_its_address(self) -> None:
        # register_ward left these behind when an email arrived later.
        user = User.objects.create(username="jane-doe", email="jane@example.com")
        self.migrate()
        user.refresh_from_db()
        self.assertEqual(user.username, "jane@example.com")
        self.assertEqual(resolve_login_user("jane@example.com"), user)
        self.assertEqual(User.objects.count(), 1)

    def test_it_frees_a_username_the_first_pass_was_blocked_on(self) -> None:
        """B wants an address A is sitting on, and A is about to move off it.
        One pass in pk order skipped B for good."""
        blocked = User.objects.create(username="jane-slug", email="jane@example.com")
        holder = User.objects.create(username="jane@example.com", email="holder@example.com")

        self.migrate()

        blocked.refresh_from_db()
        holder.refresh_from_db()
        self.assertEqual(holder.username, "holder@example.com")
        self.assertEqual(blocked.username, "jane@example.com")
        self.assertEqual(resolve_login_user("jane@example.com"), blocked)
        self.assertEqual(User.objects.count(), 2)

    def test_it_leaves_an_account_with_no_email_alone(self) -> None:
        User.objects.create(username="jane-doe", email="")
        self.migrate()
        self.assertEqual(User.objects.get().username, "jane-doe")

    def test_it_leaves_a_username_whose_lowercase_form_is_taken(self) -> None:
        # That pair is a duplicate; the merge flow resolves it, not a migration.
        User.objects.create(username="rahul@x.com", email="rahul@x.com")
        User.objects.create(username="Rahul@X.com", email="Rahul@X.com")
        self.migrate()
        self.assertEqual(
            set(User.objects.values_list("username", flat=True)),
            {"rahul@x.com", "Rahul@X.com"},
        )


class TestResolveLoginUserCost(TestCase):
    def user_reads(self, email: str) -> list[str]:
        for index in range(20):
            User.objects.create(username=f"u{index}@x.com", email=f"u{index}@x.com")
        with CaptureQueriesContext(connection) as captured:
            resolve_login_user(email)
        return [
            query["sql"]
            for query in captured.captured_queries
            if query["sql"].startswith("SELECT") and 'FROM "server_user"' in query["sql"]
        ]

    def assert_single_indexed_read(self, email: str) -> None:
        """One exact match on the unique username index.

        Both the old lookup and its fallback scan were single queries, so
        counting across table sizes would look identical; what changed is
        that there is one read and it compares with = rather than LIKE.
        """
        reads = self.user_reads(email)
        self.assertEqual(len(reads), 1, "\n\n".join(reads))
        condition = reads[0].split("WHERE", 1)[1]
        self.assertIn("=", condition)
        self.assertNotIn("LIKE", condition)

    def test_an_unknown_address_reads_the_table_once(self) -> None:
        self.assert_single_indexed_read("new@example.com")

    def test_a_known_address_reads_the_table_once(self) -> None:
        self.assert_single_indexed_read("u1@x.com")
