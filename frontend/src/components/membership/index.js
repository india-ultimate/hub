import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { inboxStack } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import { eventMembershipFee, minAge, minAgeWarning } from "../../constants";
import { fetchSeasons } from "../../queries";
import { useStore } from "../../store";
import { displayDate, findPlayerById, getAge } from "../../utils";
import Info from "../alerts/Info";
import Breadcrumbs from "../Breadcrumbs";
import RazorpayPayment from "../RazorpayPayment";
import GroupMembership from "./GroupMembership";

const Membership = () => {
  const [store] = useStore();

  const [player, setPlayer] = createSignal();
  const [membership, setMembership] = createSignal();

  const [season, setSeason] = createSignal();
  const [annual, _setAnnual] = createSignal(true);
  const [ageRestricted, setAgeRestricted] = createSignal(false);

  const [event, _setEvent] = createSignal();

  const [status, setStatus] = createSignal();

  const params = useParams();
  createEffect(() => {
    const player = findPlayerById(store.data, Number(params.playerId));
    setPlayer(player);
    setMembership(player?.membership);
  });

  const seasonsQuery = createQuery(() => ["seasons"], fetchSeasons);

  createEffect(() => {
    if (seasonsQuery.isSuccess && seasonsQuery.data?.length > 0) {
      setSeason(seasonsQuery.data[0]);
    }
  });

  const handleSeasonChange = e => {
    setSeason(
      seasonsQuery.data?.filter(
        season => season.id === Number(e.target.value)
      )[0]
    );
  };

  const [payDisabled, setPayDisabled] = createSignal(false);

  createEffect(() => {
    const dob = player()?.date_of_birth;
    const seasonEnd = new Date(season()?.end_date);
    const age = annual()
      ? getAge(dob, seasonEnd)
      : getAge(dob, new Date(event()?.start_date));
    const noSelection = annual() ? !season() : !event();
    setAgeRestricted(age < minAge);
    setPayDisabled(noSelection || age < minAge);
  });

  const getAmount = () =>
    (annual()
      ? player()?.sponsored
        ? season()?.sponsored_annual_membership_amount
        : season()?.annual_membership_amount
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

      <div class="my-2 rounded-lg bg-blue-50 p-4 text-sm " role="alert">
        <details>
          <summary class="text-blue-600">
            More Information about India Ultimate Membership
          </summary>
          <div class="my-2 space-y-2 text-sm">
            <p>
              The membership fees are designed to cover the bare-bone needs of
              the organisation. Which is paying WFDF, Auditor, Accounting and
              legal fees along with the expense of 1 Ops executive.
            </p>
            <h2 class="text-base font-semibold text-gray-600 dark:text-white">
              Apart from helping sustain India Ultimate, what does your
              membership get you?
            </h2>
            <ul class="list-inside list-disc space-y-1">
              <li>Opportunity to participate in all state/national tryouts</li>
              <li>Access to all IU tournaments, 7+ annually</li>
              <li>
                Opportunity for you to participate in WFDF recognised events
                through your club
              </li>
              <li>Access to all coaching certification programs</li>
              <li>
                Opportunity to voice your opinion with issues and decisions in
                IU going ahead
              </li>
              <li>
                Credibility of your participation -- Certificates & recognition
              </li>
              <li>
                All access to the present future features of the Hub such as
                rostering statistics, schedules, live scores etc.
              </li>
            </ul>
            <hr />
            <p>
              Regular full membership = Rs. 700 a year. This comes to Rs. 58 per
              month.
            </p>
            <p class="my-2">
              If you, or players on your college/NGO team need assistance in
              paying this, then you can apply for discounted membership{" "}
              <A
                class="cursor-pointer text-blue-500 underline"
                href="https://forms.gle/G2e18rjDjdDkmUKh7"
                target="_blank"
              >
                {" "}
                here.
              </A>
            </p>
            <p>
              If you're comfortable paying the annual membership to support the
              growth of Ultimate in the country then you DON'T need to fill this
              form.
            </p>
          </div>
        </details>
      </div>

      <select
        id="year"
        class="mt-4 block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900  focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
        value={season()?.id}
        onInput={handleSeasonChange}
        required
      >
        <For each={seasonsQuery.data || []}>
          {season => <option value={season.id}>{season.name}</option>}
        </For>
      </select>

      <Show
        when={season()}
        fallback={
          <div class="my-4">
            <Info text="Please select a season" />
          </div>
        }
      >
        <div class="mb-4 mt-2 border-b border-gray-200 dark:border-gray-700">
          <ul
            class="-mb-px flex flex-wrap justify-center text-center text-sm font-medium"
            id="myTab"
            data-tabs-toggle="#myTabContent"
            role="tablist"
          >
            <li class="mr-2" role="presentation">
              <button
                class="inline-block rounded-t-lg border-b-2 p-4"
                id="tab-individual"
                data-tabs-target="#individual"
                type="button"
                role="tab"
                aria-controls="individual"
                aria-selected="false"
              >
                Individual Membership
              </button>
            </li>
            <li class="mr-2" role="presentation">
              <button
                class="inline-block rounded-t-lg border-b-2 p-4"
                id="tab-group"
                data-tabs-target="#group"
                type="button"
                role="tab"
                aria-controls="group"
                aria-selected="false"
              >
                Group Membership
              </button>
            </li>
          </ul>
        </div>

        <div id="individual">
          <h1 class="text-lg font-semibold text-blue-500">
            Individual Membership
          </h1>
          <h3 class="text-sm italic">
            Renew membership for {player()?.full_name}
          </h3>
          <Show
            when={!membership()?.is_active}
            fallback={
              <div id="membership-exist" class="mt-4">
                Membership for {player().full_name} is active until{" "}
                {displayDate(membership().end_date)}
              </div>
            }
          >
            {/* <label class="relative inline-flex cursor-pointer items-center">
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
          </label> */}
            <Show when={annual()}>
              <p class="mt-4 font-bold">
                Paying India Ultimate membership fee:
              </p>
              <p class="mt-1">
                Validity: {displayDate(season()?.start_date)} to{" "}
                {displayDate(season()?.end_date)}
              </p>
              <p class="mt-1 font-extrabold">Total Amount: ₹ {getAmount()}</p>
            </Show>
            {/* <MembershipEventSelector
            event={event()}
            setEvent={setEvent}
            annual={annual()}
            startDate={startDate()}
            endDate={endDate()}
          /> */}
            <Show when={ageRestricted()}>
              <div
                class="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-gray-800 dark:text-red-400"
                role="alert"
              >
                {minAgeWarning}
              </div>
            </Show>
            <RazorpayPayment
              disabled={payDisabled()}
              annual={annual()}
              season={season()}
              event={event()}
              player_id={player().id}
              amount={getAmount()}
              setStatus={setStatus}
            />
            <p>{status()}</p>
          </Show>
        </div>

        <div class="space-y-2" id="group">
          <div>
            <h1 class="text-lg font-semibold text-blue-500">
              Group Membership
            </h1>
            <h3 class="text-sm italic">Renew membership for a group</h3>
          </div>

          <GroupMembership season={season()} />
        </div>
      </Show>
    </div>
  );
};

export default Membership;
