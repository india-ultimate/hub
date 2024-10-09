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
    const player_id = props?.player_id;
    const player_ids = props?.player_ids;
    const season_id = props.season?.id;
    const event_id = props.event?.id;
    const team_id = props.team?.id;
    const partial = props.partialPayment || false;
    const data = team_id
      ? player_ids
        ? { team_id, event_id, player_ids } // Player Registration
        : { team_id, event_id, partial } // Team Registration
      : props.annual
      ? player_ids
        ? { player_ids, season_id } // Group Membership
        : { player_id, season_id } // Individual Membership
      : { player_id, event_id }; // Event Membership

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
        class={`my-5 block rounded-lg bg-${
          props.buttonColor || "blue"
        }-600 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-${
          props.buttonColor || "blue"
        }-700  ${
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
