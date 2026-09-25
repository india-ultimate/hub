import csv
import tempfile
from datetime import date, datetime
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils.timezone import now

from server.core.models import Guardianship, Player, User
from server.duplicates.clusters import create_clusters
from server.duplicates.detect import (
    BLOCK_DIFFERENT_GENDER,
    BLOCK_DIFFERENT_GUARDIANS,
    BLOCK_DIFFERENT_WARDS,
    BLOCK_GUARDIANSHIP,
    BLOCK_NAME_MISMATCH,
    RULE_EMAIL,
    RULE_FUZZY_NAME_DOB,
    RULE_NAME_DOB,
    RULE_PHONE_DOB,
    RULE_SLUG_DOB,
    find_clusters,
)
from server.duplicates.identity import (
    mask_email,
    name_slug,
    names_agree,
    normalize_email,
    normalize_name,
    normalize_phone,
)
from server.duplicates.review import Line


class TestNormalizeEmail(SimpleTestCase):
    def test_casefolds_and_strips(self) -> None:
        self.assertEqual(normalize_email("  Rahul@Example.COM "), "rahul@example.com")

    def test_keeps_a_plus_tag(self) -> None:
        # One adult, many children: the tag is the only thing telling the
        # children apart, so folding it merges them into one person.
        self.assertEqual(normalize_email("worker+arjun@example.com"), "worker+arjun@example.com")
        self.assertNotEqual(
            normalize_email("worker+arjun@gmail.com"), normalize_email("worker+meera@gmail.com")
        )
        self.assertNotEqual(
            normalize_email("worker+arjun@gmail.com"), normalize_email("worker@gmail.com")
        )

    def test_drops_dots_for_gmail_only(self) -> None:
        self.assertEqual(normalize_email("ra.hul@gmail.com"), "rahul@gmail.com")
        self.assertEqual(normalize_email("ra.hul@googlemail.com"), "rahul@googlemail.com")
        self.assertEqual(normalize_email("ra.hul@example.com"), "ra.hul@example.com")

    def test_leaves_a_name_slug_username_alone(self) -> None:
        self.assertEqual(normalize_email("rahul-sharma"), "rahul-sharma")


class TestNormalizePhone(SimpleTestCase):
    def test_collapses_country_code_and_spacing(self) -> None:
        for raw in ("9876543210", "+91 9876543210", "09876543210", "98765 43210"):
            self.assertEqual(normalize_phone(raw), "9876543210", raw)

    def test_too_short_is_empty(self) -> None:
        self.assertEqual(normalize_phone("12345"), "")
        self.assertEqual(normalize_phone(""), "")


class TestNormalizeName(SimpleTestCase):
    def test_order_case_and_punctuation(self) -> None:
        expected = "rahul sharma"
        self.assertEqual(normalize_name("Rahul", "Sharma"), expected)
        self.assertEqual(normalize_name("Sharma", "Rahul"), expected)
        self.assertEqual(normalize_name("RAHUL  ", "Sharma."), expected)

    def test_folds_accents(self) -> None:
        self.assertEqual(normalize_name("José", "Fernandes"), normalize_name("Jose", "Fernandes"))

    def test_blank_is_empty(self) -> None:
        self.assertEqual(normalize_name("", ""), "")

    def test_different_people_do_not_collide(self) -> None:
        self.assertNotEqual(normalize_name("Arjun", "Menon"), normalize_name("Kavya", "Iyer"))

    def test_keeps_a_name_in_any_script(self) -> None:
        """Only [a-z0-9] used to survive, so a name typed in Devanagari came
        out empty - and an empty name is read as no disagreement at all."""
        self.assertNotEqual(normalize_name("अर्जुन", "कुमार"), "")
        self.assertNotEqual(normalize_name("अर्जुन", "कुमार"), normalize_name("मीरा", "देवी"))


