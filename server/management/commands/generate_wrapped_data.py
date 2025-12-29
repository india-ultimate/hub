from datetime import date, datetime
from typing import Any, cast

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q

from server.core.models import Player
from server.tournament.models import (
    Event,
    Match,
    MatchEvent,
    MatchStats,
    Registration,
    Tournament,
)
from server.wrapped.models import PlayerWrapped


class Command(BaseCommand):
    help = "Generate year-end wrapped data for all players for specified years"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--years",
            nargs="+",
            type=int,
            default=[2024, 2025],
            help="Years to generate wrapped data for (default: 2024 2025)",
        )
        parser.add_argument(
            "--player-id",
            type=int,
            default=None,
            help="Generate wrapped data for a specific player only",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force regenerate even if wrapped data already exists",
        )

    def get_year_date_range(self, year: int) -> tuple[date, date]:
        """Get start and end dates for a year."""
        return date(year, 1, 1), date(year, 12, 31)

    def get_tournaments_for_year(self, year: int) -> list[Tournament]:
        """Get all tournaments that occurred in the given year."""
        start_date, end_date = self.get_year_date_range(year)
        events = Event.objects.filter(Q(start_date__year=year) | Q(end_date__year=year)).distinct()
        tournaments = Tournament.objects.filter(event__in=events).distinct()
        return list(tournaments)

    def get_player_tournaments(self, player: Player, year: int) -> list[Tournament]:
        """Get tournaments where player was registered."""
        start_date, end_date = self.get_year_date_range(year)
        registrations = Registration.objects.filter(
            player=player,
            event__start_date__lte=end_date,
            event__end_date__gte=start_date,
        )
        tournaments = Tournament.objects.filter(
            event__in=[reg.event for reg in registrations]
        ).distinct()
        return list(tournaments)

    def get_player_matches(self, player: Player, year: int) -> list[Match]:
        """Get all matches where player participated in the given year."""
        tournaments = self.get_player_tournaments(player, year)
        if not tournaments:
            return []

        # Get registrations for each tournament to know which team player was on
        registrations = Registration.objects.filter(
            player=player,
            event__tournament__in=tournaments,
        ).select_related("team", "event")

        # Build a map of tournament -> team for this player
        tournament_team_map = {}
        for reg in registrations:
            try:
                tournament = Tournament.objects.get(event=reg.event)
                tournament_team_map[tournament.id] = reg.team
            except Tournament.DoesNotExist:
                continue

        # Get matches where player's team played in each specific tournament
        all_matches: list[Match] = []
        for tournament_id, team in tournament_team_map.items():
            matches = (
                Match.objects.filter(
                    tournament_id=tournament_id,
                    time__year=year,
                )
                .filter(Q(team_1=team) | Q(team_2=team))
                .distinct()
            )
            all_matches.extend(list(matches))

        # Remove duplicates and sort by time
        unique_matches = {match.id: match for match in all_matches}.values()
        matches_with_time = [m for m in unique_matches if m.time is not None]
        return sorted(
            matches_with_time,
            key=lambda m: cast(datetime, m.time),
        )

    def get_player_games_count(self, player: Player, year: int) -> int:
        """Get count of distinct games where player participated (based on registrations only)."""
        matches = self.get_player_matches(player, year)
        return len(matches)

    def calculate_streak(self, player: Player, year: int) -> int:
        """Calculate longest continuous streak of games where player scored or assisted."""
        tournaments = self.get_player_tournaments(player, year)
        if not tournaments:
            return 0

        # Get all matches for this player in chronological order
        matches = self.get_player_matches(player, year)
        if not matches:
            return 0

        # Sort all matches by time (chronological order)
        matches_with_time = [m for m in matches if m.time is not None]
        matches_sorted = sorted(
            matches_with_time,
            key=lambda m: cast(datetime, m.time),
        )

        if not matches_sorted:
            return 0

        # Get all match events where player scored or assisted
        match_stats = MatchStats.objects.filter(
            match__tournament__in=tournaments,
            match__time__year=year,
        )
        scored_or_assisted_matches = (
            MatchEvent.objects.filter(
                stats__in=match_stats,
            )
            .filter(
                Q(scored_by=player) | Q(assisted_by=player),
            )
            .values_list("stats__match_id", flat=True)
            .distinct()
        )

        match_ids_with_action = set(scored_or_assisted_matches)

        # Find longest streak in chronological order
        max_streak = 0
        current_streak = 0

        for match in matches_sorted:
            if match.id in match_ids_with_action:
                # Player scored or assisted in this match
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                # Streak broken
                current_streak = 0

        return max_streak

    def get_tournament_best(
        self, player: Player, year: int, event_type: str
    ) -> dict[str, Any] | None:
        """Get tournament with most scores/assists/blocks for player."""
        tournaments = self.get_player_tournaments(player, year)
        if not tournaments:
            return None

        match_stats = MatchStats.objects.filter(match__tournament__in=tournaments)
        match_events = MatchEvent.objects.filter(stats__in=match_stats)

        if event_type == "scores":
            events = match_events.filter(scored_by=player, type=MatchEvent.EventType.SCORE)
        elif event_type == "assists":
            events = match_events.filter(assisted_by=player, type=MatchEvent.EventType.SCORE)
        elif event_type == "blocks":
            events = match_events.filter(block_by=player, type=MatchEvent.EventType.BLOCK)
        else:
            return None

        # Count by tournament
        tournament_counts: dict[int, int] = {}
        for event in events:
            tournament = event.stats.tournament
            tournament_counts[tournament.id] = tournament_counts.get(tournament.id, 0) + 1

        if not tournament_counts:
            return None

        # Get tournament with max count
        max_tournament_id = max(tournament_counts, key=lambda k: tournament_counts[k])
        max_tournament = Tournament.objects.get(id=max_tournament_id)

        return {
            "tournament_name": max_tournament.event.title,
            "tournament_id": max_tournament.id,
            "count": tournament_counts[max_tournament_id],
        }

    def get_teams_played_for(self, player: Player, year: int) -> list[dict[str, Any]]:
        """Get list of teams player played for with tournament counts."""
        registrations = Registration.objects.filter(
            player=player,
            event__start_date__year=year,
        ).select_related("team", "event")

        # Group by team and count distinct tournaments
        team_tournament_map: dict[int, dict[str, Any]] = {}
        for reg in registrations:
            team_id = reg.team.id
            if team_id not in team_tournament_map:
                team_tournament_map[team_id] = {
                    "team_name": reg.team.name,
                    "team_id": team_id,
                    "tournament_ids": set[int](),
                }
            # Get tournament for this event
            try:
                tournament = Tournament.objects.get(event=reg.event)
                tournament_ids = cast(set[int], team_tournament_map[team_id]["tournament_ids"])
                tournament_ids.add(tournament.id)
            except Tournament.DoesNotExist:
                continue

        # Convert to final format
        result: list[dict[str, Any]] = []
        for team_data in team_tournament_map.values():
            tournament_ids = cast(set[int], team_data["tournament_ids"])
            result.append(
                {
                    "team_name": cast(str, team_data["team_name"]),
                    "team_id": cast(int, team_data["team_id"]),
                    "tournament_count": len(tournament_ids),
                }
            )

        return result

    def get_top_teammates_i_assisted(self, player: Player, year: int) -> list[dict[str, Any]]:
        """Get top 5 teammates I assisted."""
        tournaments = self.get_player_tournaments(player, year)
        if not tournaments:
            return []

        match_stats = MatchStats.objects.filter(match__tournament__in=tournaments)
        assists = MatchEvent.objects.filter(
            stats__in=match_stats,
            assisted_by=player,
            type=MatchEvent.EventType.SCORE,
            scored_by__isnull=False,
        )

        teammate_counts: dict[int, dict[str, Any]] = {}
        for assist in assists:
            if assist.scored_by and assist.scored_by != player:
                teammate_id = assist.scored_by.id
                if teammate_id not in teammate_counts:
                    teammate_counts[teammate_id] = {
                        "player_name": assist.scored_by.user.get_full_name(),
                        "player_id": teammate_id,
                        "count": 0,
                    }
                teammate_counts[teammate_id]["count"] = (
                    cast(int, teammate_counts[teammate_id]["count"]) + 1
                )

        sorted_teammates = sorted(
            teammate_counts.values(), key=lambda x: cast(int, x["count"]), reverse=True
        )
        return sorted_teammates[:5]

    def get_top_teammates_who_assisted_me(self, player: Player, year: int) -> list[dict[str, Any]]:
        """Get top 5 teammates who assisted me."""
        tournaments = self.get_player_tournaments(player, year)
        if not tournaments:
            return []

        match_stats = MatchStats.objects.filter(match__tournament__in=tournaments)
        assists = MatchEvent.objects.filter(
            stats__in=match_stats,
            scored_by=player,
            type=MatchEvent.EventType.SCORE,
            assisted_by__isnull=False,
        )

        teammate_counts: dict[int, dict[str, Any]] = {}
        for assist in assists:
            if assist.assisted_by and assist.assisted_by != player:
                teammate_id = assist.assisted_by.id
                if teammate_id not in teammate_counts:
                    teammate_counts[teammate_id] = {
                        "player_name": assist.assisted_by.user.get_full_name(),
                        "player_id": teammate_id,
                        "count": 0,
                    }
                teammate_counts[teammate_id]["count"] = (
                    cast(int, teammate_counts[teammate_id]["count"]) + 1
                )

        sorted_teammates = sorted(
            teammate_counts.values(), key=lambda x: cast(int, x["count"]), reverse=True
        )
        return sorted_teammates[:5]

    def generate_wrapped_data(
        self, player: Player, year: int, force: bool = False
    ) -> PlayerWrapped | None:
        """Generate wrapped data for a single player for a given year."""
        # Check if already exists
        if not force:
            try:
                existing = PlayerWrapped.objects.get(player=player, year=year)
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {player.user.get_full_name()} - {year} (already exists)"
                    )
                )
                return existing
            except PlayerWrapped.DoesNotExist:
                pass

        self.stdout.write(f"Generating wrapped data for {player.user.get_full_name()} - {year}...")

        # Get tournaments
        tournaments = self.get_player_tournaments(player, year)
        tournaments_played = len(tournaments)

        # Get matches and match events
        match_stats = MatchStats.objects.filter(
            match__tournament__in=tournaments,
            match__time__year=year,
        )

        # Calculate statistics
        total_games = self.get_player_games_count(player, year)
        total_scores = MatchEvent.objects.filter(
            stats__in=match_stats,
            scored_by=player,
            type=MatchEvent.EventType.SCORE,
        ).count()
        total_assists = MatchEvent.objects.filter(
            stats__in=match_stats,
            assisted_by=player,
            type=MatchEvent.EventType.SCORE,
        ).count()
        total_blocks = MatchEvent.objects.filter(
            stats__in=match_stats,
            block_by=player,
            type=MatchEvent.EventType.BLOCK,
        ).count()

        # Get MVP and MSP counts
        # Check spirit_score_team_1, spirit_score_team_2, self_spirit_score_team_1, self_spirit_score_team_2
        matches = Match.objects.filter(
            tournament__in=tournaments,
            time__year=year,
        ).select_related(
            "spirit_score_team_1",
            "spirit_score_team_2",
            "self_spirit_score_team_1",
            "self_spirit_score_team_2",
        )

        mvp_matches = set()
        msp_matches = set()

        for match in matches:
            # Check all spirit score fields for MVP/MSP
            for spirit_score_field in [
                match.spirit_score_team_1,
                match.spirit_score_team_2,
                match.self_spirit_score_team_1,
                match.self_spirit_score_team_2,
            ]:
                if spirit_score_field:
                    if spirit_score_field.mvp_v2 == player:
                        mvp_matches.add(match.id)
                    if spirit_score_field.msp_v2 == player:
                        msp_matches.add(match.id)

        match_mvps = len(mvp_matches)
        match_msps = len(msp_matches)

        # Calculate streak
        continuous_streak = self.calculate_streak(player, year)

        # Tournament bests
        most_scores = self.get_tournament_best(player, year, "scores")
        most_assists = self.get_tournament_best(player, year, "assists")
        most_blocks = self.get_tournament_best(player, year, "blocks")

        # Teams played for
        teams_played_for = self.get_teams_played_for(player, year)

        # Teammate statistics
        top_teammates_i_assisted = self.get_top_teammates_i_assisted(player, year)
        top_teammates_who_assisted_me = self.get_top_teammates_who_assisted_me(player, year)

        # Create or update wrapped data
        wrapped_data, created = PlayerWrapped.objects.update_or_create(
            player=player,
            year=year,
            defaults={
                "tournaments_played": tournaments_played,
                "total_games": total_games,
                "total_scores": total_scores,
                "total_assists": total_assists,
                "total_blocks": total_blocks,
                "match_mvps": match_mvps,
                "match_msps": match_msps,
                "continuous_streak_scored_or_assisted": continuous_streak,
                "most_scores_in_tournament": most_scores or {},
                "most_assists_in_tournament": most_assists or {},
                "most_blocks_in_tournament": most_blocks or {},
                "teams_played_for": teams_played_for,
                "top_teammates_i_assisted": top_teammates_i_assisted,
                "top_teammates_who_assisted_me": top_teammates_who_assisted_me,
            },
        )

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"{action} wrapped data for {player.user.get_full_name()} - {year}")
        )

        return wrapped_data

    def handle(self, *args: Any, **options: Any) -> None:
        years = options["years"]
        player_id = options.get("player_id")
        force = options.get("force", False)

        if player_id:
            try:
                players = [Player.objects.get(id=player_id)]
            except Player.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Player with ID {player_id} not found"))
                return
        else:
            players = list(Player.objects.all())

        total_players = len(players)
        self.stdout.write(
            f"Generating wrapped data for {total_players} players for years {years}..."
        )

        for year in years:
            self.stdout.write(f"\n=== Processing year {year} ===")
            for player in players:
                try:
                    self.generate_wrapped_data(player, year, force=force)
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error generating wrapped data for {player.user.get_full_name()} - {year}: {e!s}"
                        )
                    )
                    continue

        self.stdout.write(self.style.SUCCESS("\nCompleted generating wrapped data!"))
