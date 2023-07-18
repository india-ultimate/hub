import Player from "./Player";
import { useStore } from "../store";
import { useParams } from "@solidjs/router";
import { createSignal, createEffect, onCleanup, onMount, Show } from "solid-js";
import { getCookie, fetchUserData, displayDate } from "../utils";
import {
  membershipStartDate,
  membershipEndDate,
  membershipFee
} from "../constants";

const getPlayer = (data, id) => {
  if (data.player?.id === id) {
    return data.player;
  } else {
    return data.players?.filter(p => p.id === id)?.[0];
  }
};

const membershipOptions = () => {
  // Get the current date
  const currentDate = new Date();
  const currentMonth = currentDate.getMonth() + 1;
  const year = currentDate.getFullYear();
  const [_, membershipEndMonth] = membershipStartDate;

  let renewalOptions = [];

  if (currentMonth <= membershipEndMonth) {
    renewalOptions.push(year - 1);
    if (currentMonth == membershipEndMonth) {
      renewalOptions.push(year);
    }
  } else if (currentMonth >= membershipEndMonth) {
    renewalOptions.push(year);
  }

  return renewalOptions;
};

const handleSuccess = (data, setStatus, setPlayerById) => {
  fetch("/api/payment-success", {
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
        const player = await response.json();
        setPlayerById(player);
        setStatus("Payment successfully completed!");
      } else {
        if (response.status === 422) {
          const error = await response.json();
          setStatus(`Error: ${error.message}`);
        } else {
          setStatus(`Error: ${response.statusText} (${response.status})`);
        }
      }
    })
    .catch(error => setStatus(`Error: ${error}`));
};

const openRazorpayUI = (data, setStatus, setPlayerById) => {
  const options = {
    ...data,
    handler: e => handleSuccess(e, setStatus, setPlayerById)
  };
  const rzp = window.Razorpay(options);
  rzp.open();
};

const purchaseMembership = (
  playerId,
  startDate,
  endDate,
  setStatus,
  setPlayerById
) => {
  console.log(
    `Paying for membership for ${playerId} for ${startDate} - ${endDate}`
  );

  fetch("/api/create-order", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    body: JSON.stringify({
      player_id: playerId,
      type: "membership",
      amount: membershipFee,
      start_date: startDate,
      end_date: endDate
    }),
    credentials: "same-origin"
  })
    .then(async response => {
      if (response.ok) {
        const data = await response.json();
        setStatus("");
        openRazorpayUI(data, setStatus, setPlayerById);
      } else {
        if (response.status === 422) {
          const errors = await response.json();
          const errorMsgs = errors.detail.map(
            err => `${err.msg}: ${err.loc[2]}`
          );
          setStatus(`Validation errors: ${errorMsgs.join(", ")}`);
        } else if (response.status === 400) {
          const errors = await response.json();
          setStatus(`Validation errors: ${errors.message}`);
        } else {
          setStatus(`Error: ${response.statusText} (${response.status})`);
        }
      }
    })
    .catch(error => setStatus(`Error: ${error}`));
};

const Membership = () => {
  const [store, { setLoggedIn, setData, setPlayerById }] = useStore();
  const [player, setPlayer] = createSignal();
  const [membership, setMembership] = createSignal();

  const [status, setStatus] = createSignal();

  const years = membershipOptions();
  const [year, setYear] = createSignal(years?.[0]);
  const [startDate, setStartDate] = createSignal("");
  const [endDate, setEndDate] = createSignal("");

  const params = useParams();
  createEffect(() => {
    const player = getPlayer(store.data, Number(params.playerId));
    setPlayer(player);
    setMembership(player?.membership);
  });

  onMount(() => {
    if (!store.loggedIn) {
      fetchUserData(setLoggedIn, setData);
    }
  });

  let rzpScript;
  onMount(() => {
    rzpScript = document.createElement("script");
    rzpScript.src = "https://checkout.razorpay.com/v1/checkout.js";
    rzpScript.async = true;
    document.body.appendChild(rzpScript);
  });
  onCleanup(() => {
    if (rzpScript && document.body.contains(rzpScript)) {
      document.body.removeChild(rzpScript);
      document
        .querySelectorAll(".razorpay-container")
        .forEach(el => document.body.removeChild(el));
    }
  });

  const handleYearChange = e => {
    setYear(Number(e.target.value));
  };

  const formatDate = dateArray => {
    const [dd, mm, YYYY] = dateArray;
    const DD = dd.toString().padStart(2, "0");
    const MM = mm.toString().padStart(2, "0");
    return `${YYYY}-${MM}-${DD}`;
  };

  createEffect(() => {
    // Set startDate and endDate based on selected year
    setStartDate(formatDate([...membershipStartDate, year()]));
    setEndDate(formatDate([...membershipEndDate, year() + 1]));
  });

  return (
    <div>
      <h1 class="text-2xl font-bold text-blue-500">Membership</h1>
      <Show
        when={!membership()?.is_active}
        fallback={
          <div>
            Membership for {player().full_name} is active until{" "}
            {displayDate(membership().end_date)}
          </div>
        }
      >
        <h3>Renew membership for {player()?.full_name}</h3>
        <div class="my-2">
          <select
            id="year"
            class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            value={year()}
            onInput={handleYearChange}
            required
          >
            <For each={years}>
              {year => (
                <option value={year}>
                  {year} &mdash; {year + 1}
                </option>
              )}
            </For>
          </select>
          <p>
            Pay the membership fee (₹ {membershipFee / 100}) for the period{" "}
            {displayDate(startDate())} to {displayDate(endDate())}
          </p>
          <button
            class="my-2 text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
            onclick={e =>
              purchaseMembership(
                player()?.id,
                startDate(),
                endDate(),
                setStatus,
                setPlayerById
              )
            }
          >
            Pay
          </button>
        </div>
        <p>{status()}</p>
      </Show>
    </div>
  );
};

export default Membership;
