from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from server.core.models import User
from server.tournament_agent.catalog import is_allowed_model
from server.tournament_agent.evals import recommend_default, write_scorecard
from server.tournament_agent.evals.runner import run_suite


def _ensure_opencode_key_from_dotenv() -> None:
    """Load OPENCODE_GO_API_KEY from .env if not already in the process env."""
    if settings.OPENCODE_GO_API_KEY or os.environ.get("OPENCODE_GO_API_KEY"):
        return
    env_path = Path(settings.BASE_DIR) / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() != "OPENCODE_GO_API_KEY":
            continue
        value = value.strip().strip("'").strip('"')
        if value:
            os.environ["OPENCODE_GO_API_KEY"] = value
            settings.OPENCODE_GO_API_KEY = value
        break


class Command(BaseCommand):
    help = "Bake off tournament agent models on the capability/regression eval suite"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--models",
            type=str,
            default=(
                "kimi-k2.7-code,deepseek-v4-pro,glm-5.2,qwen3.7-plus,minimax-m3"
            ),
            help="Comma-separated model ids from the curated allowlist",
        )
        parser.add_argument(
            "--suite",
            type=str,
            default="capability",
            choices=["capability", "regression"],
        )
        parser.add_argument("--trials", type=int, default=3)
        parser.add_argument(
            "--out",
            type=str,
            default="latest_logs/agent_bakeoff",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="Staff user id to own sessions (defaults to first staff user)",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        _ensure_opencode_key_from_dotenv()
        if not settings.OPENCODE_GO_API_KEY:
            raise CommandError(
                "OPENCODE_GO_API_KEY is required for bakeoff "
                "(export it or add it to .env)"
            )

        model_ids = [m.strip() for m in options["models"].split(",") if m.strip()]
        for mid in model_ids:
            if not is_allowed_model(mid):
                raise CommandError(f"Model not in allowlist: {mid}")

        if options["user_id"]:
            user = User.objects.get(id=options["user_id"], is_staff=True)
        else:
            maybe_user = User.objects.filter(is_staff=True).order_by("id").first()
            if maybe_user is None:
                raise CommandError("No staff user found; pass --user-id")
            user = maybe_user

        results = {}
        for mid in model_ids:
            self.stdout.write(f"Running suite={options['suite']} model={mid} …")
            results[mid] = run_suite(
                model_id=mid,
                tier=options["suite"],
                trials=options["trials"],
                user=user,
            )
            self.stdout.write(
                f"  score={results[mid]['suite_score']:.1f} "
                f"pass^k={results[mid]['pass_hat_k']:.0%}"
            )
            fails = [c for c in results[mid]["cases"] if not c["passed"]]
            if fails:
                sample = fails[0]
                self.stdout.write(
                    f"  sample fail {sample['case_id']}: "
                    f"notes={sample.get('notes')} "
                    f"preview={(sample.get('response_preview') or '')[:160]!r}"
                )

        out_dir = Path(options["out"])
        write_scorecard(out_dir, results)
        best = recommend_default(results)
        self.stdout.write(self.style.SUCCESS(f"Wrote {out_dir}/scorecard.md"))
        self.stdout.write(self.style.SUCCESS(f"Recommended default: {best}"))
