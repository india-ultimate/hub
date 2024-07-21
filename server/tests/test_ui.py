import datetime
import os
import random

import pytest
from django.utils.timezone import now
from seleniumbase import BaseCase

from hub.settings import BASE_DIR
from server.models import Event, Player, User
from server.tests.localserver import running_test_server
from server.tests.utils import create_empty_directory, get_otp_from_email_logs


def create_login_user() -> tuple[str, str, int]:
    username = "jagdeep@indiaultimate.org"
    password = "password"
    user = User.objects.create(
        username=username, email=username, first_name="Jagdeep", last_name="Chatterjee"
    )
    user.set_password(password)
    user.save()
    return username, password, user.id


def create_event(title: str) -> Event:
    today = now()
    days = random.randint(30, 100)  # noqa: S311
    start = (datetime.timedelta(days=days) + today).date()
    end = (datetime.timedelta(days=days + 2) + today).date()
    team_reg_start = today - datetime.timedelta(days=14)
    team_reg_end = today - datetime.timedelta(days=7)
    player_reg_start = team_reg_end + datetime.timedelta(days=1)
    player_reg_end = end - datetime.timedelta(days - 1)
    return Event.objects.create(
        title=title,
        start_date=start,
        end_date=end,
        team_registration_start_date=team_reg_start,
        team_registration_end_date=team_reg_end,
        player_registration_start_date=player_reg_start,
        player_registration_end_date=player_reg_end,
    )


@pytest.mark.django_db(transaction=True)
class TestIntegration(BaseCase):
    def setUp(self, masterqa_mode: bool = False) -> None:
        super().setUp()
        test_email_dir = BASE_DIR.joinpath("tmp")
        create_empty_directory(test_email_dir)

    def tearDown(self) -> None:
        super().tearDown()
        test_email_dir = BASE_DIR.joinpath("tmp")
        create_empty_directory(test_email_dir)

    @pytest.mark.skipif(
        not os.environ.get("PHONEPE_MERCHANT_ID"), reason="no PhonePe configuration found"
    )
    def test_new_user_login(self) -> None:
        username, password, user_id = create_login_user()
        names = ["NCS 23-24 SW Sectionals (Bangalore)", "NCS 23-24 North Sectionals (Delhi)"]
        for name in names:
            create_event(name)

        with running_test_server() as base_url:
            self.open(base_url)
            self.click_link("Login")
            self.click("button#password-tab")
            self.type("input#email", username)
            self.type("input#current-password", f"{password}\n")
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

            # self.click(f'a[href="/membership/{player_id}"]')
            # self.js_click("div.my-2 label div")
            # self.click("select#event")
            # self.assert_element("select#event option")
            # self.check_if_unchecked("input")
            # self.assert_element('button:contains("Pay")')
            # self.click('button:contains("Pay")')

            # Redirect to PhonePe page
            # self.js_click("input#net-banking", timeout=45)
            # self.js_click("button#b2bOnboardingSubmitButton")
            # self.type("input#username", "test")
            # self.type("input#password", "test\n")
            # self.click('input[value="Confirm"]')
            # self.save_screenshot_to_logs("pay-clicked.png")

            self.click("#my-account", timeout=45)
            self.click(f'a[href="/vaccination/{player_id}"]')
            self.select_option_by_text("select#name", "Covishield")
            self.choose_file("input#certificate", "frontend/assets/favico.png")
            self.click('button:contains("Submit")')
            self.click("div#root section div")
            # self.click(f'a[href="/waiver/{player_id}"]')
            # self.js_click("input#waiver")
            # self.js_click("input#legal")
            # self.click('button:contains("I Agree")')

            self.click("#my-account")
            self.assert_element("div#accordion-body-player div div table tbody tr:nth-of-type(7)")
            self.assert_element("div#accordion-body-player div div table tbody tr:nth-of-type(8)")
            self.assert_element("div#accordion-body-player div div table tbody tr:nth-of-type(9)")

            self.click("h2#accordion-heading-transactions")
            self.assert_element("h2#accordion-heading-transactions")

    def test_login_with_otp(self) -> None:
        username, password, user_id = create_login_user()

        with running_test_server() as base_url:
            self.open(base_url)
            self.click_link("Login")
            self.click("button#email-otp-tab")
            self.type("input#otp-email", username)
            self.click("button#send-otp-button")
            self.assert_element("input#email-otp-number")

            test_email_dir = BASE_DIR.joinpath("tmp")
            otp = get_otp_from_email_logs(test_email_dir)

            self.type("input#email-otp-number", otp)
            self.click("button#validate-otp-button")
            self.assert_element("h2#accordion-heading-actions")
            self.assert_element('a[href="/registration/me"]')
            print("Successfully logged in!")