class TestNamesAgree(SimpleTestCase):
    """Whether two (first, last) names can belong to one person."""

    def test_a_surname_one_letter_off_is_one_person(self) -> None:
        self.assertTrue(names_agree(("Rahul", "Sharma"), ("Rahul", "Sharm")))

    def test_swapped_order_is_one_person(self) -> None:
        self.assertTrue(names_agree(("Rahul", "Sharma"), ("Sharma", "Rahul")))

    def test_a_given_name_one_letter_off_is_two_people(self) -> None:
        # All of these score 95 or more as whole names. The given name is
        # the part that tells two people apart, so it has to match exactly.
        for left, right in (
            (("Arun", "Venkatesan"), ("Tarun", "Venkatesan")),
            (("Ashwin", "Balasubramanian"), ("Ashwini", "Balasubramanian")),
            (("Rajesh", "Krishnamurthy"), ("Ramesh", "Krishnamurthy")),
        ):
            self.assertFalse(names_agree(left, right), (left, right))


class TestNameSlug(SimpleTestCase):
    def test_matches_the_registration_fallback(self) -> None:
        self.assertEqual(name_slug("Jane", "Doe"), "jane-doe")


class TestMaskEmail(SimpleTestCase):
    def test_keeps_the_domain(self) -> None:
        self.assertEqual(mask_email("rahul.sharma@gmail.com"), "raxxxxxxxxma@gmail.com")

    def test_handles_a_username_with_no_domain(self) -> None:
        self.assertEqual(mask_email("jane-doe"), "jaxxxxoe")


