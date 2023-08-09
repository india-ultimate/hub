import random
import string
from typing import Any

from django.test import TestCase
from django.utils.timezone import now

from server.models import Player, User


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
        "name": "UPAI Hub",
        "image": "https://d36m266ykvepgv.cloudfront.net/uploads/media/o4G97mT9vR/s-448-250/upai-2.png",
        "description": "Membership for ",
        "prefill": {"name": "", "email": "username@foo.com", "contact": ""},
    }


def create_player(user: User) -> Player:
    return Player.objects.create(user=user, date_of_birth=now().date())


class ApiBaseTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.username = "username@foo.com"
        self.password = "password"
        self.user = user = User.objects.create(username=self.username, email=self.username)
        user.set_password(self.password)
        user.save()
        self.player = Player.objects.create(user=self.user, date_of_birth="1990-01-01")
        self.player.refresh_from_db()
