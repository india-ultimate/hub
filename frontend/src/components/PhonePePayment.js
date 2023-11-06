import { getCookie } from "../utils";
import { createSignal, Show } from "solid-js";
import { Spinner } from "../icons";
import ManualPaymentModal from "./ManualPaymentModal";

const PhonePePayment = props => {
  const [loading, setLoading] = createSignal(false);

  const initiatePayment = () => {
    const player_id = props?.player_id;
    const player_ids = props?.player_ids;
    const year = props.year;
    const event_id = props.event?.id;
    const data = props.annual
      ? player_ids
        ? { player_ids, year }
        : { player_id, year }
      : { player_id, event_id };

    setLoading(true);
    props.setStatus("");

    fetch("/api/initiate-payment", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      body: JSON.stringify(data),
      credentials: "same-origin"
    })
      .then(async response => {
        if (response.ok) {
          const data = await response.json();
          window.location = data.redirect_url;
        } else {
          if (response.status === 422) {
            const error = await response.json();
            props.setStatus(`Error: ${error.message}`);
          } else {
            const body = await response.text();
            props.setStatus(
              `Error: ${response.statusText} (${response.status}) — ${body}`
            );
          }
        }
        setLoading(false);
      })
      .catch(error => {
        setLoading(false);
        props.setStatus(`Error: ${error}`);
      });
  };

  return (
    <>
      <Show when={loading()}>
        <Spinner />
      </Show>
      <div
        class="p-4 my-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400"
        role="alert"
      >
        If you are using UPI for your payment, try manually entering your UPI ID
        instead of using the PhonePe QR code.
      </div>
      <button
        class={`block text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 my-5 ${
          props.disabled ? "cursor-not-allowed" : ""
        }`}
        type="button"
        disabled={props.disabled}
        onClick={initiatePayment}
      >
        Pay
      </button>
      <div
        class="p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300"
        role="alert"
      >
        <details>
          <summary>Facing issues with the Payment gateway?</summary>
          <div class="my-4">
            You can make a direct payment (without using the payment gateway)
            and record the payment in the Hub
            <ManualPaymentModal
              disabled={props.disabled}
              annual={props.annual}
              year={props.year}
              player_ids={props.player_ids}
              amount={props.amount}
              setStatus={props.setStatus}
              successCallback={props.successCallback}
            />
          </div>
        </details>
      </div>
    </>
  );
};

export default PhonePePayment;
