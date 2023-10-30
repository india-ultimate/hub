import { getCookie } from "../utils";
import { createSignal, Show } from "solid-js";
import { Spinner } from "../icons";

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
    </>
  );
};

export default PhonePePayment;
