import { useParams } from "@solidjs/router";
import { inboxStack } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import {
  annualMembershipFee,
  eventMembershipFee,
  membershipEndDate,
  membershipStartDate,
  minAge,
  minAgeWarning,
  sponsoredAnnualMembershipFee
} from "../constants";
import { useStore } from "../store";
import {
  displayDate,
  findPlayerById,
  getAge,
  membershipYearOptions
} from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import MembershipEventSelector from "./MembershipEventSelector";
import RazorpayPayment from "./RazorpayPayment";
// import PhonePePayment from "./PhonePePayment";
import StatusStepper from "./StatusStepper";

const Membership = () => {
  const [store] = useStore();

  const [player, setPlayer] = createSignal();
  const [membership, setMembership] = createSignal();

  const years = membershipYearOptions();
  const [year, setYear] = createSignal(years?.[0]);
  const [startDate, setStartDate] = createSignal("");
  const [endDate, setEndDate] = createSignal("");
  const [annual, setAnnual] = createSignal(true);
  const [ageRestricted, setAgeRestricted] = createSignal(false);

  const [event, setEvent] = createSignal();

  const [status, setStatus] = createSignal();

  const params = useParams();
  createEffect(() => {
    const player = findPlayerById(store.data, Number(params.playerId));
    setPlayer(player);
    setMembership(player?.membership);
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
    if (annual()) {
      // Set startDate and endDate based on selected year
      setStartDate(formatDate([...membershipStartDate, year()]));
      setEndDate(formatDate([...membershipEndDate, year() + 1]));
    } else if (event()) {
      setStartDate(event().start_date);
      setEndDate(event().end_date);
    }
  });

  const [payDisabled, setPayDisabled] = createSignal(false);

  createEffect(() => {
    const dob = player()?.date_of_birth;
    const [endDay, endMonth] = membershipEndDate;
    const seasonEnd = new Date(year() + 1, endMonth - 1, endDay);
    const age = annual()
      ? getAge(dob, seasonEnd)
      : getAge(dob, new Date(event()?.start_date));
    const noSelection = annual() ? !year() : !event();
    setAgeRestricted(age < minAge);
    setPayDisabled(noSelection || age < minAge);
  });

  const getAmount = () =>
    (annual()
      ? player()?.sponsored
        ? sponsoredAnnualMembershipFee
        : annualMembershipFee
      : eventMembershipFee) / 100;

  return (
    <div>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Membership" }
        ]}
      />
      <h1 class="text-2xl font-bold text-blue-500">Membership</h1>
      <Show
        when={!membership()?.is_active}
        fallback={
          <div id="membership-exist">
            Membership for {player().full_name} is active until{" "}
            {displayDate(membership().end_date)}
            <StatusStepper player={player()} />
          </div>
        }
      >
        <h3>Renew membership for {player()?.full_name}</h3>

        <div class="my-2">
          <label class="relative inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              value=""
              class="peer sr-only"
              checked={annual()}
              onChange={() => setAnnual(!annual())}
            />
            <div class="peer h-6 w-11 rounded-full bg-gray-200 after:absolute after:left-[2px] after:top-0.5 after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-blue-600 peer-checked:after:translate-x-full peer-checked:after:border-white peer-focus:ring-4 peer-focus:ring-blue-300 dark:border-gray-600 dark:bg-gray-700 dark:peer-focus:ring-blue-800" />
            <span class="ml-3 text-sm font-medium text-gray-900 dark:text-gray-300">
              Annual membership
            </span>
          </label>
          <Show when={annual()}>
            <select
              id="year"
              class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
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
              Pay India Ultimate membership fee (₹ {getAmount()}) valid for the
              period from {displayDate(startDate())} to {displayDate(endDate())}
            </p>
          </Show>
          <MembershipEventSelector
            event={event()}
            setEvent={setEvent}
            annual={annual()}
            startDate={startDate()}
            endDate={endDate()}
          />
          s{" "}
          <Show when={ageRestricted()}>
            <div
              class="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-gray-800 dark:text-red-400"
              role="alert"
            >
              {minAgeWarning}
            </div>
          </Show>
        </div>
        <RazorpayPayment
          disabled={payDisabled()}
          annual={annual()}
          year={year()}
          event={event()}
          player_id={player().id}
          amount={getAmount()}
          setStatus={setStatus}
        />
        <p>{status()}</p>
      </Show>
    </div>
  );
};

export default Membership;
