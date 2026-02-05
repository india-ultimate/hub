import re
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib import messages
from django.core.management import call_command
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from server.core.models import Team
from server.series.models import Series
from server.tournament.models import Event

OUTPUT_MAX_LENGTH = 2000

# Strip ANSI escape sequences (e.g. [31;1m) from command output for browser display
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def csv_imports_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        action = request.POST.get("action")
        csv_file = request.FILES.get("csv_file")

        if not action or action not in (
            "import_players",
            "activate_memberships",
            "add_to_series_roster",
            "add_to_event_roster",
        ):
            messages.error(request, "Invalid action.")
            return redirect("admin:csv_imports")

        if not csv_file:
            messages.error(request, "Please upload a CSV file.")
            return redirect("admin:csv_imports")

        if not (csv_file.name or "").lower().endswith(".csv"):
            messages.error(request, "File must be a CSV.")
            return redirect("admin:csv_imports")

        if action == "add_to_series_roster":
            series_id = request.POST.get("series_id")
            team_id = request.POST.get("team_id")
            if not series_id or not team_id:
                messages.error(request, "Series ID and Team ID are required.")
                return redirect("admin:csv_imports")

        if action == "add_to_event_roster":
            event_id = request.POST.get("event_id")
            team_id = request.POST.get("team_id")
            if not event_id or not team_id:
                messages.error(request, "Event ID and Team ID are required.")
                return redirect("admin:csv_imports")

        out = StringIO()
        err = StringIO()
        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp:
                tmp_path = tmp.name  # set immediately so finally can clean up on any exception
                for chunk in csv_file.chunks():
                    tmp.write(chunk)

            if action == "import_players":
                date_format = request.POST.get("date_format") or "%Y-%m-%d"
                guardian_email_optional = request.POST.get("guardian_email_optional") == "on"
                call_command(
                    "import_players",
                    tmp_path,
                    date_format=date_format,
                    guardian_email_optional=guardian_email_optional,
                    stdout=out,
                    stderr=err,
                )
            elif action == "activate_memberships":
                call_command("activate_memberships", tmp_path, stdout=out, stderr=err)
            elif action == "add_to_series_roster":
                call_command(
                    "add_to_series_roster",
                    tmp_path,
                    series_id=request.POST.get("series_id"),
                    team_id=request.POST.get("team_id"),
                    stdout=out,
                    stderr=err,
                )
            elif action == "add_to_event_roster":
                call_command(
                    "add_to_event_roster",
                    tmp_path,
                    event_id=request.POST.get("event_id"),
                    team_id=request.POST.get("team_id"),
                    stdout=out,
                    stderr=err,
                )

            err_content = _strip_ansi(err.getvalue())
            if err_content:
                msg = err_content[:OUTPUT_MAX_LENGTH]
                if len(err_content) > OUTPUT_MAX_LENGTH:
                    msg += "\n... (output truncated)"
                messages.error(request, msg)
            else:
                out_content = _strip_ansi(out.getvalue())
                msg = "Command completed successfully."
                if out_content:
                    msg += "\n" + out_content[:OUTPUT_MAX_LENGTH]
                    if len(out_content) > OUTPUT_MAX_LENGTH:
                        msg += "\n... (output truncated)"
                messages.success(request, msg)

        except Exception as e:
            messages.error(request, f"Error: {e}")
        finally:
            if tmp_path and Path(tmp_path).exists():
                Path(tmp_path).unlink(missing_ok=True)

        return redirect("admin:csv_imports")

    context = {
        "title": "CSV import tools",
        "series_list": Series.objects.all().order_by("name"),
        "team_list": Team.objects.all().order_by("name"),
        "event_list": Event.objects.all().order_by("title"),
    }
    return render(request, "admin/csv_imports.html", context)
