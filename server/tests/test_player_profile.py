from unittest import mock

from django.db import IntegrityError
from django.test import TestCase

from server.core.models import Player, User
from server.player_profile.slugs import has_base, unique_slug
from server.tests.base import create_player


def make_player(first: str, last: str) -> Player:
    n = User.objects.count()
    user = User.objects.create(username=f"u{n}", first_name=first, last_name=last)
    return create_player(user)


class TestSlugs(TestCase):
    def test_slug_from_name(self) -> None:
        self.assertEqual(make_player("Ananya", "Rao").slug, "ananya-rao")

    def test_same_name_gets_suffix(self) -> None:
        slugs = [make_player("Ananya", "Rao").slug for _ in range(3)]
        self.assertEqual(slugs, ["ananya-rao", "ananya-rao-2", "ananya-rao-3"])

    def test_non_latin_name_falls_back(self) -> None:
        self.assertEqual(make_player("अनन्या", "").slug, "player")
        self.assertEqual(make_player("अनन्या", "").slug, "player-2")

    def test_rename_updates_slug(self) -> None:
        player = make_player("Ananya", "Rao")
        player.user.first_name = "Anu"
        player.user.save()
        player.refresh_from_db()
        self.assertEqual(player.slug, "anu-rao")
        self.assertFalse(Player.objects.filter(slug="ananya-rao").exists())

    def test_rename_frees_old_slug_and_avoids_collision(self) -> None:
        a = make_player("Ananya", "Rao")
        b = make_player("Meera", "Iyer")
        b.user.first_name, b.user.last_name = "Ananya", "Rao"
        b.user.save()
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((a.slug, b.slug), ("ananya-rao", "ananya-rao-2"))

    def test_unrelated_save_keeps_slug(self) -> None:
        player = make_player("Ananya", "Rao")
        with self.assertNumQueries(1):
            player.user.save(update_fields=["last_login"])
        player.refresh_from_db()
        self.assertEqual(player.slug, "ananya-rao")

    def test_unique_slug_pure(self) -> None:
        self.assertEqual(unique_slug("a", {"a", "a-2"}), "a-3")
        self.assertTrue(has_base("a-12", "a"))
        self.assertFalse(has_base("ab", "a"))

    def test_slug_collision_on_save_is_retried(self) -> None:
        make_player("Ananya", "Rao")
        stale = iter(["ananya-rao"])
        with mock.patch(
            "server.core.models.unique_slug",
            side_effect=lambda base, taken: next(stale, None) or unique_slug(base, taken),
        ):
            player = make_player("Ananya", "Rao")
        self.assertEqual(player.slug, "ananya-rao-2")

    def test_other_integrity_error_is_not_retried(self) -> None:
        first = make_player("Ananya", "Rao")
        first.iu_id = "X1"
        first.save()
        user = User.objects.create(username="dup", first_name="Ananya", last_name="Rao")
        with (
            mock.patch.object(Player, "assign_slug", autospec=True) as assign,
            self.assertRaises(IntegrityError),
        ):
            Player.objects.create(user=user, iu_id="X1", date_of_birth=first.date_of_birth)
        self.assertEqual(assign.call_count, 1)

    def test_save_with_update_fields_persists_new_slug(self) -> None:
        player = make_player("Ananya", "Rao")
        player.slug = None
        player.save(update_fields=["imported_data"])
        player.refresh_from_db()
        self.assertEqual(player.slug, "ananya-rao")
