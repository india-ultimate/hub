"""Closing the payment popup, or losing the Hub mid-payment, on a paid form.

Razorpay and the two payment requests are stubbed in the page: what matters
here is what the Submit button does when the popup closes or the Hub is
unreachable, which the real checkout can't be made to do on demand.
"""

from contextlib import ExitStack

import pytest
from seleniumbase import BaseCase

from server.core.models import User
from server.forms.models import Form
from server.tests import test_ui
from server.tests.localserver import APP_URL, running_test_server

# A Razorpay whose popup does `window.popup` ("dismiss" or "pay") when opened,
# a Hub that makes the order, and a Hub that can't be reached to confirm it.
STUBS = """
window.popup = arguments[0];
window.Razorpay = class {
  constructor(options) { this.options = options; }
  on() {}
  open() {
    if (window.popup === "dismiss") this.options.modal?.ondismiss?.();
    else this.options.handler({razorpay_payment_id: "pay_x"});
  }
};
const realFetch = window.fetch;
window.fetch = (url, init) => {
  if (url.endsWith("/responses") && init?.method === "POST") {
    const order = {key: "k", order_id: "order_x", modal: {}};
    return Promise.resolve(new Response(
      JSON.stringify({status: "payment_required", order}),
      {status: 200, headers: {"Content-Type": "application/json"}}
    ));
  }
  if (url.endsWith("/razorpay/callback")) return Promise.reject(new TypeError("offline"));
  return realFetch(url, init);
};
"""

SUBMIT = 'button[type="submit"]'


@pytest.mark.django_db(transaction=True)
class TestPaymentPopupIntegration(BaseCase):
    sign_in_as = test_ui.TestIntegration.sign_in_as

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.servers = ExitStack()
        cls.servers.enter_context(running_test_server())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.servers.close()
        super().tearDownClass()

    def setUp(self, masterqa_mode: bool = False) -> None:
        super().setUp()
        user = User.objects.create_user("payer@example.com", "payer@example.com", "pw")
        Form.objects.create(
            title="Camp sign-up",
            slug="camp-sign-up",
            fields=[{"key": "size", "label": "Size", "type": "text", "required": True}],
            payment_amount=150000,
            is_active=True,
            created_by=user,
        )
        self.sign_in_as(user)

    def submit_with_popup(self, popup: str) -> None:
        self.open(f"{APP_URL}/forms/camp-sign-up")
        self.type("#size", "M")
        self.execute_script(STUBS, popup)
        self.click(SUBMIT)

    def test_closing_the_popup_lets_them_pay_again(self) -> None:
        self.submit_with_popup("dismiss")
        self.wait_for_text("Pay ₹1,500 & Submit", SUBMIT, timeout=10)
        self.assert_element_not_present(f"{SUBMIT}:disabled")

    def test_an_unconfirmed_payment_keeps_the_button_off(self) -> None:
        self.submit_with_popup("pay")
        self.wait_for_text("don't pay again", timeout=10)
        self.assert_element_present(f"{SUBMIT}:disabled")
