import { createSignal, onMount, Show } from "solid-js";

import { Spinner } from "../icons";
import { useStore } from "../store";
import { fetchUserData, getCookie } from "../utils";

const RazorpayPayment = props => {
  const [loading, setLoading] = createSignal(false);

  const [_, { userFetchSuccess, userFetchFailure }] = useStore();

  onMount(() => {
    if (!window.Razorpay) {
      props.setStatus(
        "Razorpay SDK failed to load. please check are you online?"
      );
      if (props.failureCallback) {
        props.failureCallback(
          "Razorpay SDK failed to load. please check are you online?"
        );
      }
    }
  });

  const initiatePayment = () => {
    const player_ids = props?.player_ids;
    const event_id = props.event?.id;
    const team_id = props.team?.id;
    const partial = props.partialPayment || false;
    // A subscription order names who is buying which tier; the server prices
    // it. Registrations keep their own shapes.
    const data = team_id
      ? player_ids
        ? { team_id, event_id, player_ids } // Player Registration
        : { team_id, event_id, partial } // Team Registration
      : { season_id: props.season?.id, items: props.items }; // Subscription

    setLoading(true);
    props.setStatus("");

    fetch("/api/transactions/razorpay", {
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
              fetch("/api/transactions/razorpay/callback", {
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
                  if (response.status >= 400 && response.status < 500) {
                    const error = await response.json();
                    props.setStatus(`Error: ${error.message}`);
                    if (props.failureCallback) {
                      props.failureCallback(error.message);
                    }
                  } else {
                    const body = await response.text();
                    props.setStatus(
                      `Error: ${response.statusText} (${response.status}) — ${body}`
                    );
                    if (props.failureCallback) {
                      props.failureCallback(
                        `${response.statusText} (${response.status}) — ${body}`
                      );
                    }
                  }
                }
                setLoading(false);
              });
            }
          });
          paymentObject.on("payment.failed", response => {
            props.setStatus(
              `Error: ${response.error.code}: ${response.error.description}`
            );
            if (props.failureCallback) {
              props.failureCallback(
                `${response.error.code}: ${response.error.description}`
              );
            }
            setLoading(false);
          });
          paymentObject.open();

          //   window.location = data.redirect_url;
        } else {
          if (response.status >= 400 && response.status < 500) {
            const error = await response.json();
            props.setStatus(`Error: ${error.message}`);
            if (props.failureCallback) {
              props.failureCallback(`${error.message}`);
            }
          } else {
            const body = await response.text();
            props.setStatus(
              `Error: ${response.statusText} (${response.status}) — ${body}`
            );
            if (props.failureCallback) {
              props.failureCallback(
                `${response.statusText} (${response.status}) — ${body}`
              );
            }
          }
          setLoading(false);
        }
      })
      .catch(error => {
        setLoading(false);
        props.setStatus(`Error: ${error}`);
        if (props.failureCallback) {
          props.failureCallback(`${error}`);
        }
      });
  };

  return (
    <>
      <button
        class={`block rounded-lg bg-${props.buttonColor || "blue"}-600 ${
          props.large
            ? "mx-auto w-full max-w-md px-6 py-4 text-base font-semibold shadow-sm focus:outline-none focus:ring-4 focus:ring-blue-300"
            : "my-5 px-3 py-2.5 text-sm font-medium"
        } text-center text-white hover:bg-${props.buttonColor || "blue"}-700  ${
          props.disabled || loading()
            ? "cursor-not-allowed bg-gray-400 hover:bg-gray-500"
            : ""
        }`}
        type="button"
        disabled={props.disabled || loading()}
        onClick={initiatePayment}
      >
        <Show when={loading()} fallback={props.buttonText || "Pay"}>
          <div class="text-sm">
            <Spinner height={20} width={20} />
            <span class="mr-2">Paying...</span>
          </div>
        </Show>
      </button>
    </>
  );
};

export default RazorpayPayment;
