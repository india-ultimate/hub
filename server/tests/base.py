import datetime
import random
import string
from typing import Any

from django.test import TestCase
from django.utils.timezone import now

from server.models import (
    Event,
    Match,
    Player,
    Pool,
    Team,
    Tournament,
    UCPerson,
    UCRegistration,
    User,
)


def fake_id(n: int) -> str:
    choices = string.digits + string.ascii_letters
    return "".join(random.choice(choices) for _ in range(n))  # noqa: S311


def fake_order(amount: int) -> dict[str, Any]:
    order_id = f"order_{fake_id(16)}"
    return {
        "order_id": order_id,
        "amount": amount,
        "currency": "INR",
        "receipt": "78e1cdbe:2023-06-01:1689402191",
        "key": "rzp_test_2wH8PYPLML64BA",
        "name": "India Ultimate Hub",
        "image": "https://d36m266ykvepgv.cloudfront.net/uploads/media/o4G97mT9vR/s-448-250/upai-2.png",
        "description": "Membership for ",
        "prefill": {"name": "", "email": "username@foo.com", "contact": ""},
    }


def create_player(user: User) -> Player:
    return Player.objects.create(user=user, date_of_birth=now().date())


def create_event(title: str) -> Event:
    today = now()
    days = random.randint(30, 100)  # noqa: S311
    start = (datetime.timedelta(days=days) + today).date()
    end = (datetime.timedelta(days=days + 2) + today).date()
    return Event.objects.create(title=title, start_date=start, end_date=end)


def add_teams_to_event(event: Event, no_of_teams: int) -> list[Team]:
    teams = []
    for i in range(1, no_of_teams + 1):
        team = Team.objects.create(name="Team " + str(i), ultimate_central_id=i)
        teams.append(team)

    person = UCPerson.objects.create(email="john@gmail.com", slug="john")

    for team in teams:
        UCRegistration.objects.create(
            event=event, team=team, person=person, roles=["admin", "player"]
        )

    return teams


def create_tournament(event: Event) -> Tournament:
    tournament = Tournament.objects.create(event=event)

    team_list = UCRegistration.objects.filter(event=event).values_list("team", flat=True).distinct()
    for team_id in team_list:
        tournament.teams.add(team_id)

    tournament.refresh_from_db()
    return tournament


def create_pool(name: str, tournament: Tournament, seeding: list[int]) -> Pool:
    pool_seeding = {}
    pool_results = {}
    for i, seed in enumerate(seeding):
        team_id = tournament.initial_seeding[str(seed)]

        pool_seeding[seed] = team_id
        pool_results[team_id] = {
            "rank": i + 1,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "GF": 0,  # Goals For
            "GA": 0,  # Goals Against
        }

    pool = Pool(
        sequence_number=1,
        name=name,
        tournament=tournament,
        initial_seeding=dict(sorted(pool_seeding.items())),
        results=pool_results,
    )
    pool.save()

    pool_seeding_list = list(map(int, pool.initial_seeding.keys()))

    for i, x in enumerate(pool_seeding_list):
        for _j, y in enumerate(pool_seeding_list[i + 1 :], i + 1):
            match = Match(
                tournament=tournament,
                pool=pool,
                sequence_number=1,
                placeholder_seed_1=x,
                placeholder_seed_2=y,
            )

            match.save()

    return pool


def start_tournament(tournament: Tournament) -> None:
    matches = Match.objects.filter(tournament=tournament).exclude(pool__isnull=True)

    for match in matches:
        team_1_id = tournament.initial_seeding[str(match.placeholder_seed_1)]
        team_2_id = tournament.initial_seeding[str(match.placeholder_seed_2)]

        team_1 = Team.objects.get(id=team_1_id)
        team_2 = Team.objects.get(id=team_2_id)

        match.team_1 = team_1
        match.team_2 = team_2
        match.status = Match.Status.SCHEDULED

        match.save()

    tournament.status = Tournament.Status.LIVE
    tournament.save()


class ApiBaseTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.username = "username@foo.com"
        self.password = "password"
        self.user = user = User.objects.create(
            username=self.username, email=self.username, first_name="John", last_name="Williamson"
        )
        user.set_password(self.password)
        user.save()
        person = UCPerson.objects.create(email=self.username, slug="username")
        self.player = Player.objects.create(
            user=self.user, date_of_birth="1990-01-01", ultimate_central_id=person.id
        )
        self.player.refresh_from_db()
        self.event = create_event("NCS Sectionals 2023")
        self.teams = add_teams_to_event(self.event, 14)
        UCRegistration.objects.create(
            event=self.event, team=self.teams[0], person=person, roles=["admin", "player"]
        )
        self.tournament = create_tournament(self.event)
