import datetime
import email
import os
import random
import re
import zlib
from contextlib import ExitStack
from email.utils import getaddresses
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.test import Client
from django.utils.timezone import now
from seleniumbase import BaseCase

from hub.settings import BASE_DIR
from server.core.models import Player, User
from server.duplicates.clusters import close_finished, detect_and_create
from server.duplicates.emails import notify
from server.duplicates.flow import dismiss, merge_pair, request_merge, request_staff
from server.duplicates.identity import mask_email
from server.duplicates.models import (
    AccountMerge,
    ClusterEvent,
    ClusterMember,
    DuplicateCluster,
    EmailAlias,
)
from server.season.models import Season
from server.servicerequests.models import ServiceRequestStatus
from server.task.models import Task
from server.tests.localserver import APP_URL, DJANGO_URL, running_test_server
from server.tests.razorpay_checkout import complete_razorpay_test_payment
from server.tests.utils import create_empty_directory
from server.tournament.models import Event

MAIL_DIR = BASE_DIR.joinpath("tmp")
# Django's file backend appends each message to the file after a line of 79
# dashes.
MAIL_SEPARATOR = "-" * 79
CODE = re.compile(r"<strong[^>]*>\s*(\d{6})\s*</strong>")
MERGE_PATH = re.compile(r"/merge-accounts/[\w-]+")


def mail_to(address: str) -> list[str]:
    """Bodies of every mail the servers wrote to `address`, newest first.

    Headers are parsed, never searched: the Message-ID holds the server's
    PID, and six digits of it would pass for a code. The To header is
    parsed into addresses and compared whole, so one address is never
    mistaken for another it merely contains (`sharma@x.com` inside
    `rahul.sharma@x.com`).
    """
    found = []
    files = sorted(MAIL_DIR.glob("*"), key=lambda path: (path.stat().st_mtime_ns, path.name))
    for path in files:
        for chunk in path.read_text().split(MAIL_SEPARATOR):
            if not chunk.strip():
                continue
            message = email.message_from_string(chunk.lstrip("\n"))
            recipients = {addr.lower() for _, addr in getaddresses([message.get("To") or ""])}
            if address.lower() not in recipients:
                continue
            found.append(
                "".join(
                    part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
                    for part in message.walk()
                    if not part.is_multipart()
                    and part.get_content_type() in ("text/plain", "text/html")
                )
            )
    return list(reversed(found))


