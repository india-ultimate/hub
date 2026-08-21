"""The Format section of a tournament's rules tracks the stages that actually exist."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import patch

from django.test import TestCase
from django.utils.dateparse import parse_datetime

import server.tournament.rules as rules_module
from server.core.models import Team
from server.tests.base import create_event, not_none
from server.tournament.models import CrossPool, Match, Tournament, TournamentField
from server.tournament.rules import (
    EMPTY_FORMAT,
    FORMAT_BLOCK_END,
    FORMAT_BLOCK_START,
    render_format_table,
    sync_rules_format,
    upgrade_legacy_format_block,
)
from server.tournament.utils import (
    build_bracket,
    build_pool,
    build_position_pool,
    build_swiss_round,
    get_default_rules,
)

STAFF_NOTE = "Bring your own water. Fields open at 7am."


class RulesFormatTests(TestCase):
    def setUp(self) -> None:
        self.event = create_event(title="Format Open")
        self.tournament = Tournament.objects.create(event=self.event)
        teams = [Team.objects.create(name=f"Fmt {i}", slug=f"fmt-{i}") for i in range(1, 9)]
        seeding = {str(i): team.id for i, team in enumerate(teams, start=1)}
        self.tournament.initial_seeding = seeding
        self.tournament.current_seeding = seeding
        self.tournament.rules = get_default_rules()
        self.tournament.save()
        self.tournament.teams.set(teams)
        self.tournament.refresh_from_db()
        TournamentField.objects.create(tournament=self.tournament, name="Field 1")

    def _rules(self) -> str:
        self.tournament.refresh_from_db()
        return self.tournament.rules or ""

    def _block(self) -> str:
        rules = self._rules()
        start = rules.index(FORMAT_BLOCK_START)
        end = rules.index(FORMAT_BLOCK_END)
        return rules[start:end]

    def test_a_new_tournament_starts_with_a_placeholder_not_a_made_up_format(self) -> None:
        # The shipped default used to describe a 16-team event regardless of what
        # was actually being run.
        self.assertIn(EMPTY_FORMAT, self._rules())
        self.assertNotIn("4 Pools of 4", self._rules())

    def test_creating_a_pool_fills_the_table_in(self) -> None:
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        block = self._block()
        self.assertIn("**Pool A**", block)
        self.assertIn("1-4", block)
        self.assertIn("Round-robin, re-seed within the pool", block)
        self.assertNotIn(EMPTY_FORMAT, block)

    def test_every_stage_type_appears_in_play_order(self) -> None:
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        build_pool(self.tournament, name="B", sequence_number=2, seeding=[5, 6, 7, 8])
        build_bracket(self.tournament, name="1-8", sequence_number=3)

        block = self._block()
        for label in ("**Pool A**", "**Pool B**", "**Bracket 1-8**"):
            self.assertIn(label, block)
        self.assertLess(block.index("**Pool A**"), block.index("**Bracket 1-8**"))
        self.assertIn("Winner takes the higher seed", block)

    def test_a_swiss_group_reports_its_round_count(self) -> None:
        build_swiss_round(
            self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4], num_rounds=3
        )
        self.assertIn("**Swiss A**", self._block())
        self.assertIn("3 rounds", self._block())

    def test_deleting_a_stage_takes_it_back_out(self) -> None:
        pool = build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        build_pool(self.tournament, name="B", sequence_number=2, seeding=[5, 6, 7, 8])
        self.assertIn("**Pool A**", self._block())

        pool.delete()

        self.assertNotIn("**Pool A**", self._block())
        self.assertIn("**Pool B**", self._block())

    def test_removing_every_stage_returns_to_the_placeholder(self) -> None:
        pool = build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        pool.delete()
        self.assertIn(EMPTY_FORMAT, self._block())

    def test_the_table_never_mentions_matches(self) -> None:
        # The table is built from stage rows alone. Match counts and durations move
        # constantly during an event, and tracking them meant a rewrite per match.
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        for match in Match.objects.filter(tournament=self.tournament):
            match.duration_mins = 100
            match.save()

        block = self._block()
        for noise in ("game", "minute", "100"):
            self.assertNotIn(noise, block, f"table should not carry match data: {noise!r}")

    def test_writing_outside_the_markers_is_never_touched(self) -> None:
        self.tournament.rules = (self._rules() or "") + f"\n\n## Local notes\n\n{STAFF_NOTE}\n"
        self.tournament.save()

        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        rules = self._rules()
        self.assertIn(STAFF_NOTE, rules)
        # A structural heading, not a rules detail: this test is about the markers,
        # and should not need editing every time the WFDF ruleset is updated.
        self.assertIn("### Game Time, Time Outs, Scores", rules)
        self.assertIn("**Pool A**", rules)

    def test_rules_without_markers_are_left_completely_alone(self) -> None:
        # The opt-out, and what protects tournaments created before this existed.
        handwritten = "## Format\n\nWe do our own thing here.\n"
        self.tournament.rules = handwritten
        self.tournament.save()

        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        self.assertEqual(self._rules(), handwritten)

    def test_a_tournament_with_no_rules_at_all_is_not_given_any(self) -> None:
        self.tournament.rules = None
        self.tournament.save()

        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        self.tournament.refresh_from_db()
        self.assertIn(self.tournament.rules, (None, ""))

    def test_sync_reports_whether_it_changed_anything(self) -> None:
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        self.tournament.refresh_from_db()
        # Already in sync from the signal, so a second call is a no-op.
        self.assertFalse(sync_rules_format(self.tournament))

    def test_seeds_with_gaps_are_listed_rather_than_ranged(self) -> None:
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 3, 6, 8])
        self.assertIn("1, 3, 6, 8", self._block())

    def test_the_table_is_valid_markdown_with_a_row_per_stage(self) -> None:
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        build_pool(self.tournament, name="B", sequence_number=2, seeding=[5, 6, 7, 8])

        table = render_format_table(self.tournament)
        rows = [line for line in table.splitlines() if line.startswith("|")]
        self.assertEqual(len(rows), 4, "header, separator, and one row per pool")
        self.assertTrue(all(line.endswith("|") for line in rows))


LEGACY_TABLE = """| Stage            | Description                                                      |
| :--------------- | :--------------------------------------------------------------- |
| **Pool Games**   | 1-16 (4 Pools of 4). Re-seed within pools only. 75 minute games. |
| **Cross-Pool 1** | 1-4, 5-12, 13-16. 75 minute games.                               |
| **Bracket**      | 1-8, 9-16. Winner takes the higher seed. 100 minute games.       |"""

LEGACY_RULES = f"""# Format & Rules

