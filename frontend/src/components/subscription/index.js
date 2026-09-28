import { useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { inboxStack } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import { eventSubscriptionFee, minAge, minAgeWarning } from "../../constants";
import { fetchPlayerById, fetchSeasons } from "../../queries";
import { displayDate, getAge } from "../../utils";
import Info from "../alerts/Info";
import Breadcrumbs from "../Breadcrumbs";
import RazorpayPayment from "../RazorpayPayment";
import PillTabs from "../tabs/PillTabs";
import GroupSubscription from "./GroupSubscription";
import ServiceRequestModal from "./ServiceRequestModal";

const Subscription = () => {
  const [player, setPlayer] = createSignal();
  const [subscription, setSubscription] = createSignal();

  const [season, setSeason] = createSignal();
  const [annual, _setAnnual] = createSignal(true);
  const [ageRestricted, setAgeRestricted] = createSignal(false);
  const [subscriptionType, setSubscriptionType] = createSignal("patron"); // "patron" or "standard"

  const [event, _setEvent] = createSignal();

  const [status, setStatus] = createSignal();
  const [activeTab, setActiveTab] = createSignal("individual");

  const params = useParams();

  const playerQuery = createQuery(
    () => ["player", params.playerId],
    () => fetchPlayerById(Number(params.playerId))
  );

  createEffect(() => {
    if (playerQuery.isSuccess && playerQuery.data) {
      setPlayer(playerQuery.data);
      setSubscription(playerQuery.data?.subscription);
    }
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
      return eventSubscriptionFee / 100;
    }

    // For annual subscription, check subscription type and sponsored status
    if (player()?.sponsored) {
      return season()?.sponsored_annual_subscription_amount / 100;
    } else {
      return subscriptionType() === "patron"
        ? season()?.supporter_annual_subscription_amount / 100
        : season()?.annual_subscription_amount / 100;
    }
  };

  return (
    <div>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Subscription" }
        ]}
      />
      <h1 class="text-2xl font-bold text-blue-500">Subscription</h1>

      <div class="my-2 rounded-lg bg-blue-50 p-4 text-sm " role="alert">
        <details>
          <summary class="text-blue-600">
            More Information about India Ultimate Subscription
          </summary>
          <div class="my-2 space-y-2 text-sm">
            <p>
              Subscription fees help cover India Ultimate's essential costs:
              WFDF dues, audit, accountant, legal fees etc., along with the
              salary of at least one full-time staff member. Currently, IU has a
              team of a CEO, two senior operations executives, and one part-time
              staff.
            </p>
            <h2 class="text-base font-semibold text-gray-600 dark:text-white">
              Apart from helping sustain India Ultimate, what does your
              subscription get you?
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
              Subscription Fees
            </h2>
            <div>
              <details>
                <summary class="text-base font-bold">
                  Patron subscription – Rs. 1500
                </summary>
                <p class="mt-2">
                  The <strong>Patron Subscription</strong> is for those who wish
                  to actively support the growth of flying disc sports and
                  FDSF(I). As the number of members grows, so do the
                  responsibilities of the federation. To meet these needs, the
                  organisation continues to rely on the goodwill of the
                  community while working towards diversifying revenue streams,
                  including private sponsors and, in the long run, government
                  support. Recognising the different economic backgrounds within
                  our community, the Patron Subscription at Rs. 1500 per year
                  helps subsidise the standard subscription, ensuring equitable
                  sharing of responsibility. The usage of the subscription fee
                  is explained in the pie chart below.
                </p>
              </details>
              <details>
                <summary class="mt-2 text-base font-bold">
                  Standard subscription – Rs. 750
                </summary>
              </details>
              <details>
                <summary class="mt-2 text-base font-bold">
                  Supported Subscription – Rs. 250 (on a need basis)
                </summary>
                <p class="mt-2">
                  <strong>Supported Subscription</strong> is designed to
                  increase access to FDSF(I) subscription for community members
                  from underserved social groups. By reducing entry-level
                  barriers to playing the sport, IU operations will grant a
                  case-by-case partial waiver to those who require
                  subsidisation. Please avail this option if needed.
                </p>
              </details>
            </div>

            <p class="my-2">
              If you, or players on your college/NGO team need assistance in
              paying this, then you can apply for supported subscription by
              clicking the button below.
            </p>

            <div class="my-4">
              <ServiceRequestModal currentPlayer={player()} />
            </div>
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
        <PillTabs
          tabs={[
            { id: "individual", label: "Individual Subscription" },
            { id: "group", label: "Group Subscription" }
          ]}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        <Show when={activeTab() === "individual"}>
          <div>
            <h1 class="text-lg font-semibold text-blue-500">
              Individual Subscription
            </h1>
            <h3 class="text-sm italic">
              Renew subscription for {player()?.full_name}
            </h3>
            <Show
              when={!subscription()?.is_active}
              fallback={
                <div id="subscription-exist" class="mt-4">
                  Subscription for {player().full_name} is active until{" "}
                  {displayDate(subscription().end_date)}
                </div>
              }
            >
              <Show when={annual()}>
                <div class="mt-4">
                  <label class="mb-2 block text-sm font-medium text-gray-900 dark:text-white">
                    Subscription Type
                  </label>
                  <Show
                    when={!player()?.sponsored}
                    fallback={
                      <div class="block w-full rounded-lg border border-gray-300 bg-gray-100 p-2.5 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white">
                        Supported Subscription – ₹{" "}
                        {season()?.sponsored_annual_subscription_amount / 100}
                      </div>
                    }
                  >
                    <select
                      class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
                      value={subscriptionType()}
                      onChange={e => setSubscriptionType(e.target.value)}
                    >
                      <option value="patron">
                        Patron Subscription - ₹{" "}
                        {season()?.supporter_annual_subscription_amount / 100}
                      </option>
                      <option value="standard">
                        Standard Subscription - ₹{" "}
                        {season()?.annual_subscription_amount / 100}
                      </option>
                    </select>
                  </Show>
                </div>
                <p class="mt-4 font-bold">
                  Paying India Ultimate subscription fee:
                </p>
                <p class="mt-1">
                  Validity: {displayDate(season()?.start_date)} to{" "}
                  {displayDate(season()?.end_date)}
                </p>
                <p class="mt-1 font-extrabold">Total Amount: ₹ {getAmount()}</p>
              </Show>
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
                is_supporter={subscriptionType() === "patron"}
                successCallback={() => {
                  playerQuery.refetch();
                }}
              />
              <p>{status()}</p>
            </Show>
          </div>
        </Show>

        <Show when={activeTab() === "group"}>
          <div class="space-y-2">
            <div>
              <h1 class="text-lg font-semibold text-blue-500">
                Group Subscription
              </h1>
              <h3 class="text-sm italic">Renew subscription for a group</h3>
            </div>

            <div class="mb-4">
              <ServiceRequestModal currentPlayer={player()} />
            </div>

            <GroupSubscription
              season={season()}
              subscriptionType={subscriptionType()}
              successCallback={() => {
                playerQuery.refetch();
              }}
            />
          </div>
        </Show>
      </Show>
    </div>
  );
};

export default Subscription;
