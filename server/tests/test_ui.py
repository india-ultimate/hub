import datetime
import os
import random

import pytest
from django.utils.timezone import now
from seleniumbase import BaseCase

from server.models import Event, Player, User
from server.tests.localserver import running_test_server
from server.tests.utils import zulip_get_email_link


def create_login_user() -> tuple[str, str, int]:
    username = "jagdeep@indiaultimate.org"
    password = "password"
    user = User.objects.create(
        username=username, email=username, first_name="Jagdeep", last_name="Chatterjee"
    )
    user.set_password(password)
    user.save()
    return username, password, user.id


def get_zulip_stream_email() -> str:
    return os.environ["ZULIP_STREAM_EMAIL"]


def create_email_link_user() -> tuple[str, int]:
    username = get_zulip_stream_email()
    user = User.objects.create(
        username=username, email=username, first_name="Jagdeep", last_name="Chatterjee"
    )
    return username, user.id


def create_event(title: str) -> Event:
    today = now()
    days = random.randint(30, 100)  # noqa: S311
    start = (datetime.timedelta(days=days) + today).date()
    end = (datetime.timedelta(days=days + 2) + today).date()
    return Event.objects.create(title=title, start_date=start, end_date=end)


@pytest.mark.django_db(transaction=True)
class TestIntegration(BaseCase):
    def test_new_user_login(self) -> None:
        username, password, user_id = create_login_user()
        names = ["NCS 23-24 SW Sectionals (Bangalore)", "NCS 23-24 North Sectionals (Delhi)"]
        for name in names:
            create_event(name)

        with running_test_server() as base_url:
            self.open(base_url)
            self.click('a[href="/login"]')
            self.click("button#password-tab")
            self.type("input#username-input", username)
            self.type("input#password-input", f"{password}\n")
            self.assert_element("h2#accordion-heading-actions")
            self.assert_element('a[href="/registration/me"]')
            print("Successfully logged in!")

            self.click('a[href="/registration/me"]')
            self.type("input#first_name", "Jagdeep")
            self.type("input#last_name", "Chatterjee")
            self.type("input#date_of_birth", "2008-01-01")
            self.assert_element("div#date_of_birth-error")
            self.type("input#date_of_birth", "1985-10-01")
            self.select_option_by_text("select#gender", "Male")
            self.type("input#phone", "+919876543210")
            self.select_option_by_text("select#occupation", "Government")
            self.type("input#city", "Bengaluru")
            self.select_option_by_text("select#state_ut", "Karnataka")
            self.assert_element('button:contains("Submit")')
            self.save_screenshot_to_logs("form.png")

            self.click('button:contains("Submit")')
            self.assert_text("Successful Registration")
            player_id = Player.objects.get(user_id=user_id).id

            self.assert_element(f'a[href="/edit/registration/{player_id}"] svg')
            self.assert_element(f'a[href="/vaccination/{player_id}"]')
            self.assert_element(f'a[href="/uc-login/{player_id}"]')
            self.assert_element(f'a[href="/membership/{player_id}"]')
            self.assert_element(f'a[href="/waiver/{player_id}"]')
            print("Successfully registered!")

            self.click(f'a[href="/membership/{player_id}"]')
            self.js_click("div.my-2 label div")
            self.click("select#event")
            self.assert_element("select#event option")
            self.check_if_unchecked("input")
            self.assert_element('button:contains("Pay")')
            self.click('button:contains("Pay")')

            self.type("input#transaction-id", "blah-blah\n")
            self.save_screenshot_to_logs("pay-clicked.png")

            self.click(f'a[href="/vaccination/{player_id}"]', timeout=60)
            self.select_option_by_text("select#name", "Covishield")
            self.choose_file("input#certificate", "frontend/assets/favico.png")
            self.click('button:contains("Submit")')
            self.click("div#root section div")
            self.click(f'a[href="/waiver/{player_id}"]')
            self.js_click("input#waiver")
            self.js_click("input#legal")
            self.click('button:contains("I Agree")')

            self.click('a[href="/dashboard"]')
            self.assert_element("div#accordion-body-player div div table tbody tr:nth-of-type(7)")
            self.assert_element("div#accordion-body-player div div table tbody tr:nth-of-type(8)")
            self.assert_element("div#accordion-body-player div div table tbody tr:nth-of-type(9)")

            self.click("h2#accordion-heading-transactions")
            self.assert_element("h2#accordion-heading-transactions")

    @pytest.mark.skipif(not os.environ.get("ZULIP_SITE"), reason="no zulip configuration found")
    def test_login_with_email(self) -> None:
        username, user_id = create_email_link_user()

        with running_test_server() as base_url:
            self.open(base_url)
            self.click('a[href="/login"]')
            self.click("button#email-link-tab")
            self.type("input#email-link-input", username)
            self.click("div#email-link form div button")

            signin_url = zulip_get_email_link()
            self.open(signin_url)
            self.click("form div button")

            self.assert_text("Welcome Jagdeep Chatterjee")

    @pytest.mark.skipif(not os.environ.get("ZULIP_SITE"), reason="no zulip configuration found")
    def test_signup_with_email(self) -> None:
        username = get_zulip_stream_email()
        with running_test_server() as base_url:
            self.open(base_url)
            self.click('a[href="/login"]')
            self.click("button#email-link-tab")
            self.type("input#email-link-input", username)
            self.click("div#email-link form div button")

            signin_url = zulip_get_email_link()
            self.open(signin_url)
            self.click("form div button")

            self.type("input#first_name", "Jagdeep")
            self.type("input#last_name", "Chatterjee")
            self.type("input#phone", "+919876543210\n")

            self.assert_text("Welcome Jagdeep Chatterjee")
            self.click('a[href="/registration/me"]')

            self.assert_text("Jagdeep", "input#first_name")
            self.assert_text("Chatterjee", "input#last_name")
            self.assert_text("+919876543210", "input#phone")

            self.click('a[href="/dashboard"]')
            self.click('a[href="/registration/ward"]')
            self.assert_text("", "input#first_name")
            self.assert_text("", "input#last_name")