## Format

{LEGACY_TABLE}

## Rules

### All games are played by WFDF 2021 rules
"""


class LegacyFormatUpgradeTests(TestCase):
    """`upgrade_legacy_format_block` — the backfill's decision, as a pure function."""

    def test_the_shipped_default_is_taken_over(self) -> None:
        upgraded = not_none(upgrade_legacy_format_block(LEGACY_RULES))
        self.assertIn(FORMAT_BLOCK_START, upgraded)
        self.assertIn(FORMAT_BLOCK_END, upgraded)
        self.assertNotIn("4 Pools of 4", upgraded)
        # Everything outside the table survives.
        self.assertIn("### All games are played by WFDF 2021 rules", upgraded)
        self.assertIn("# Format & Rules", upgraded)

    def test_an_edited_table_is_refused(self) -> None:
        edited = LEGACY_RULES.replace("4 Pools of 4", "3 Pools of 5")
        self.assertIsNone(upgrade_legacy_format_block(edited))

    def test_a_table_with_a_row_removed_is_refused(self) -> None:
        trimmed = "\n".join(
            line for line in LEGACY_RULES.splitlines() if "Cross-Pool 1" not in line
        )
        self.assertIsNone(upgrade_legacy_format_block(trimmed))

    def test_already_managed_rules_are_refused(self) -> None:
        managed = f"## Format\n\n{FORMAT_BLOCK_START}\nx\n{FORMAT_BLOCK_END}\n"
        self.assertIsNone(upgrade_legacy_format_block(managed))

    def test_rules_with_no_format_section_are_refused(self) -> None:
        self.assertIsNone(upgrade_legacy_format_block("## Rules\n\nJust rules.\n"))

    def test_a_format_section_with_no_table_is_refused(self) -> None:
        self.assertIsNone(upgrade_legacy_format_block("## Format\n\nWe play pools.\n\n## Rules\n"))

    def test_empty_and_missing_rules_are_refused(self) -> None:
        for value in (None, ""):
            self.assertIsNone(upgrade_legacy_format_block(value))

    def test_a_table_outside_the_format_section_is_ignored(self) -> None:
        # A stock-looking table under some other heading is not the format table.
        elsewhere = f"## Rules\n\n{LEGACY_TABLE}\n"
        self.assertIsNone(upgrade_legacy_format_block(elsewhere))

    def test_prose_around_the_table_survives(self) -> None:
        with_prose = LEGACY_RULES.replace(
            LEGACY_TABLE, f"Read this first.\n\n{LEGACY_TABLE}\n\nAnd this after."
        )
        upgraded = not_none(upgrade_legacy_format_block(with_prose))
        self.assertIn("Read this first.", upgraded)
        self.assertIn("And this after.", upgraded)
        self.assertIn(FORMAT_BLOCK_START, upgraded)

    def test_the_format_section_is_found_whatever_its_case(self) -> None:
        self.assertIsNotNone(
            upgrade_legacy_format_block(LEGACY_RULES.replace("## Format", "## FORMAT"))
        )

    def test_a_trailing_newline_is_preserved_either_way(self) -> None:
        with_newline = upgrade_legacy_format_block(LEGACY_RULES)
        without = upgrade_legacy_format_block(LEGACY_RULES.rstrip("\n"))
        with_newline = not_none(with_newline)
        without = not_none(without)
        self.assertTrue(with_newline.endswith("\n"))
        self.assertFalse(without.endswith("\n"))

    def test_upgrading_is_idempotent(self) -> None:
        once = not_none(upgrade_legacy_format_block(LEGACY_RULES))
        self.assertIsNone(upgrade_legacy_format_block(once))