class TestFindClusters(TestCase):
    def make_player(
        self,
        username: str,
        *,
        first: str = "Rahul",
        last: str = "Sharma",
        email: str | None = None,
        dob: str = "1995-06-15",
        phone: str = "",
        uc_id: int | None = None,
        last_login: datetime | None = None,
        gender: str = Player.GenderTypes.MALE,
    ) -> Player:
        user = User.objects.create(
            username=username,
            email=username if email is None else email,
            first_name=first,
            last_name=last,
            phone=phone,
            last_login=last_login,
        )
        return Player.objects.create(
            user=user,
            date_of_birth=date.fromisoformat(dob),
            gender=gender,
            match_up=Player.MatchupTypes.MALE,
            city="Bengaluru",
            ultimate_central_id=uc_id,
        )

    def test_same_name_and_dob_cluster(self) -> None:
        self.make_player("a@x.com")
        self.make_player("b@x.com")
        clusters = find_clusters()
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].members), 2)
        self.assertIn(RULE_NAME_DOB, clusters[0].rules)

    def test_swapped_name_order_still_clusters(self) -> None:
        self.make_player("a@x.com", first="Rahul", last="Sharma")
        self.make_player("b@x.com", first="Sharma", last="Rahul")
        self.assertEqual(len(find_clusters()), 1)

    def test_same_name_different_dob_does_not_cluster(self) -> None:
        self.make_player("a@x.com", dob="1998-01-01")
        self.make_player("b@x.com", dob="1999-01-01")
        self.assertEqual(find_clusters(), [])

    def test_different_name_same_dob_does_not_cluster(self) -> None:
        self.make_player("a@x.com", first="Arjun", last="Menon")
        self.make_player("b@x.com", first="Kavya", last="Iyer")
        self.assertEqual(find_clusters(), [])

    def test_blank_names_do_not_cluster(self) -> None:
        self.make_player("a@x.com", first="", last="")
        self.make_player("b@x.com", first="", last="")
        self.assertEqual(find_clusters(), [])

    def test_normalized_email_clusters_different_people(self) -> None:
        # Same inbox wins even when the names look unrelated.
        self.make_player("ra.hul@gmail.com", first="Arjun", last="Menon", dob="1990-01-01")
        self.make_player("other", email="rahul@gmail.com", first="Kavya", last="Iyer")
        clusters = find_clusters()
        self.assertEqual(len(clusters), 1)
        self.assertIn(RULE_EMAIL, clusters[0].rules)

    def test_an_adult_holding_several_children_s_accounts_is_left_alone(self) -> None:
        """An NGO worker registers each child on a tag of their own address.
        Gmail delivers all of it to the worker, but they are not one person."""
        self.make_player("worker@gmail.com", first="Priya", last="Nair", dob="1985-01-01")
        self.make_player("worker+arjun@gmail.com", first="Arjun", last="Kumar", dob="2011-04-02")
        self.make_player("worker+meera@gmail.com", first="Meera", last="Das", dob="2013-09-14")

        self.assertEqual(find_clusters(), [])

    def test_a_shared_inbox_with_different_names_is_blocked(self) -> None:
        """A family on one address. Nothing here says they are one person."""
        self.make_player("family@x.com", first="Meera", last="Sharma", dob="1980-01-01")
        self.make_player(
            "kid", email="family@x.com", first="Arjun", last="Sharma", dob="2012-03-04"
        )

        cluster = find_clusters()[0]
        self.assertEqual(cluster.rules, {RULE_EMAIL})
        self.assertEqual(cluster.blockers, [BLOCK_NAME_MISMATCH])

    def test_a_shared_phone_with_different_names_is_blocked(self) -> None:
        """A coach's number on two players who happen to share a birthday."""
        self.make_player(
            "a@x.com", first="Arjun", last="Menon", dob="2012-03-04", phone="9876543210"
        )
        self.make_player("b@x.com", first="Meera", last="Das", dob="2012-03-04", phone="9876543210")

        cluster = find_clusters()[0]
        self.assertEqual(cluster.rules, {RULE_PHONE_DOB})
        self.assertEqual(cluster.blockers, [BLOCK_NAME_MISMATCH])

    def test_a_chain_through_a_name_match_is_still_blocked(self) -> None:
        """Parent and child share an inbox; the child happens to share a name
        and birthday with a stranger. One name rule in the chain must not make
        the parent and the stranger mergeable."""
        self.make_player("parent@x.com", first="Meera", last="Nair", dob="1980-01-01")
        self.make_player(
            "child", email="parent@x.com", first="Arjun", last="Nair", dob="2012-03-04"
        )
        self.make_player("stranger@x.com", first="Arjun", last="Nair", dob="2012-03-04")

        cluster = find_clusters()[0]
        self.assertEqual(len(cluster.members), 3)
        self.assertEqual(cluster.rules, {RULE_EMAIL, RULE_NAME_DOB, RULE_SLUG_DOB})
        self.assertIn(BLOCK_NAME_MISMATCH, cluster.blockers)

    def test_a_name_match_is_not_blocked_by_it(self) -> None:
        self.make_player("a@x.com")
        self.make_player("b@x.com")

        cluster = find_clusters()[0]
        self.assertIn(RULE_NAME_DOB, cluster.rules)
        self.assertTrue(cluster.is_mergeable)

    def test_an_account_with_no_name_is_not_a_mismatch(self) -> None:
        """An empty account made by signing in, beside the real one. This is
        the case the whole flow exists for and must stay mergeable."""
        self.make_player("rahul@x.com", first="Rahul", last="Sharma")
        self.make_player("blank", email="rahul@x.com", first="", last="")

        cluster = find_clusters()[0]
        self.assertEqual(cluster.rules, {RULE_EMAIL})
        self.assertTrue(cluster.is_mergeable)

    def test_phone_and_dob_cluster(self) -> None:
        self.make_player("a@x.com", first="Arjun", last="Menon", phone="9876543210")
        self.make_player("b@x.com", first="A", last="Menon", phone="+91 98765 43210")
        clusters = find_clusters()
        self.assertEqual(len(clusters), 1)
        self.assertIn(RULE_PHONE_DOB, clusters[0].rules)

    def test_name_slug_username_links_to_the_real_account(self) -> None:
        # What register_ward leaves behind when no email is given.
        self.make_player("rahul-sharma", email="", first="", last="")
        self.make_player("rahul@x.com", first="Rahul", last="Sharma")
        clusters = find_clusters()
        self.assertEqual(len(clusters), 1)
        self.assertIn(RULE_SLUG_DOB, clusters[0].rules)

    def test_clusters_merge_transitively_across_rules(self) -> None:
        # a ~ b on the shared inbox, b ~ c on name and date of birth.
        self.make_player("a@x.com", email="shared@x.com", first="Arjun", last="Menon")
        self.make_player("b@x.com", email="shared@x.com", first="Rahul", last="Sharma")
        self.make_player("c@x.com", first="Rahul", last="Sharma")
        clusters = find_clusters()
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].members), 3)

    def test_guardianship_edge_blocks_the_cluster(self) -> None:
        parent = self.make_player("parent@x.com")
        child = self.make_player("child@x.com")
        Guardianship.objects.create(
            user=parent.user, player=child, relation=Guardianship.Relation.FA
        )
        clusters = find_clusters()
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].blockers, [BLOCK_GUARDIANSHIP])
        self.assertFalse(clusters[0].is_mergeable)

    def test_conflicting_ultimate_central_ids_do_not_block(self) -> None:
        # Ultimate Central is retired. The primary keeps its own id and the
        # other goes into the audit snapshot with the rest of the absorbed row.
        self.make_player("a@x.com", uc_id=4242)
        self.make_player("b@x.com", uc_id=9999)
        clusters = find_clusters()
        self.assertEqual(len(clusters), 1)
        self.assertTrue(clusters[0].is_mergeable)

    def test_twins_on_a_parents_phone_are_blocked(self) -> None:
        parent = self.make_player("mum@x.com", first="Meera", dob="1980-01-01")
        wards = [
            self.make_player("arjun@x.com", first="Arjun", dob="2012-03-04", phone="9876543210"),
            self.make_player("aryan@x.com", first="Aryan", dob="2012-03-04", phone="9876543210"),
        ]
        for ward in wards:
            Guardianship.objects.create(
                user=parent.user, player=ward, relation=Guardianship.Relation.MO
            )

        cluster = find_clusters()[0]
        self.assertEqual({m.username for m in cluster.members}, {"arjun@x.com", "aryan@x.com"})
        # Both apply: two wards of one guardian, and only a shared phone
        # holding two different names together.
        self.assertEqual(cluster.blockers, [BLOCK_DIFFERENT_WARDS, BLOCK_NAME_MISMATCH])

    def test_one_child_claimed_by_two_parents_is_blocked(self) -> None:
        """Same child, registered once by each parent. Only one guardianship
        row can survive the one-to-one, and picking a parent is not ours."""
        mother = self.make_player("mum@x.com", first="Meera", last="Rao", dob="1980-01-01")
        father = self.make_player("dad@x.com", first="Vikram", last="Rao", dob="1978-01-01")
        first = self.make_player("arjun@x.com", first="Arjun", last="Rao", dob="2012-03-04")
        second = self.make_player("arjun.rao@x.com", first="Arjun", last="Rao", dob="2012-03-04")
        Guardianship.objects.create(
            user=mother.user, player=first, relation=Guardianship.Relation.MO
        )
        Guardianship.objects.create(
            user=father.user, player=second, relation=Guardianship.Relation.FA
        )

        cluster = find_clusters()[0]
        self.assertEqual({m.username for m in cluster.members}, {"arjun@x.com", "arjun.rao@x.com"})
        self.assertIn(BLOCK_DIFFERENT_GUARDIANS, cluster.blockers)

    def test_one_child_registered_twice_still_merges(self) -> None:
        parent = self.make_player("dad@x.com", first="Vikram", dob="1980-01-01")
        for username in ("arjun@x.com", "arjun.sharma@x.com"):
            ward = self.make_player(username, first="Arjun", dob="2012-03-04")
            Guardianship.objects.create(
                user=parent.user, player=ward, relation=Guardianship.Relation.FA
            )

        cluster = find_clusters()[0]
        self.assertEqual(
            {m.username for m in cluster.members}, {"arjun@x.com", "arjun.sharma@x.com"}
        )
        self.assertTrue(cluster.is_mergeable)

    def test_members_are_ordered_by_most_recent_sign_in(self) -> None:
        self.make_player("never@x.com")
        recent = self.make_player("recent@x.com", last_login=now())
        self.assertEqual(find_clusters()[0].members[0].user_id, recent.user_id)

    def test_a_misspelling_clusters_and_is_not_then_refused(self) -> None:
        """The pair fuzzy exists to find. Comparing names for equality here
        would block every one of them the moment it was found."""
        self.make_player("a@x.com", first="Rahul", last="Sharma", phone="9876543210")
        self.make_player("b@y.com", first="Rahul", last="Sharm", phone="+91 98765 43210")

        clusters = find_clusters()
        self.assertEqual(len(clusters), 1)
        self.assertIn(RULE_FUZZY_NAME_DOB, clusters[0].rules)
        self.assertTrue(clusters[0].is_mergeable)

    def test_a_misspelling_with_nothing_else_shared_does_not_cluster(self) -> None:
        """A near name and a birthday is not enough on its own. In
        production half the surname typos share neither phone nor email."""
        self.make_player("a@x.com", first="Rahul", last="Sharma")
        self.make_player("b@y.com", first="Rahul", last="Sharm")
        self.assertEqual(find_clusters(), [])

    def test_a_misspelling_sharing_an_email_name_clusters(self) -> None:
        # Same mailbox name at two providers is the second signal too.
        self.make_player("rahul.s@gmail.com", first="Rahul", last="Sharma")
        self.make_player("rahuls@yahoo.com", first="Rahul", last="Sharm")
        self.assertIn(RULE_FUZZY_NAME_DOB, find_clusters()[0].rules)

    def test_twins_on_a_parents_phone_are_refused(self) -> None:
        """Same phone, same birthday, given names a letter apart: twins. Two
        of the three such pairs in production share a phone, so a second
        signal alone would have merged them."""
        self.make_player("ashwin@x.com", first="Ashwin", last="Balasubramanian", phone="9876543210")
        self.make_player(
            "ashwini@x.com", first="Ashwini", last="Balasubramanian", phone="9876543210"
        )

        cluster = find_clusters()[0]
        self.assertNotIn(RULE_FUZZY_NAME_DOB, cluster.rules)
        self.assertIn(BLOCK_NAME_MISMATCH, cluster.blockers)

    def test_twins_where_only_one_has_a_guardian_are_refused(self) -> None:
        # different_wards needs two guardianship rows; the name rule does not.
        parent = self.make_player("mum@x.com", first="Lakshmi", dob="1980-01-01")
        ashwin = self.make_player(
            "ashwin@x.com", first="Ashwin", last="Balasubramanian", phone="9876543210"
        )
        self.make_player(
            "ashwini@x.com", first="Ashwini", last="Balasubramanian", phone="9876543210"
        )
        Guardianship.objects.create(
            user=parent.user, player=ashwin, relation=Guardianship.Relation.MO
        )

        cluster = find_clusters()[0]
        self.assertFalse(cluster.is_mergeable)

    def test_two_nameless_accounts_on_one_phone_are_refused(self) -> None:
        """One nameless account is the empty one sign in creates. Two is no
        evidence at all, and twins on a family phone look exactly like it."""
        self.make_player("a@x.com", first="", last="", phone="9876543210")
        self.make_player("b@x.com", first="", last="", phone="9876543210")

        cluster = find_clusters()[0]
        self.assertIn(BLOCK_NAME_MISMATCH, cluster.blockers)

    def test_a_ward_named_in_devanagari_is_refused(self) -> None:
        """The name used to normalise to nothing, and one empty name is read
        as the blank account sign in creates rather than as a disagreement -
        so the check was off for exactly the NGO accounts the +tag rule
        protects. One child in each script is the shape that exposed it."""
        worker = self.make_player("worker@ngo.org", first="Anita", dob="1985-01-01")
        for username, first, last in (
            ("worker+arjun@gmail.com", "Arjun", "Kumar"),
            ("worker+meera@gmail.com", "मीरा", "देवी"),
        ):
            ward = self.make_player(
                username, first=first, last=last, dob="2012-03-04", phone="9876543210"
            )
            Guardianship.objects.create(
                user=worker.user, player=ward, relation=Guardianship.Relation.LG
            )

        cluster = find_clusters()[0]
        self.assertFalse(cluster.is_mergeable)
        self.assertIn(BLOCK_NAME_MISMATCH, cluster.blockers)

    def test_same_name_and_birthday_but_a_different_gender_is_refused(self) -> None:
        self.make_player("a@x.com", gender=Player.GenderTypes.MALE)
        self.make_player("b@x.com", gender=Player.GenderTypes.FEMALE)
        self.assertIn(BLOCK_DIFFERENT_GENDER, find_clusters()[0].blockers)

    def test_a_transposition_falls_below_the_bar(self) -> None:
        # "shrama" for "sharma" scores 92, under NAME_SIMILARITY. Deliberate:
        # the threshold is what stops two real people being grouped.
        self.make_player("a@x.com", first="Rahul", last="Sharma")
        self.make_player("b@x.com", first="Rahul", last="Shrama")
        self.assertEqual(find_clusters(), [])

    def test_a_name_that_is_merely_different_does_not_cluster(self) -> None:
        self.make_player("a@x.com", first="Arjun", last="Menon")
        self.make_player("b@x.com", first="Kavya", last="Iyer")
        self.assertEqual(find_clusters(), [])

    def test_an_exact_match_is_not_reported_as_fuzzy(self) -> None:
        self.make_player("a@x.com")
        self.make_player("b@x.com")
        self.assertNotIn(RULE_FUZZY_NAME_DOB, find_clusters()[0].rules)


