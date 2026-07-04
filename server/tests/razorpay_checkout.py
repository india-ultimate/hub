from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seleniumbase.fixtures.base_case import BaseCase

TEST_CONTACT_NUMBER = "9898234512"
# Domestic Mastercard from https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/test-integration/
TEST_CARD_NUMBER = "5267318187975449"
TEST_CARD_EXPIRY = "12/30"
TEST_CARD_CVV = "123"
# Indian test cards: enter 4-10 digit OTP on the sample payment page for success.
TEST_CARD_OTP = "123456"


def _wait_for_razorpay_sdk(test_case: BaseCase, timeout: float = 45) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if test_case.execute_script("return typeof window.Razorpay !== 'undefined'"):
            return
        time.sleep(0.5)
    raise AssertionError("Razorpay checkout SDK did not load")


def _submit_contact_details_if_needed(test_case: BaseCase) -> None:
    contact_selector = 'input[data-testid="contactNumber"]'
    if not test_case.is_element_visible(contact_selector):
        return

    test_case.click(contact_selector)
    test_case.clear(contact_selector)
    test_case.type(contact_selector, TEST_CONTACT_NUMBER)
    test_case.js_click(
        'div[data-testid="contact-overlay-container"] button:contains("Continue")',
        timeout=45,
    )


def _click_button_with_text(test_case: BaseCase, text: str, timeout: float = 15) -> None:
    script = """
        const label = arguments[0];
        const button = Array.from(document.querySelectorAll("button")).find(
            (element) => element.textContent.trim().includes(label)
        );
        if (!button) {
            return false;
        }
        button.click();
        return true;
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if test_case.execute_script(script, text):
            return
        time.sleep(0.5)
    raise AssertionError(f'Could not click Razorpay button containing "{text}"')


def _select_payment_method(test_case: BaseCase, method: str) -> None:
    selector = f'div[data-value="{method}"]'
    test_case.js_click(selector, timeout=45)
    deadline = time.time() + 15
    while time.time() < deadline:
        is_selected = test_case.execute_script(
            """
                const method = arguments[0];
                const tab = document.querySelector(`div[data-value="${method}"]`);
                if (!tab) {
                    return false;
                }
                return tab.classList.contains("peer-checked")
                    || tab.closest("label")?.querySelector("input")?.checked
                    || tab.getAttribute("aria-selected") === "true";
            """,
            method,
        )
        if is_selected:
            return
        test_case.js_click(selector, timeout=5)
        time.sleep(0.5)
    raise AssertionError(f'Razorpay payment method "{method}" was not selected')


def _uncheck_save_card_if_needed(test_case: BaseCase) -> None:
    save_card = 'input[data-testid="save-card-checkbox"]'
    if test_case.is_element_visible(save_card) and test_case.execute_script(
        "return document.querySelector(arguments[0])?.checked === true",
        save_card,
    ):
        test_case.click(save_card)


def _dismiss_save_card_prompt_if_needed(test_case: BaseCase) -> None:
    deadline = time.time() + 15
    while time.time() < deadline:
        for selector in (
            'button[name="pay_without_saving_card"]',
            'button:contains("Maybe later")',
        ):
            if test_case.is_element_visible(selector):
                test_case.js_click(selector, timeout=15)
                return
        time.sleep(0.5)


def _submit_card_otp_if_needed(test_case: BaseCase) -> None:
    otp_selector = 'form[name="otp"] input[name="otp"]'
    deadline = time.time() + 45
    while time.time() < deadline:
        if test_case.is_element_visible(otp_selector):
            break
        time.sleep(0.5)
    else:
        return

    test_case.type(otp_selector, TEST_CARD_OTP)
    test_case.js_click('form[name="otp"] button[type="submit"]', timeout=45)


def _leave_checkout_if_open(test_case: BaseCase, timeout: float = 45) -> None:
    try:
        test_case.switch_to_default_content()
    except Exception:
        pass

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            checkout_open = test_case.execute_script(
                """
                    const container = document.querySelector(".razorpay-container");
                    return !!(container && container.offsetParent !== null);
                """
            )
            if not checkout_open:
                return
        except Exception:
            return
        time.sleep(0.5)


def _complete_card_payment(test_case: BaseCase) -> None:
    """Complete Razorpay test-mode card payment per Razorpay docs.

    https://razorpay.com/docs/payments/payments/test-card-details/?preferred-country=IN
    """
    _select_payment_method(test_case, "card")

    card_number_selector = 'input[name="card.number"]'
    test_case.wait_for_element_visible(card_number_selector, timeout=45)
    test_case.type(card_number_selector, TEST_CARD_NUMBER)
    test_case.type('input[name="card.expiry"]', TEST_CARD_EXPIRY)
    test_case.type('input[name="card.cvv"]', TEST_CARD_CVV)
    _uncheck_save_card_if_needed(test_case)
    test_case.js_click('button[data-test-id="add-card-cta"]', timeout=45)
    _dismiss_save_card_prompt_if_needed(test_case)
    _submit_card_otp_if_needed(test_case)

    try:
        _click_button_with_text(test_case, "Success", timeout=5)
    except (AssertionError, Exception):
        pass
    _leave_checkout_if_open(test_case)


def complete_razorpay_test_payment(test_case: BaseCase) -> None:
    """Complete Razorpay checkout in test mode using the card payment flow."""
    _wait_for_razorpay_sdk(test_case)
    test_case.wait_for_element('button:contains("Pay")', timeout=45)
    test_case.js_click('button:contains("Pay")', timeout=45)
    test_case.wait_for_element_visible(".razorpay-container iframe", timeout=45)
    test_case.switch_to_frame(".razorpay-container iframe")
    _submit_contact_details_if_needed(test_case)
    _complete_card_payment(test_case)
