import { getCookie } from "./utils";

export const UNREACHABLE =
  "We couldn't reach the Hub to confirm — don't pay again; this page will update.";

// Opens Razorpay for an order the server made, and tells the server when
// it's paid. onPaid runs as soon as Razorpay says so, before the server
// confirms; onDismiss only when given (the checkout was closed unpaid).
// If the confirmation never reaches the Hub the money may still be taken,
// so that goes to onUnconfirmed (else onFailure), never "nothing charged".
// Outside components/, where solid-hot-loader keeps only default exports.
export const openCheckout = (
  order,
  { onPaid, onSuccess, onFailure, onDismiss, onUnconfirmed }
) => {
  const paymentObject = new window.Razorpay({
    ...order,
    ...(onDismiss && { modal: { ...order.modal, ondismiss: onDismiss } }),
    handler: response => {
      onPaid?.();
      fetch("/api/transactions/razorpay/callback", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify(response),
        credentials: "same-origin"
      }).then(
        async response => {
          if (response.ok) {
            onSuccess?.();
          } else if (response.status >= 400 && response.status < 500) {
            const error = await response.json();
            onFailure?.(error.message);
          } else {
            const body = await response.text();
            onFailure?.(
              `${response.statusText} (${response.status}) — ${body}`
            );
          }
        },
        // Only the request failing lands here, not the handlers above.
        () => (onUnconfirmed || onFailure)?.(UNREACHABLE)
      );
    }
  });
  paymentObject.on("payment.failed", response => {
    onFailure?.(`${response.error.code}: ${response.error.description}`);
  });
  paymentObject.open();
};