class TestFindDuplicateAccountsCommand(TestFindClusters):
    def test_reports_nothing_when_there_are_no_duplicates(self) -> None:
        self.make_player("only@x.com")
        out = StringIO()
        call_command("find_duplicate_accounts", stdout=out)
        self.assertIn("No duplicate accounts found", out.getvalue())

    def test_summarises_and_writes_a_row_per_account(self) -> None:
        self.make_player("a@x.com")
        self.make_player("b@x.com")
        self.make_player("c@x.com", first="Arjun", last="Menon", dob="1990-01-01")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicates.csv"
            out = StringIO()
            call_command("find_duplicate_accounts", csv=str(path), stdout=out)

            self.assertIn("Clusters:              1", out.getvalue())
            self.assertIn("Would be merged away:  1", out.getvalue())
            rows = list(csv.DictReader(path.read_text().splitlines()))

        self.assertEqual(len(rows), 2)
        self.assertEqual({r["email"] for r in rows}, {"a@x.com", "b@x.com"})
        self.assertIn(RULE_NAME_DOB, rows[0]["rules"].split())

    def test_reports_the_reason_a_cluster_is_blocked(self) -> None:
        parent = self.make_player("parent@x.com")
        child = self.make_player("child@x.com")
        Guardianship.objects.create(
            user=parent.user, player=child, relation=Guardianship.Relation.FA
        )
        out = StringIO()
        call_command("find_duplicate_accounts", stdout=out)
        self.assertIn("Blocked clusters:      1", out.getvalue())
        self.assertIn(f"blocked by {BLOCK_GUARDIANSHIP}: 1", out.getvalue())


