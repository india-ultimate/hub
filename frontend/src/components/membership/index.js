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
  const [membershipType, setMembershipType] = createSignal("patron"); // "patron" or "standard"

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

  const getAmount = () => {
    if (!annual()) {
      return eventMembershipFee / 100;
    }

    // For annual membership, check membership type
    if (membershipType() === "patron") {
      return season()?.supporter_annual_membership_amount / 100;
    } else {
      // Standard membership
      return player()?.sponsored
        ? season()?.sponsored_annual_membership_amount / 100
        : season()?.annual_membership_amount / 100;
    }
  };

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
              Membership fees help cover India Ultimate’s essential costs: WFDF
              dues, audit, accountant, legal fees etc., along with the salary of
              at least one full-time staff member. Currently, IU has a team of a
              CEO, two senior operations executives, and one part-time staff.
            </p>
            <h2 class="text-base font-semibold text-gray-600 dark:text-white">
              Apart from helping sustain India Ultimate, what does your
              membership get you?
            </h2>
            <ul class="list-inside list-disc space-y-1">
              <li>
                Opportunity to participate in all state/national team tryouts
              </li>
              <li>
                Tournament Access - Eligible to play all IU-sanctioned
                tournaments (7+ annually)
              </li>
              <li>
                Opportunity for you to participate in WFDF recognised events
                through your club
              </li>
              <li>Coaching & Workshops</li>
              <li>Governance & Voice</li>
              <li>
                Credibility of your participation -- Certificates & recognition
              </li>
              <li>
                Updates & Content - IU newsletter + access to Hub (rostering,
                stats, schedules, scores)
              </li>
              <li>Contribute to growth of Flying Disc in India</li>
            </ul>
            <hr />
            <h2 class="text-base font-semibold text-gray-600 dark:text-white">
              Membership Fees
            </h2>
            <div>
              <details>
                <summary class="text-base font-bold">
                  Patron membership – Rs. 1500
                </summary>
                <p class="mt-2">
                  The <strong>Patron Membership</strong> is for those who wish
                  to actively support the growth of flying disc sports and
                  FDSF(I). As the number of members grows, so do the
                  responsibilities of the federation. To meet these needs, the
                  organisation continues to rely on the goodwill of the
                  community while working towards diversifying revenue streams,
                  including private sponsors and, in the long run, government
                  support. Recognising the different economic backgrounds within
                  our community, the Patron Membership at Rs. 1500 per year
                  helps subsidise the standard membership, ensuring equitable
                  sharing of responsibility. The usage of the membership fee is
                  explained in the pie chart below.
                </p>
              </details>
              <details>
                <summary class="mt-2 text-base font-bold">
                  Standard membership – Rs. 750
                </summary>
              </details>
              <details>
                <summary class="mt-2 text-base font-bold">
                  Supported Membership – Rs. 250 (on a need basis)
                </summary>
                <p class="mt-2">
                  <strong>Supported Membership</strong> is designed to increase
                  access to FDSF(I) membership for community members from
                  underserved social groups. By reducing entry-level barriers to
                  playing the sport, IU operations will grant a case-by-case
                  partial waiver to those who require subsidisation. Please
                  avail this option if needed.
                </p>
              </details>
            </div>

            <p class="my-2">
              If you, or players on your college/NGO team need assistance in
              paying this, then you can apply for supported membership{" "}
              <A
                class="cursor-pointer text-blue-500 underline"
                href="https://forms.gle/G2e18rjDjdDkmUKh7"
                target="_blank"
              >
                {" "}
                here.
              </A>
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
              <div class="mt-4">
                <label class="mb-2 block text-sm font-medium text-gray-900 dark:text-white">
                  Membership Type
                </label>
                <select
                  class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
                  value={membershipType()}
                  onChange={e => setMembershipType(e.target.value)}
                >
                  <option value="patron">
                    Patron Membership - ₹{" "}
                    {season()?.supporter_annual_membership_amount / 100}
                  </option>
                  <option value="standard">
                    Standard Membership - ₹{" "}
                    {season()?.annual_membership_amount / 100}
                  </option>
                </select>
              </div>
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
              membershipType={membershipType()}
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

          <GroupMembership
            season={season()}
            membershipType={membershipType()}
          />
        </div>
      </Show>
    </div>
  );
};

export default Membership;
