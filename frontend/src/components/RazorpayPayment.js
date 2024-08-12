import { createSignal, onMount, Show } from "solid-js";

import { Spinner } from "../icons";
import { useStore } from "../store";
import {
  fetchUserData,
  getCookie,
  loadRazorpayScript,
  razorpayScriptExists
} from "../utils";

const RazorpayPayment = props => {
  const [loading, setLoading] = createSignal(false);

  const [_, { userFetchSuccess, userFetchFailure }] = useStore();

  onMount(async () => {
    if (!razorpayScriptExists()) {
      const res = await loadRazorpayScript();

      if (!res) {
        props.setStatus(
          "Razorpay SDK failed to load. please check are you online?"
        );
      }
    }
  });

  const initiatePayment = () => {
    const player_id = props?.player_id;
    const player_ids = props?.player_ids;
    const season_id = props.season?.id;
    const event_id = props.event?.id;
    const data = props.annual
      ? player_ids
        ? { player_ids, season_id }
        : { player_id, season_id }
      : { player_id, event_id };

    setLoading(true);
    props.setStatus("");

    fetch("/api/create-order", {
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

          const paymentObject = new window.Razorpay({
            ...data,
            handler: response => {
              fetch("/api/payment-success", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-CSRFToken": getCookie("csrftoken")
                },
                body: JSON.stringify(response),
                credentials: "same-origin"
              }).then(async response => {
                if (response.ok) {
                  fetchUserData(userFetchSuccess, userFetchFailure);
                  if (props.successCallback) {
                    props.successCallback();
                  }
                  props.setStatus(
                    <span class="text-green-500 dark:text-green-400">
                      Payment successfully completed! 🎉
                    </span>
                  );
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
              });
            }
          });
          paymentObject.on("payment.failed", response => {
            props.setStatus(
              `Error: ${response.error.code}: ${response.error.description}`
            );
          });
          paymentObject.open();

          //   window.location = data.redirect_url;
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
      <button
        class={`my-5 block rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800  ${
          props.disabled
            ? "cursor-not-allowed bg-gray-400 hover:bg-gray-500"
            : ""
        }`}
        type="button"
        disabled={props.disabled}
        onClick={initiatePayment}
      >
        Pay
      </button>
      {/* <div
        class="mb-4 rounded-lg bg-yellow-50 p-4 text-sm text-yellow-800 dark:bg-gray-800 dark:text-yellow-300"
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
              player_id={props.player_id}
              player_ids={props.player_ids}
              amount={props.amount}
              setStatus={props.setStatus}
              successCallback={props.successCallback}
              event={props.event}
            />
          </div>
        </details>
      </div> */}
    </>
  );
};

export default RazorpayPayment;