class TestUnreachableClusters(TestFindClusters):
    def test_a_group_nobody_can_email_is_not_saved(self) -> None:
        self.make_player("rahul-sharma", email="")
        self.make_player("sharma-rahul", first="Sharma", last="Rahul", email="")

        self.assertEqual(create_clusters(find_clusters()), [])

    def test_one_reachable_member_is_enough(self) -> None:
        self.make_player("rahul-sharma", email="")
        self.make_player("rahul@x.com")

        self.assertEqual(len(create_clusters(find_clusters())), 1)


class TestReviewLine(SimpleTestCase):
    def test_a_blank_is_unknown_not_different(self) -> None:
        self.assertFalse(Line("City", ["Pune", ""]).differs)

    def test_two_values_disagreeing_is_marked(self) -> None:
        self.assertTrue(Line("City", ["Pune", "Delhi"]).differs)

    def test_a_missing_profile_is_marked(self) -> None:
        self.assertTrue(Line("Has a player profile", ["yes", ""]).differs)

    def test_names_are_compared_normalised(self) -> None:
        self.assertFalse(Line("Name", ["Rahul  Sharma", "sharma rahul"]).differs)

    def test_rows_that_always_differ_are_not_marked(self) -> None:
        self.assertFalse(Line("Email", ["a@x.com", "b@x.com"]).differs)
