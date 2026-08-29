import importlib.util
import os
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

_PATH = Path(__file__).resolve().parent.parent.parent / "scripts" / "check-scale.py"
_SPEC = importlib.util.spec_from_file_location("check_scale", _PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover
    raise RuntimeError(f"cannot load {_PATH}")
check_scale = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_scale)


class DecideTest(SimpleTestCase):
    def test_no_escalation_on_a_performance_profile(self) -> None:
        escalate, reason = check_scale.decide("performance", None, None)

        self.assertFalse(escalate)
        self.assertIn("performance", reason)

    def test_no_escalation_without_samples(self) -> None:
        self.assertEqual(False, check_scale.decide("shared", None, None)[0])
        self.assertEqual(False, check_scale.decide("shared", 100000.0, None)[0])
        self.assertEqual(False, check_scale.decide("shared", None, 100000.0)[0])

    def test_escalates_on_the_2026_08_28_drain(self) -> None:
        # First firing that day: the 2h window peaked at 56,010, five hours before
        # the first 504.
        escalate, reason = check_scale.decide("shared", 56010.0, 41134.0)

        self.assertTrue(escalate)
        self.assertIn("56010", reason)

    def test_does_not_escalate_on_a_deploy_dip(self) -> None:
        # 2026-08-20 bottomed at 9,983 but recovered inside 90 minutes, so the 2h
        # window still contains a healthy reading. Depth alone would have fired.
        escalate, _ = check_scale.decide("shared", 100000.0, 9983.0)

        self.assertFalse(escalate)

    def test_floor_is_a_backstop_for_a_faster_drain(self) -> None:
        escalate, reason = check_scale.decide("shared", 100000.0, 4999.0)

        self.assertTrue(escalate)
        self.assertIn("floor", reason)

    def test_healthy_balance_does_not_escalate(self) -> None:
        escalate, reason = check_scale.decide("shared", 200000.0, 199837.0)

        self.assertFalse(escalate)
        self.assertIn("healthy", reason)


class HttpErrorMessageTest(SimpleTestCase):
    def test_403_explains_the_token_scope(self) -> None:
        message = check_scale.http_error_message(403, b"Forbidden")

        self.assertIn("403", message)
        self.assertIn("FLY_METRICS_TOKEN", message)
        self.assertIn("Forbidden", message)

    def test_other_codes_carry_no_token_hint(self) -> None:
        message = check_scale.http_error_message(500, b"boom")

        self.assertNotIn("FLY_METRICS_TOKEN", message)
        self.assertIn("boom", message)

    def test_empty_body_leaves_no_trailing_space(self) -> None:
        message = check_scale.http_error_message(502, b"   ")

        self.assertEqual(message, message.rstrip())


class EmitTest(SimpleTestCase):
    def _emit_to_file(self, escalate: bool, reason: str) -> str:
        with tempfile.NamedTemporaryFile("w+", delete=False) as handle:
            path = handle.name
        try:
            with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": path}):
                check_scale._emit(escalate, reason)
            return Path(path).read_text()
        finally:
            Path(path).unlink()

    def test_writes_github_output(self) -> None:
        contents = self._emit_to_file(True, "drain detected")

        self.assertIn("escalate=true\n", contents)
        self.assertIn("reason=drain detected\n", contents)

    def test_writes_lowercase_false(self) -> None:
        self.assertIn("escalate=false\n", self._emit_to_file(False, "healthy"))

    def test_without_github_output_it_only_prints(self) -> None:
        with mock.patch.dict(os.environ, clear=False) as env:
            env.pop("GITHUB_OUTPUT", None)
            check_scale._emit(False, "healthy")


class CurrentCpuKindTest(SimpleTestCase):
    def test_reads_the_live_fly_toml(self) -> None:
        # Guards the field path into fly.toml.
        self.assertIn(check_scale._current_cpu_kind(), {"shared", "performance"})


class MainTest(SimpleTestCase):
    def test_exits_when_no_token_is_set(self) -> None:
        with mock.patch.dict(os.environ, clear=False) as env:
            env.pop("FLY_METRICS_TOKEN", None)
            env.pop("FLY_API_TOKEN", None)

            with self.assertRaises(SystemExit) as caught:
                check_scale.main()

        self.assertIn("FLY_METRICS_TOKEN", str(caught.exception))