class LegacyTournamentBackfillTests(RulesFormatTests):
    """End to end: a pre-existing tournament, upgraded, then kept in sync."""

    def _make_legacy(self, rules: str = LEGACY_RULES) -> None:
        self.tournament.rules = rules
        self.tournament.save()

    def test_an_upgraded_tournament_starts_tracking_its_stages(self) -> None:
        self._make_legacy()
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        # Still legacy, so the signal correctly did nothing.
        self.assertEqual(self._rules(), LEGACY_RULES)

        self.tournament.refresh_from_db()
        self.tournament.rules = upgrade_legacy_format_block(self.tournament.rules)
        self.tournament.save()
        sync_rules_format(self.tournament)

        block = self._block()
        self.assertIn("**Pool A**", block)
        self.assertNotIn("4 Pools of 4", self._rules())
        self.assertIn("### All games are played by WFDF 2021 rules", self._rules())

    def test_after_upgrading_later_stage_changes_flow_through(self) -> None:
        self._make_legacy()
        self.tournament.rules = upgrade_legacy_format_block(self.tournament.rules)
        self.tournament.save()

        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        self.assertIn("**Pool A**", self._block())

    def test_an_edited_legacy_tournament_is_never_touched(self) -> None:
        edited = LEGACY_RULES.replace("4 Pools of 4", "3 Pools of 5, our own way")
        self._make_legacy(edited)

        self.assertIsNone(upgrade_legacy_format_block(self.tournament.rules))
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        self.assertEqual(self._rules(), edited)