def test_mail_to_matches_whole_addresses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One address must never see mail sent to another it is merely a
    substring of. No servers or database needed: a mail file is written
    directly, the way the file-based email backend would write one."""
    monkeypatch.setattr(f"{__name__}.MAIL_DIR", tmp_path)
    (tmp_path / "20260923-000000.log").write_text(
        'Content-Type: text/plain; charset="utf-8"\n'
        "MIME-Version: 1.0\n"
        "Subject: Test\n"
        "From: noreply@example.com\n"
        "To: rahul.sharma@x.com\n"
        "Date: Wed, 23 Sep 2026 00:00:00 -0000\n"
        "Message-ID: <123.456@host>\n"
        "\n"
        "hello\n"
    )

    assert mail_to("sharma@x.com") == []  # noqa: S101 — the check this test exists for
    assert mail_to("rahul.sharma@x.com") == ["hello\n"]  # noqa: S101


def latest_code(address: str) -> str:
    for body in mail_to(address):
        match = CODE.search(body)
        if match:
            return match.group(1)
    raise AssertionError(f"no code in any mail to {address}")


def queued_mail(to: str | None = None) -> list[dict[str, Any]]:
    """Emails queued for the task worker, which never runs in these tests."""
    tasks = Task.objects.filter(type=Task.TaskType.SEND_EMAIL).order_by("id")
    return [task.data for task in tasks if to is None or to in task.data.get("to", [])]


def merge_path(text: str) -> str:
    """The group page a link points at, on whichever host sent it."""
    match = MERGE_PATH.search(text)
    if match is None:
        raise AssertionError("no merge link in the text")
    return match.group(0)


def make_player(
    address: str,
    first: str = "Rahul",
    last: str = "Sharma",
    city: str = "Bengaluru",
    institution: str = "",
) -> User:
    # A phone of its own: phone is a detection rule, and one shared number
    # would pull unrelated people into one (blocked, so unsaved) group.
    phone = f"9{zlib.crc32(address.encode()) % 10**9:09d}"
    user = User.objects.create(
        username=address, email=address, first_name=first, last_name=last, phone=phone
    )
    Player.objects.create(
        user=user,
        date_of_birth=datetime.date(1995, 6, 15),
        gender=Player.GenderTypes.MALE,
        match_up=Player.MatchupTypes.MALE,
        city=city,
        educational_institution=institution,
    )
    return user


def create_login_user() -> tuple[str, str, int]:
    username = "jagdeep@indiaultimate.org"
    password = "password"
    user = User.objects.create(
        username=username,
        email=username,
        first_name="Jagdeep",
        last_name="Chatterjee",
        phone="9898234512",
    )
    user.set_password(password)
    user.save()
    return username, password, user.id


def create_duplicate_accounts() -> tuple[User, User]:
    """Two accounts for one person: same name and date of birth, and one
    detail they disagree about, so the review step has something to ask."""
    keep = make_player("rahul.sharma@gmail.com", city="Chennai")
    absorb = make_player("rahul@iitb.ac.in", city="Bengaluru")
    return keep, absorb


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
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # One Django and one webpack server for the whole class: starting them
        # is most of each test's time. The database is still flushed and the
        # mail folder still emptied between tests.
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def setUp(self, masterqa_mode: bool = False) -> None:
        super().setUp()
        create_empty_directory(MAIL_DIR)

    def tearDown(self) -> None:
        super().tearDown()
        create_empty_directory(MAIL_DIR)

    def sign_in_as(self, user: User) -> None:
        """Signed in without the login screens: the session is made in this
        process and handed to the browser, since both use one database."""
        client = Client()
        client.force_login(user)
        self.open(DJANGO_URL)  # the cookie needs a page on the host first
        self.delete_all_cookies()
        self.driver.add_cookie(
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
                "path": "/",
            }
        )
        # Pick up a CSRF cookie too, as a real first visit would.
        self.open(DJANGO_URL)

    def sign_in_with_otp(self, address: str) -> None:
        self.click("button#email-otp-tab")
        self.type("input#otp-email", address)
        self.click("button#send-otp-button")
        self.assert_element("input#email-otp-number")
        self.type("input#email-otp-number", latest_code(address))
        self.click("button#validate-otp-button")

    def admin_sign_in(self, address: str, password: str) -> None:
        self.delete_all_cookies()
        self.open(f"{DJANGO_URL}/admin/login/")
        self.type("input#id_username", address)
        self.type("input#id_password", password)
        self.click('input[type="submit"]')
        self.assert_element("#user-tools")

    @pytest.mark.skipif(
        not os.environ.get("RAZORPAY_KEY_ID"), reason="no Razorpay configuration found"
    )
    def test_new_user_login(self) -> None:
        username, password, user_id = create_login_user()
        names = ["NCS 23-24 SW Sectionals (Bangalore)", "NCS 23-24 North Sectionals (Delhi)"]
        for name in names:
            create_event(name)
        Season.objects.create(
            name="Season 24-25",
            start_date="2024-08-01",
            end_date="2025-07-30",
            annual_membership_amount=70000,
            sponsored_annual_membership_amount=20000,
            supporter_annual_membership_amount=150000,
        )

        self.open(DJANGO_URL)
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
        self.type("input#phone", "+919898234512")
        self.select_option_by_text("select#occupation", "Government")
        self.type("input#city", "Bengaluru")
        self.select_option_by_text("select#state_ut", "Karnataka")
        self.assert_element('button:contains("Submit")')
        self.save_screenshot_to_logs("form.png")

        self.click('button:contains("Submit")')
        self.assert_text("Successful Registration")
        player_id = Player.objects.get(user_id=user_id).id

        self.assert_element(f'a[href="/edit/registration/{player_id}"] svg')
        # self.assert_element(f'a[href="/vaccination/{player_id}"]')
        # self.assert_element(f'a[href="/uc-login/{player_id}"]')
        self.assert_element(f'a[href="/membership/{player_id}"]')
        self.assert_element(f'a[href="/waiver/{player_id}"]')
        print("Successfully registered!")

        self.click(f'a[href="/membership/{player_id}"]')
        self.assert_element('button:contains("Pay")')

        # Redirect to Razorpay modal (card flow; UPI Collect was removed in 2026)
        complete_razorpay_test_payment(self)
        self.wait_for_element("div#membership-exist", timeout=45)
        self.save_screenshot_to_logs("pay-clicked.png")

        self.click("#my-account", timeout=45)
        # self.click(f'a[href="/vaccination/{player_id}"]')
        # self.select_option_by_text("select#name", "Covishield")
        # self.choose_file("input#certificate", "frontend/assets/favico.png")
        # self.click('button:contains("Submit")')
        # self.click("div#root section div")
        self.click(f'a[href="/waiver/{player_id}"]')
        self.js_click("input#waiver")
        self.js_click("input#legal")
        self.click('button:contains("I Agree")')

        self.click("#my-account")
        self.assert_element("div#accordion-body-player div div table tbody tr:nth-of-type(7)")
        self.assert_element("div#accordion-body-player div div table tbody tr:nth-of-type(8)")
        self.assert_element("div#accordion-body-player div div table tbody tr:nth-of-type(9)")

        self.click("h2#accordion-heading-transactions")
        self.assert_element("h2#accordion-heading-transactions")

    def test_login_with_otp(self) -> None:
        username, password, user_id = create_login_user()

        self.open(DJANGO_URL)
        self.click_link("Login")
        self.sign_in_with_otp(username)
        self.assert_element("h2#accordion-heading-actions")
        self.assert_element('a[href="/registration/me"]')

        print("Successfully logged in!")

    # Breaks if: same-inbox verification, the per-keeper code check, the
    # resend wait, or attempt counting; the default field choice, or
    # `resolved` being applied; close_if_done; alias writing (Task 1) or
    # alias sign-in through /otp-login; the kept and merged emails; the
    # `mine` endpoint, the login redirect, or the "merged" headline (Task 3);
    # the confirm dialog appearing before any merge, with or without a
    # conflicting field to choose; the code dialog sending the code as it
    # opens, keeping its own errors and closing once the code is right
    # (redesign).
    def test_merging_three_accounts_end_to_end(self) -> None:
        keeper = make_player("rahul.sharma.demo@gmail.com", city="Chennai")
        # Gmail ignores dots: the same inbox, so signing in proves it.
        same_inbox = make_player("rahulsharmademo@gmail.com", city="")
        other = make_player("rahul.demo@iitb.example", city="Bengaluru", institution="IIT Bombay")
        [group] = detect_and_create()
        rows = {row.user_id: row for row in group.members.all()}
        self.assertEqual(len(rows), 3)
        mine, b, c = rows[keeper.id], rows[same_inbox.id], rows[other.id]

        # Signed out: statuses only, every other address masked.
        self.open(DJANGO_URL)
        self.open(f"{APP_URL}/merge-accounts/{mine.claim_token}")
        self.assert_element("div#merge-sign-in-prompt")
        self.assert_text_not_visible(same_inbox.email)
        self.assert_text_not_visible(other.email)

        # The login link comes back to the group, not the Dashboard.
        self.click("a#merge-login-link")
        self.sign_in_with_otp(keeper.email)
        self.assert_element("table#merge-table")

        # The same-inbox account confirmed itself when the page loaded, and
        # says why (spec §3) rather than leaving it unexplained.
        self.assert_attribute(f"span#merge-state-{b.pk}", "data-state", "verified")
        self.assert_text("same inbox", f"span#merge-proof-{b.pk}")
        b.refresh_from_db()
        self.assertEqual(b.state, ClusterMember.State.VERIFIED)
        self.assertEqual(b.proof, ClusterMember.Proof.SAME_INBOX)
        self.assertEqual(b.verified_by_id, keeper.id)

        # Confirming opens a dialog rather than acting straight away, even
        # with no conflicting field to choose (owner decision).
        self.click(f"button#merge-confirm-{b.pk}")
        self.assert_element(f"button#merge-modal-confirm-{b.pk}")
        self.assert_text("can't be undone")
        self.assert_attribute(f"span#merge-state-{b.pk}", "data-state", "verified")
        self.click(f"button#merge-modal-confirm-{b.pk}")
        self.assert_attribute(f"span#merge-state-{b.pk}", "data-state", "merged")
        self.assertFalse(User.objects.filter(id=same_inbox.id).exists())
        first_merge = AccountMerge.objects.get(cluster=group)
        self.assertEqual(first_merge.record["proof"]["method"], ClusterMember.Proof.SAME_INBOX)
        group.refresh_from_db()
        self.assertTrue(group.is_open)  # the third account is still to come

        # A code, sent by opening the dialog that asks for it. A second ask
        # inside the minute is refused, in the dialog rather than behind it.
        self.click(f"button#merge-send-code-{c.pk}")
        self.assert_element(f"input#merge-code-{c.pk}")  # the dialog is open
        self.assert_element("p#merge-notice")
        self.click(f"button#merge-code-cancel-{c.pk}")
        self.click(f"button#merge-send-code-{c.pk}")
        self.assert_text("Wait a minute", f"p#merge-code-error-{c.pk}")
        self.assertEqual(
            ClusterEvent.objects.filter(member=c, kind=ClusterEvent.Kind.CODE_SENT).count(), 1
        )

        # The code email names the keeper masked, never in full.
        body = mail_to(other.email)[0]
        self.assertIn(mask_email(keeper.email), body)
        self.assertNotIn(keeper.email, body)

        code = latest_code(other.email)
        wrong = f"{(int(code) + 1) % 10**6:06d}"
        self.type(f"input#merge-code-{c.pk}", wrong)
        self.click(f"button#merge-verify-{c.pk}")
        self.assert_text("isn't right", f"p#merge-code-error-{c.pk}")
        c.refresh_from_db()
        self.assertEqual(c.code_attempts, 1)

        # The right code confirms the row and closes the dialog behind it.
        self.type(f"input#merge-code-{c.pk}", code)
        self.click(f"button#merge-verify-{c.pk}")
        self.assert_attribute(f"span#merge-state-{c.pk}", "data-state", "verified")
        self.assert_element_not_visible(f"input#merge-code-{c.pk}")

        # The confirm dialog shows the conflict; the accounts disagree about
        # the city, and the keeper's is preselected.
        self.click(f"button#merge-confirm-{c.pk}")
        self.assert_element(f"fieldset#merge-field-{c.pk}-city")
        self.assert_element(f"input#merge-option-{c.pk}-city-0:checked")
        self.click(f"input#merge-option-{c.pk}-city-1")
        self.click(f"button#merge-modal-confirm-{c.pk}")
        self.assert_attribute(f"span#merge-state-{c.pk}", "data-state", "merged")
        self.assert_text("These accounts were merged.", "p#merge-finished")

        player = Player.objects.get(user=keeper)
        self.assertEqual(player.city, "Bengaluru")
        self.assertEqual(player.educational_institution, "IIT Bombay")  # a blank filled
        group.refresh_from_db()
        self.assertEqual(group.status, DuplicateCluster.Status.RESOLVED)
        self.assertTrue(group.events.filter(kind=ClusterEvent.Kind.CLOSED).exists())
        self.assertEqual(AccountMerge.objects.filter(cluster=group).count(), 2)
        self.assertEqual(
            set(EmailAlias.objects.filter(user=keeper).values_list("email", flat=True)),
            {"rahulsharmademo@gmail.com", "rahul.demo@iitb.example"},
        )
        self.assertEqual(len(queued_mail(to=keeper.email)), 2)  # one kept notice each
        self.assertEqual(len(queued_mail(to=same_inbox.email)), 1)
        self.assertEqual(len(queued_mail(to=other.email)), 1)

        # Nothing is waiting any more.
        self.open(f"{APP_URL}/dashboard")
        self.assert_element("h2#accordion-heading-actions")
        self.assert_element_not_present("div#merge-groups-notice")

        # The absorbed address still signs in, to the kept account. A fresh
        # CSRF cookie needs a page on the Django host first (see setUp's
        # sign_in_as for the same fallback-routing quirk).
        self.delete_all_cookies()
        self.open(DJANGO_URL)
        self.open(f"{APP_URL}/login")
        self.sign_in_with_otp(other.email)
        self.assert_element("h2#accordion-heading-actions")
        self.assertFalse(User.objects.filter(username=other.email).exists())
        self.assertEqual(User.objects.filter(first_name="Rahul").count(), 1)
        print("Merged three accounts end to end!")

    def test_saying_they_are_not_the_same_person(self) -> None:
        keep, absorb = create_duplicate_accounts()
        cluster = detect_and_create()[0]
        mine = ClusterMember.objects.get(cluster=cluster, user=keep)
        theirs = ClusterMember.objects.get(cluster=cluster, user=absorb)

        self.open(DJANGO_URL)

        # Dismissing now needs a signed-in member, so sign in first.
        self.open(f"{APP_URL}/login")
        self.sign_in_with_otp(keep.email)
        self.assert_element("h2#accordion-heading-actions")

        self.open(f"{APP_URL}/merge-accounts/{mine.claim_token}")
        # The irreversible warning now lives in the merge dialog, not here.
        self.assert_text("These accounts look like yours.")
        self.click("button#merge-dismiss-button")
        self.click("button#merge-dismiss-confirm")
        self.assert_element("p#merge-finished")

        # The other account's own link still opens for a signed-out
        # viewer. It renders the same words from a different branch of
        # the component (rows.length is 0, not 1, since an anonymous
        # viewer is nobody's own row) - the table of rows is the part
        # that tells them apart, and only this one hides it.
        self.delete_all_cookies()
        self.open(f"{APP_URL}/merge-accounts/{theirs.claim_token}")
        self.assert_element("p#merge-finished")
        self.assert_element_not_present("table#merge-table")

        self.assertEqual(User.objects.filter(id=absorb.id).count(), 1)
        self.assertEqual(User.objects.filter(id=keep.id).count(), 1)
        print("Successfully refused a group that is not one person!")

    # Breaks if: `find_login_user`, the self-address check, or
    # `MAX_OPEN_REQUESTS`; `/merge-accounts/mine` or the Dashboard notice; or
    # the list's cached query surviving a dismiss instead of being
    # invalidated, which would leave the back link showing a stale status.
    def test_starting_a_merge_request(self) -> None:
        keep, absorb = create_duplicate_accounts()

        self.open(DJANGO_URL)

        self.open(f"{APP_URL}/login")
        self.sign_in_with_otp(keep.email)
        self.assert_element("h2#accordion-heading-actions")

        self.open(f"{APP_URL}/dashboard")
        # Both duplicate accounts already have a player profile, so this
        # accordion section starts collapsed.
        self.click("h2#accordion-heading-actions")
        self.click("a#merge-request-link")
        self.assert_element("div#merge-request-keeper")
        # Nothing to say here: the reason is asked for on the merge page, and
        # only of the people who can't reach an inbox.
        self.assert_element_absent("textarea#merge-request-note")
        self.type("input#merge-request-email", "nobody@x.com")
        self.click("button#merge-request-submit")
        self.assert_text("couldn't find an account", "p#merge-request-error")
        self.type("input#merge-request-email", keep.email)
        self.click("button#merge-request-submit")
        self.assert_text("already belongs to this account", "p#merge-request-error")
        EmailAlias.objects.create(email="old.rahul@x.com", user=keep)
        self.type("input#merge-request-email", "old.rahul@x.com")
        self.click("button#merge-request-submit")
        self.assert_text("already belongs to this account", "p#merge-request-error")
        self.type("input#merge-request-email", absorb.email)
        self.click("button#merge-request-submit")
        self.assert_element("table#merge-table")

        group = DuplicateCluster.objects.get(requested_by_id=keep.id)
        self.assertEqual(group.origin, DuplicateCluster.Origin.REQUESTED)
        self.assertEqual(set(group.members.values_list("user_id", flat=True)), {keep.id, absorb.id})
        token = group.members.get(user=keep).claim_token

        # The Dashboard cached an empty merge list a moment ago, and the list
        # is cached for a minute. Walk there by SPA link, as a person does -
        # a reload would refetch everything and hide a missed invalidation.
        self.click("a#merge-back-to-list")
        self.assert_element("table#merge-list-table")
        self.assert_element(f"tr#merge-list-row-{token}")
        print("Successfully started a merge from the Dashboard!")

        # Three open requests is the most; a fourth is refused and makes nothing.
        extras = [
            request_merge(keep, make_player(f"extra{n}@x.com", first=f"Extra{n}").email, "")
            for n in (1, 2)
        ]
        groups = DuplicateCluster.objects.count()
        self.open(f"{APP_URL}/merge-accounts/new")
        self.type("input#merge-request-email", make_player("fourth@x.com", first="Fourth").email)
        self.click("button#merge-request-submit")
        self.assert_text("You already have 3 merge requests open", "p#merge-request-error")
        self.assertEqual(DuplicateCluster.objects.count(), groups)

        # The Dashboard's notice now opens the list page, which links to each
        # group; the group page itself is one hop further than it was. Pick
        # this group's own row by token, so the click is proven to land on
        # this group and not merely on some row.
        self.open(f"{APP_URL}/dashboard")
        self.assert_element("div#merge-groups-notice")
        self.click("div#merge-groups-notice a")
        self.assert_element("table#merge-list-table")
        self.assert_element(f"tr#merge-list-row-{token}")
        self.assert_text("Ready to review", f"tr#merge-list-row-{token}")
        self.click(f"tr#merge-list-row-{token} a")
        self.assert_element("table#merge-table")
        self.assert_text(absorb.email, "table#merge-table")

        # Cancelling changes what the list should show for this group. The
        # list's query is cached for a minute; the actions on this page must
        # invalidate it, not just refetch their own.
        self.click("button#merge-dismiss-button")
        self.click("button#merge-dismiss-confirm")
        self.assert_element("p#merge-finished")

        # The back link is an SPA link, not a reload - it must show the new
        # state itself, not whatever the list last cached.
        self.click("a#merge-back-to-list")
        self.assert_element("table#merge-list-table")
        self.assert_text("Closed", f"tr#merge-list-row-{token}")

        # A group whose link has expired waits on nobody: the Dashboard stops
        # counting it, and the list says so and points at starting again -
        # a link that must sit above the row's own link to be clickable.
        expired, live = extras
        ClusterMember.objects.filter(pk=expired.pk).update(
            expires_at=now() - datetime.timedelta(days=1)
        )
        self.open(f"{APP_URL}/dashboard")
        self.assert_text("1 account waiting", "div#merge-groups-notice")
        self.click("div#merge-groups-notice a")
        self.assert_text("Link expired", f"tr#merge-list-row-{expired.claim_token}")
        self.assert_text("Ready to review", f"tr#merge-list-row-{live.claim_token}")
        self.click(f"a#merge-list-start-again-{expired.claim_token}")
        self.assert_element("input#merge-request-email")

    # Breaks if: `_visible_rows` or the masking in `_serialize`; `can_act`,
    # Row.actionable() or expiry gating; the wrong-account message (Task 3);
    # the back link showing for anyone but a signed-in member of the group
    # (it keys off `signed_in_as`, not merely being signed in somewhere);
    # the emailed link opening the wrong account's own row once its owner is
    # signed in (step 1b, using the actual link build_messages sent them);
    # a page load that writes state. It does NOT cover build_messages
    # assigning one member's `claim_token` to another's email — nothing on
    # the page renders differently by which token opened it, only by who is
    # signed in — so that mapping bug would show no symptom here.
    def test_who_sees_what(self) -> None:
        keeper = make_player("kiran@x.com", first="Kiran", last="Rao")
        other = make_player("kiran.rao@y.com", first="Kiran", last="Rao")
        outsider = make_player("zoya@x.com", first="Zoya", last="Khan")
        merged_keeper = make_player("arjun@x.com", first="Arjun", last="Mehta")
        merged_other = make_player("arjun.m@y.com", first="Arjun", last="Mehta")
        dismisser = make_player("meera@x.com", first="Meera", last="Iyer")
        make_player("meera.i@y.com", first="Meera", last="Iyer")
        gone_keeper = make_player("farah@x.com", first="Farah", last="Khan")
        gone_other = make_player("farah.k@y.com", first="Farah", last="Khan")
        groups: dict[int, DuplicateCluster] = {}
        for g in detect_and_create():
            first_member = g.members.order_by("id").first()
            assert first_member is not None  # noqa: S101 — every cluster here has 2+ members
            assert first_member.user_id is not None  # noqa: S101 — freshly seeded, never gone
            groups[first_member.user_id] = g
        open_group, done, dismissed, resolved_by_deletion = (
            groups[keeper.id],
            groups[merged_keeper.id],
            groups[dismisser.id],
            groups[gone_keeper.id],
        )

        # A group already merged, and one already dismissed.
        ClusterMember.objects.filter(cluster=done, user=merged_other).update(
            state=ClusterMember.State.VERIFIED,
            verified_by_id=merged_keeper.id,
            verified_at=now(),
            proof=ClusterMember.Proof.EMAIL_CODE,
        )
        merge_pair(done, merged_keeper, merged_other.id, actor=merged_keeper)
        dismiss(dismissed, dismisser)

        # A group resolved because the other account was deleted outside any
        # merge (spec §13) — not the same thing, and must not be shown as one.
        gone_other.delete()
        close_finished()

        notify(open_group)
        mine = open_group.members.get(user=keeper)
        theirs = open_group.members.get(user=other)

        def states() -> list[str]:
            return list(open_group.members.order_by("id").values_list("state", flat=True))

        before = states()

        # 1. The group email's own link, signed out: statuses, masked, no actions.
        [mail] = queued_mail(to=other.email)
        self.open(DJANGO_URL)
        self.open(f"{APP_URL}{merge_path(mail['html_content'])}")
        self.assert_element("table#merge-table")
        self.assert_text_not_visible(keeper.email)
        self.assert_element_not_present("button[id^=merge-send-code-]")
        # No session, so no list of their own to link back to.
        self.assert_element_not_present("a#merge-back-to-list")
        self.assertEqual(states(), before)

        # 1b. The same emailed link works end to end for its owner: signed
        #     in, it shows full details on their own row. (Disclosure is
        #     keyed to who is signed in, not which member's token opened the
        #     page, so this does not prove build_messages paired the right
        #     token with the right recipient — only that the link it sent
        #     actually works for them.)
        self.sign_in_as(other)
        self.open(f"{APP_URL}{merge_path(mail['html_content'])}")
        self.assert_text(other.email, f"tr#merge-row-{theirs.pk}")
        # A signed-in member sees every row's full address now (spec §4).
        self.assert_text(keeper.email, f"tr#merge-row-{mine.pk}")
        self.assertEqual(states(), before)

        # 2. A member: both addresses in full, actions offered on the other.
        self.sign_in_as(keeper)
        self.open(f"{APP_URL}/merge-accounts/{mine.claim_token}")
        self.assert_text(keeper.email, f"tr#merge-row-{mine.pk}")
        self.assert_text(other.email, f"tr#merge-row-{theirs.pk}")
        self.assert_element(f"button#merge-send-code-{theirs.pk}")
        self.assert_element(f"button#merge-staff-open-{theirs.pk}")
        # Where a help request goes is said on the page, not only in the mail.
        self.assert_text("Ops team", "p#merge-help-note")
        self.assert_text("These aren't the same person", "button#merge-dismiss-button")
        self.assert_element("a#merge-back-to-list")
        self.assertEqual(states(), before)

        # 3. Signed in to an account outside the group: told so, no actions.
        self.sign_in_as(outsider)
        self.open(f"{APP_URL}/merge-accounts/{mine.claim_token}")
        self.assert_text(outsider.email, "div#merge-wrong-account")
        self.assert_element_not_present("div#merge-sign-in-prompt")
        self.assert_element_not_present("button[id^=merge-send-code-]")
        # Signed in, but to the wrong account: still not a member here.
        self.assert_element_not_present("a#merge-back-to-list")
        self.click("button#merge-sign-out")
        self.assert_element("button#email-otp-tab")  # the login page, not a loop
        self.assertEqual(states(), before)

        # 4. Expired: the member still sees where things stand, can do nothing;
        #    a signed-out visitor gets nothing.
        ClusterMember.objects.filter(cluster=open_group).update(
            expires_at=now() - datetime.timedelta(days=1)
        )
        self.sign_in_as(keeper)
        self.open(f"{APP_URL}/merge-accounts/{mine.claim_token}")
        self.assert_text("This link has expired")
        self.assert_element_not_present("button[id^=merge-send-code-]")
        self.assert_element_not_present("button[id^=merge-verify-]")
        self.delete_all_cookies()
        self.open(f"{APP_URL}/merge-accounts/{mine.claim_token}")
        self.assert_element("p#merge-link-invalid")

        # 5. Merged: the keeper sees it done; the absorbed row's link shows
        #    one sentence and no table.
        self.sign_in_as(merged_keeper)
        kept_row = done.members.get(merged_into_id__isnull=True)
        self.open(f"{APP_URL}/merge-accounts/{kept_row.claim_token}")
        self.assert_text("These accounts were merged.", "p#merge-finished")
        self.assert_text("Merged into yours")
        self.open(f"{APP_URL}/merge-accounts")
        self.assert_text("Merged", f"tr#merge-list-row-{kept_row.claim_token}")
        self.delete_all_cookies()
        gone_row = done.members.get(merged_into_id=merged_keeper.id)
        self.open(f"{APP_URL}/merge-accounts/{gone_row.claim_token}")
        self.assert_text("These accounts were merged.", "p#merge-finished")
        self.assert_element_not_present("table#merge-table")

        # 5b. Resolved by a deletion, not a merge (spec §13): the keeper must
        #     not see "These accounts were merged." above a row saying the
        #     other account no longer exists. Revert Finding 1's fix and this
        #     fails, since two rows and status Resolved was the old condition.
        self.sign_in_as(gone_keeper)
        resolved_by_deletion.refresh_from_db()
        self.assertEqual(resolved_by_deletion.status, DuplicateCluster.Status.RESOLVED)
        own_row = resolved_by_deletion.members.get(user=gone_keeper)
        self.open(f"{APP_URL}/merge-accounts/{own_row.claim_token}")
        self.assert_text("These accounts were sorted out.", "p#merge-finished")
        self.assert_text("Account deleted")
        # The list says what the group page says: nothing was merged here.
        self.open(f"{APP_URL}/merge-accounts")
        self.assert_text("Sorted out", f"tr#merge-list-row-{own_row.claim_token}")

        # 5c. Anonymous — no membership at all, so no rows either way — still
        # learns whether a merge happened: "were merged" for the group that
        # really merged, something else for the one deletion resolved.
        # Revert the payload's anything_merged flag and this fails, since
        # every finished, rowless group used to read as merged.
        self.delete_all_cookies()
        self.open(f"{APP_URL}/merge-accounts/{gone_row.claim_token}")
        self.assert_text("These accounts were merged.", "p#merge-finished")
        self.open(f"{APP_URL}/merge-accounts/{own_row.claim_token}")
        self.assert_element("p#merge-finished")
        self.assert_text_not_visible("were merged")

        # 6. Dismissed: the member sees the sentence and only their own row.
        self.sign_in_as(dismisser)
        own = dismissed.members.get(user=dismisser)
        self.open(f"{APP_URL}/merge-accounts/{own.claim_token}")
        self.assert_element("p#merge-finished")
        self.assertEqual(len(self.find_elements("tr[id^=merge-row-]")), 1)
        print("Every viewer sees only what they should!")

    # Breaks if: the admin actions' registration; approve_staff or
    # reject_staff; the approval signal's skip for REQUEST_ACCOUNT_MERGE; the
    # staff emails; the read-only inlines; the rejected state being
    # actionable again; the help dialog collecting the reason and closing
    # once it is sent (redesign).
    def test_our_team_approves_one_and_rejects_another(self) -> None:
        k1 = make_player("anil@x.com", first="Anil", last="Das")
        o1 = make_player("anil.d@y.com", first="Anil", last="Das")
        k2 = make_player("bina@x.com", first="Bina", last="Roy")
        o2 = make_player("bina.r@y.com", first="Bina", last="Roy")
        User.objects.create_superuser("staff@x.com", "staff@x.com", "staff-pass")
        groups: dict[int, DuplicateCluster] = {}
        for g in detect_and_create():
            first_member = g.members.order_by("id").first()
            assert first_member is not None  # noqa: S101 — every cluster here has 2 members
            assert first_member.user_id is not None  # noqa: S101 — freshly seeded, never gone
            groups[first_member.user_id] = g
        ga, gb = groups[k1.id], groups[k2.id]
        row1, row2 = ga.members.get(user=o1), gb.members.get(user=o2)

        # A member asks our team, through the page's help dialog.
        self.sign_in_as(k1)
        self.open(f"{APP_URL}/merge-accounts/{ga.members.get(user=k1).claim_token}")
        self.assert_element_not_visible(f"textarea#merge-staff-note-{row1.pk}")
        self.click(f"button#merge-staff-open-{row1.pk}")
        self.type(f"textarea#merge-staff-note-{row1.pk}", "I lost that inbox when I left college")
        self.click(f"button#merge-staff-send-{row1.pk}")
        self.assert_attribute(f"span#merge-state-{row1.pk}", "data-state", "pending-staff")
        self.assert_element_not_visible(f"textarea#merge-staff-note-{row1.pk}")  # dialog closed
        self.assert_element_not_present(f"button#merge-staff-open-{row1.pk}")
        row1.refresh_from_db()
        first_request = row1.staff_request
        assert first_request is not None  # noqa: S101 — just requested above
        self.assertEqual(first_request.status, ServiceRequestStatus.PENDING)
        self.assertEqual(first_request.user_id, k1.id)
        self.assertEqual(
            [m["subject"] for m in queued_mail(to=k1.email)], ["We're reviewing your merge request"]
        )
        [to_other] = queued_mail(to=o1.email)
        self.assertIn(row1.claim_token, to_other["html_content"])  # their own link

        # The other group's request, made directly: its UI path is the one above.
        second_request = request_staff(gb, k2, o2.id, "phone number changed")

        # Staff approve one and reject the other, in the admin.
        self.admin_sign_in("staff@x.com", "staff-pass")
        self.open(f"{DJANGO_URL}/admin/server/servicerequest/")
        self.click(f"input[name=_selected_action][value='{first_request.pk}']")
        self.select_option_by_value("select[name=action]", "approve_and_merge")
        self.click("button[name=index]")
        # The admin's own message confirms the action ran and its redirect
        # finished, before this checks the database it wrote to directly.
        self.assert_text(f"Request {first_request.pk} merged")
        self.assertFalse(User.objects.filter(id=o1.id).exists())
        first_request.refresh_from_db()
        self.assertEqual(first_request.status, ServiceRequestStatus.APPROVED)
        merge = AccountMerge.objects.get(cluster=ga)
        self.assertEqual(merge.record["proof"]["method"], ClusterMember.Proof.STAFF)
        self.assertEqual(merge.actor_email, "staff@x.com")

        self.open(f"{DJANGO_URL}/admin/server/servicerequest/")
        self.click(f"input[name=_selected_action][value='{second_request.pk}']")
        self.select_option_by_value("select[name=action]", "reject_merge")
        self.click("button[name=index]")
        self.assert_text(f"Request {second_request.pk} rejected")
        row2.refresh_from_db()
        self.assertEqual(row2.state, ClusterMember.State.REJECTED)
        self.assertIn(
            "We couldn't confirm an account for your merge",
            [m["subject"] for m in queued_mail(to=k2.email)],
        )

        # The history pages, read-only.
        self.open(f"{DJANGO_URL}/admin/server/duplicatecluster/{ga.pk}/change/")
        self.assert_text(o1.email)
        self.assert_element_not_present("input[name=_save]")
        self.open(f"{DJANGO_URL}/admin/server/accountmerge/{merge.pk}/change/")
        self.assert_text(o1.email)
        # A staff-approved merge aliases the absorbed address like any other
        # (the owner's call, see merge_accounts), so it signs in to the keeper.
        self.open(f"{DJANGO_URL}/admin/server/emailalias/?q={o1.email}")
        self.assert_text(o1.email)
        self.assertEqual(EmailAlias.objects.get(email=o1.email).user_id, k1.id)
        users = User.objects.count()
        self.delete_all_cookies()
        self.open(DJANGO_URL)
        self.open(f"{APP_URL}/login")
        self.sign_in_with_otp(o1.email)
        self.assert_element("h2#accordion-heading-actions")
        self.assertEqual(User.objects.count(), users)
        self.assertFalse(User.objects.filter(username=o1.email).exists())

        # Back as the second keeper: rejected, and a code can be tried again.
        self.sign_in_as(k2)
        self.open(f"{APP_URL}/merge-accounts/{gb.members.get(user=k2).claim_token}")
        self.assert_attribute(f"span#merge-state-{row2.pk}", "data-state", "rejected")
        self.assert_element(f"button#merge-send-code-{row2.pk}")
        print("Our team approved one merge and rejected another!")

    # Breaks if: the code email's link; `dismiss` permissions; the
    # cancel-versus-dismiss wording or event kind; opening the dismiss link
    # acting before the person confirms.
    def test_the_other_owner_says_no_and_a_requester_cancels(self) -> None:
        keeper = make_player("kavya@x.com", first="Kavya", last="Nair")
        other = make_player("dev@y.com", first="Dev", last="Patel")
        third = make_player("tara@z.com", first="Tara", last="Bose")
        mine = request_merge(keeper, other.email, "")
        group = mine.cluster
        theirs = group.members.get(user=other)

        # Opening the old dismiss link only asks; it never acts on load.
        self.sign_in_as(keeper)
        self.open(f"{APP_URL}/merge-accounts/{mine.claim_token}?dismiss=1")
        self.assert_element("button#merge-dismiss-confirm")
        group.refresh_from_db()
        self.assertTrue(group.is_open)

        # The keeper sends a code; the other owner opens that email's link.
        self.open(f"{APP_URL}/merge-accounts/{mine.claim_token}")
        # The person who asked is told so; a detected group reads differently.
        self.assert_text("You asked to merge these accounts", "p#merge-intro")
        self.assert_text("Cancel this request", "button#merge-dismiss-button")
        self.click(f"button#merge-send-code-{theirs.pk}")
        self.assert_element("p#merge-notice")
        link = merge_path(mail_to(other.email)[0])

        self.sign_in_as(other)
        self.open(f"{APP_URL}{link}")
        # The recipient did not ask for this - a stranger named them, the
        # system did not match them - so this must read differently from
        # both the requester's line above and a detected group's.
        self.assert_text("Someone asked to merge these accounts", "p#merge-intro")
        self.assert_text("These aren't the same person", "button#merge-dismiss-button")
        self.click("button#merge-dismiss-button")
        self.click("button#merge-dismiss-confirm")
        self.assert_element("p#merge-finished")
        group.refresh_from_db()
        self.assertEqual(group.status, DuplicateCluster.Status.DISMISSED)
        self.assertEqual(group.dismissed_by_id, theirs.pk)
        event = group.events.get(kind=ClusterEvent.Kind.DISMISSED)
        self.assertEqual(event.actor_id, other.id)

        # The keeper now sees the sentence and their own row only. They are
        # the requester (is_requester is true), but the OTHER owner said no,
        # not them — so this must still be the plain dismissal sentence, not
        # a claim that the keeper cancelled anything. This is the case an
        # is_requester-only fix would get wrong.
        self.sign_in_as(keeper)
        self.open(f"{APP_URL}/merge-accounts/{mine.claim_token}")
        self.assert_text(
            "Someone in this group said these aren't the same person.", "p#merge-finished"
        )
        self.assertEqual(len(self.find_elements("tr[id^=merge-row-]")), 1)

        # A requester cancelling their own request is recorded as a cancel,
        # and worded as one.
        second = request_merge(keeper, third.email, "")
        self.open(f"{APP_URL}/merge-accounts/{second.claim_token}")
        self.click("button#merge-dismiss-button")
        self.assert_text("Cancel this merge request?")
        self.click("button#merge-dismiss-confirm")
        # The click fires an async POST; wait for its refetch to land before
        # reading the database, or this races the request that writes it.
        self.assert_text("You cancelled this merge request.", "p#merge-finished")
        cancelled = second.cluster
        self.assertTrue(cancelled.events.filter(kind=ClusterEvent.Kind.CANCELLED).exists())
        self.assertFalse(cancelled.events.filter(kind=ClusterEvent.Kind.DISMISSED).exists())

        # The other owner says no while the keeper has the page open. Send
        # code is refused, and the dialog keeps its error until the keeper
        # closes it; then the page shows where things stand, not the same
        # button again. Refresh only on success and the button stays;
        # refresh while the dialog is open and the error goes with it.
        ravi = make_player("ravi@w.com", first="Ravi", last="Iyer")
        third_request = request_merge(keeper, ravi.email, "")
        ravis = third_request.cluster.members.get(user=ravi)
        self.open(f"{APP_URL}/merge-accounts/{third_request.claim_token}")
        self.assert_element(f"button#merge-send-code-{ravis.pk}")
        dismiss(third_request.cluster, ravi)
        self.click(f"button#merge-send-code-{ravis.pk}")
        self.assert_text("already been sorted out", f"p#merge-code-error-{ravis.pk}")
        self.click(f"button#merge-code-cancel-{ravis.pk}")
        self.assert_element("p#merge-finished")
        self.assert_element_absent(f"button#merge-send-code-{ravis.pk}")
        print("The other owner said no, and a request was cancelled!")

    # Breaks if: the blocked-merge review (Task 2) — the `blocked` signal from
    # a "reason": "blocked" response, or the staff note/button it then shows,
    # including their ids being distinct from the open-row staff-note ids and
    # the "Ask our team to review" wording spec §12 requires; the confirm
    # dialog's error not using role="alert" (redesign).
    def test_a_blocked_merge_goes_to_our_team(self) -> None:
        keeper = make_player("rahul.k@x.com", first="Rahul", last="Sharma")
        other = make_player("priya.s@y.com", first="Priya", last="Sharma")
        mine = request_merge(keeper, other.email, "")
        theirs = mine.cluster.members.get(user=other)
        # Proven already: a blocker is only ever reached after proof.
        ClusterMember.objects.filter(pk=theirs.pk).update(
            state=ClusterMember.State.VERIFIED,
            verified_by_id=keeper.id,
            verified_at=now(),
            proof=ClusterMember.Proof.EMAIL_CODE,
        )

        self.sign_in_as(keeper)
        self.open(f"{APP_URL}/merge-accounts/{mine.claim_token}")
        self.click(f"button#merge-confirm-{theirs.pk}")
        self.click(f"button#merge-modal-confirm-{theirs.pk}")
        self.assert_text("different people", f"p#merge-modal-error-{theirs.pk}")
        self.assertTrue(User.objects.filter(id=other.id).exists())
        self.click(f"button#merge-modal-cancel-{theirs.pk}")

        # Spec §12 mandates this exact phrase on the offered review.
        self.assert_text("Ask our team to review", f"button#merge-blocked-send-{theirs.pk}")
        self.type(f"textarea#merge-blocked-note-{theirs.pk}", "Priya is my legal name")
        self.click(f"button#merge-blocked-send-{theirs.pk}")
        self.assert_attribute(f"span#merge-state-{theirs.pk}", "data-state", "pending-staff")
        theirs.refresh_from_db()
        self.assertEqual(theirs.state, ClusterMember.State.PENDING_STAFF)
        self.assertIsNotNone(theirs.staff_request_id)
        print("A blocked merge went to our team!")
