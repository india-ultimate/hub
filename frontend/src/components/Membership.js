import StatusStepper from "./StatusStepper";
import { useStore } from "../store";
import { useParams } from "@solidjs/router";
import {
  createSignal,
  createEffect,
  onCleanup,
  onMount,
  Show,
  For
} from "solid-js";
import {
  fetchUserData,
  displayDate,
  fetchUrl,
  membershipYearOptions,
  findPlayerById,
  purchaseMembership
} from "../utils";
import {
  membershipStartDate,
  membershipEndDate,
  annualMembershipFee,
  eventMembershipFee
} from "../constants";

const Membership = () => {
  const [store, { setLoggedIn, setData, setPlayerById }] = useStore();
  const [player, setPlayer] = createSignal();
  const [membership, setMembership] = createSignal();

  const [status, setStatus] = createSignal();

  const years = membershipYearOptions();
  const [year, setYear] = createSignal(years?.[0]);
  const [startDate, setStartDate] = createSignal("");
  const [endDate, setEndDate] = createSignal("");
  const [annual, setAnnual] = createSignal(true);

  const [events, setEvents] = createSignal([]);

  const [event, setEvent] = createSignal();

  const params = useParams();
  createEffect(() => {
    const player = findPlayerById(store.data, Number(params.playerId));
    setPlayer(player);
    setMembership(player?.membership);
  });

  const isShortEvent = event =>
    (new Date(event.end_date) - new Date(event.start_date)) / (1000 * 86400) <=
    5;

  const eventsSuccessHandler = async response => {
    const data = await response.json();
    if (response.ok) {
      setEvents(data.filter(isShortEvent));
    } else {
      console.log(data);
    }
  };

  onMount(() => {
    if (!store.loggedIn) {
      fetchUserData(setLoggedIn, setData);
    }
    fetchUrl("/api/events", eventsSuccessHandler, error => console.log(error));
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

  const handleEventChange = e => {
    setEvent(events().find(ev => ev.id === Number(e.target.value)));
  };

  const triggerPurchase = () => {
    const data = annual()
      ? {
          player_id: player().id,
          year: year()
        }
      : {
          player_id: player().id,
          event_id: event().id
        };

    purchaseMembership(data, setStatus, setPlayerById);
  };

  const formatDate = dateArray => {
    const [dd, mm, YYYY] = dateArray;
    const DD = dd.toString().padStart(2, "0");
    const MM = mm.toString().padStart(2, "0");
    return `${YYYY}-${MM}-${DD}`;
  };

  createEffect(() => {
    if (annual()) {
      // Set startDate and endDate based on selected year
      setStartDate(formatDate([...membershipStartDate, year()]));
      setEndDate(formatDate([...membershipEndDate, year() + 1]));
    } else if (event()) {
      setStartDate(event().start_date);
      setEndDate(event().end_date);
    }
  });

  createEffect(() => {
    // Set event when we have a list of events
    if (events()?.length > 0) {
      setEvent(events()?.[0]);
    }
  });

  const [payDisabled, setPayDisabled] = createSignal(false);
  createEffect(() => {
    setPayDisabled(!(annual() && year()) && !(!annual() && event()));
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
            <StatusStepper player={player()} />
          </div>
        }
      >
        <h3>Renew membership for {player()?.full_name}</h3>

        <div class="my-2">
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              value=""
              class="sr-only peer"
              checked={annual()}
              onChange={() => setAnnual(!annual())}
            />
            <div class="w-11 h-6 bg-gray-200 rounded-full peer peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600" />
            <span class="ml-3 text-sm font-medium text-gray-900 dark:text-gray-300">
              Annual membership
            </span>
          </label>

          <Show when={annual()}>
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
              Pay UPAI membership fee (₹ {annualMembershipFee / 100}) valid for
              the period from {displayDate(startDate())} to{" "}
              {displayDate(endDate())}
            </p>
          </Show>

          <Show when={!annual() && events()?.length > 0}>
            <select
              id="event"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              value={event()?.id}
              onInput={handleEventChange}
              required
            >
              <For each={events()}>
                {event => <option value={event?.id}>{event?.title}</option>}
              </For>
            </select>
            <p>
              Pay UPAI membership fee (₹ {eventMembershipFee / 100}) for the{" "}
              {event().title} ({displayDate(startDate())} to{" "}
              {displayDate(endDate())})
            </p>
          </Show>
          <Show when={!annual() && events()?.length === 0}>
            <p>No upcoming events found, for membership...</p>
          </Show>
          <div>
            <button
              class={`my-2 text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 ${
                payDisabled() ? "cursor-not-allowed" : ""
              } `}
              onClick={triggerPurchase}
              disabled={payDisabled()}
            >
              Pay
            </button>
          </div>
        </div>
        <p>{status()}</p>
      </Show>
    </div>
  );
};

export default Membership;