class RulesFormatEdgeCaseTests(RulesFormatTests):
    """Malformed markers, unusual stage shapes, and things that must NOT resync."""

    # --- marker handling ---

    def test_a_start_marker_with_no_end_is_left_alone(self) -> None:
        broken = f"## Format\n\n{FORMAT_BLOCK_START}\nhalf a block\n"
        self.tournament.rules = broken
        self.tournament.save()

        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        self.assertEqual(self._rules(), broken)

    def test_an_end_marker_with_no_start_is_left_alone(self) -> None:
        broken = f"## Format\n\nno opening marker\n{FORMAT_BLOCK_END}\n"
        self.tournament.rules = broken
        self.tournament.save()

        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        self.assertEqual(self._rules(), broken)

    def test_markers_in_the_wrong_order_are_left_alone(self) -> None:
        reversed_markers = f"{FORMAT_BLOCK_END}\nbackwards\n{FORMAT_BLOCK_START}\n"
        self.tournament.rules = reversed_markers
        self.tournament.save()

        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        self.assertEqual(self._rules(), reversed_markers)

    def test_an_empty_rules_string_is_left_alone(self) -> None:
        self.tournament.rules = ""
        self.tournament.save()

        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.rules, "")

    def test_only_the_first_marker_pair_is_managed(self) -> None:
        # A second pair is left as literal text rather than being silently merged
        # into the first — two managed blocks is a mistake worth staying visible.
        self.tournament.rules = (
            f"{FORMAT_BLOCK_START}\nfirst\n{FORMAT_BLOCK_END}\n\n"
            f"{FORMAT_BLOCK_START}\nsecond\n{FORMAT_BLOCK_END}\n"
        )
        self.tournament.save()

        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        rules = self._rules()
        self.assertIn("**Pool A**", rules)
        self.assertIn("second", rules)
        self.assertNotIn("first", rules)

    def test_text_on_the_same_line_as_a_marker_survives(self) -> None:
        self.tournament.rules = f"before {FORMAT_BLOCK_START}\nx\n{FORMAT_BLOCK_END} after"
        self.tournament.save()

        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        rules = self._rules()
        self.assertTrue(rules.startswith("before "))
        self.assertTrue(rules.endswith(" after"))

    # --- stage shapes ---

    def test_a_single_round_swiss_reads_in_the_singular(self) -> None:
        build_swiss_round(
            self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4], num_rounds=1
        )
        self.assertIn("1 round", self._block())
        self.assertNotIn("1 rounds", self._block())

    def test_a_cross_pool_appears_without_needing_its_matches(self) -> None:
        # A cross pool is created bare and given matches separately; its row must
        # not wait on them.
        CrossPool.objects.create(tournament=self.tournament)
        block = self._block()
        self.assertIn("**Cross-Pool**", block)
        self.assertIn("Winner takes the higher seed", block)

    def test_a_position_pool_appears_after_the_bracket(self) -> None:
        build_bracket(self.tournament, name="1-4", sequence_number=1)
        build_position_pool(self.tournament, name="A", sequence_number=2, seeding=[5, 6, 7, 8])

        block = self._block()
        self.assertIn("**Position Pool A**", block)
        self.assertLess(block.index("**Bracket 1-4**"), block.index("**Position Pool A**"))

    def test_a_tournament_with_no_teams_omits_the_team_count(self) -> None:
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        self.tournament.teams.clear()

        table = render_format_table(self.tournament)
        self.assertNotIn(" teams.", table)
        self.assertIn("Stages are listed in the order they are played.", table)

    def test_a_results_only_save_does_not_re_render_the_table(self) -> None:
        """Scoring saves a stage per result; the table cannot have changed."""
        pool = build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])

        rendered = 0
        real = rules_module.render_format_table

        def counting(tournament: Tournament) -> str:
            nonlocal rendered
            rendered += 1
            return real(tournament)

        with patch.object(rules_module, "render_format_table", counting):
            pool.results = {"1": {"rank": 1}}
            pool.save(update_fields=["results"])
        self.assertEqual(rendered, 0)

        # A field the table is built from still syncs.
        with patch.object(rules_module, "render_format_table", counting):
            pool.name = "B"
            pool.save(update_fields=["name"])
        self.assertEqual(rendered, 1)
        self.assertIn("Pool B", self._block())

    # --- one stage, one write ---

    def _rules_writes(self, fn: Callable[[], object]) -> int:
        """How many times `fn` rewrites the rules."""
        calls = 0
        real = rules_module.sync_rules_format

        def counting(tournament: Tournament) -> bool:
            nonlocal calls
            changed = real(tournament)
            calls += 1 if changed else 0
            return changed

        with patch.object(rules_module, "sync_rules_format", counting):
            fn()
        return calls

    def test_creating_one_pool_writes_the_rules_exactly_once(self) -> None:
        writes = self._rules_writes(
            lambda: build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        )
        self.assertEqual(writes, 1)

    def test_creating_one_swiss_group_writes_the_rules_exactly_once(self) -> None:
        writes = self._rules_writes(
            lambda: build_swiss_round(
                self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4], num_rounds=3
            )
        )
        self.assertEqual(writes, 1)

    def test_creating_one_bracket_writes_the_rules_exactly_once(self) -> None:
        writes = self._rules_writes(
            lambda: build_bracket(self.tournament, name="1-4", sequence_number=1)
        )
        self.assertEqual(writes, 1)

    def test_creating_one_position_pool_writes_the_rules_exactly_once(self) -> None:
        writes = self._rules_writes(
            lambda: build_position_pool(
                self.tournament, name="A", sequence_number=1, seeding=[5, 6, 7, 8]
            )
        )
        self.assertEqual(writes, 1)

    def test_a_full_setup_writes_once_per_stage_and_no_more(self) -> None:
        def setup() -> None:
            build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
            build_pool(self.tournament, name="B", sequence_number=2, seeding=[5, 6, 7, 8])
            build_bracket(self.tournament, name="1-4", sequence_number=3)

        self.assertEqual(self._rules_writes(setup), 3)

    def test_saving_matches_never_touches_the_rules(self) -> None:
        # Scores, times and durations all live on matches, and a live tournament
        # saves them constantly. None of it is format information any more.
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        before = self._rules()

        field = TournamentField.objects.filter(tournament=self.tournament).first()

        def churn() -> None:
            for hour, match in enumerate(
                Match.objects.filter(tournament=self.tournament).order_by("id"), start=9
            ):
                match.score_team_1, match.score_team_2 = 15, 9
                match.status = Match.Status.COMPLETED
                # Distinct slots: (tournament, time, field) is unique_together.
                match.time = parse_datetime(f"2026-08-01T{hour:02d}:00:00+00:00")
                match.field = field
                match.duration_mins = 100
                match.save()

        self.assertEqual(self._rules_writes(churn), 0)
        self.assertEqual(self._rules(), before)

    def test_deleting_a_stage_writes_once_despite_cascading_matches(self) -> None:
        pool = build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        build_pool(self.tournament, name="B", sequence_number=2, seeding=[5, 6, 7, 8])

        self.assertEqual(self._rules_writes(pool.delete), 1)

    # --- integrity ---

    def test_repeated_syncs_are_byte_identical(self) -> None:
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        build_bracket(self.tournament, name="1-4", sequence_number=2)
        first = self._rules()

        self.tournament.refresh_from_db()
        sync_rules_format(self.tournament)
        sync_rules_format(self.tournament)

        self.assertEqual(self._rules(), first)

    def test_syncing_does_not_clobber_a_concurrent_seeding_write(self) -> None:
        # sync saves with update_fields=["rules"], so a stale in-memory copy of the
        # tournament cannot write back an old seeding on top of a newer one.
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        stale = Tournament.objects.get(id=self.tournament.id)

        Tournament.objects.filter(id=self.tournament.id).update(status=Tournament.Status.LIVE)
        sync_rules_format(stale)

        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.status, Tournament.Status.LIVE)

    def test_deleting_the_tournament_does_not_raise(self) -> None:
        # Cascade delete fires post_delete for every stage and match after the
        # tournament row is gone.
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        build_bracket(self.tournament, name="1-4", sequence_number=2)

        self.tournament.delete()

        self.assertFalse(Tournament.objects.filter(event=self.event).exists())

    def test_the_rules_endpoint_still_lets_staff_overwrite_everything(self) -> None:
        # The managed block is a convention, not a lock: staff can still replace the
        # whole document, and doing so opts them out until they put markers back.
        build_pool(self.tournament, name="A", sequence_number=1, seeding=[1, 2, 3, 4])
        self.tournament.rules = "Ours now."
        self.tournament.save()

        build_bracket(self.tournament, name="1-4", sequence_number=2)

        self.assertEqual(self._rules(), "Ours now.")


NOTE = "The table above is maintained for you"


class FormatNoteVisibilityTests(TestCase):
    def test_the_shipped_default_hides_the_editing_note(self) -> None:
        rules = get_default_rules()
        start = rules.index(NOTE)
        commented = rules.rfind("<!--", 0, start) > rules.rfind("-->", 0, start)
        self.assertTrue(commented, "the editing note must not be published")
