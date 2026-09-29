import { useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { heart, inboxStack } from "solid-heroicons/solid";
import { createEffect, createSignal, Show } from "solid-js";

import { minAge, minAgeWarning } from "../../constants";
import {
  fetchCurrentSeason,
  fetchPlayerById,
  fetchSeasonPlans
} from "../../queries";
import { displayDate, getAge } from "../../utils";
import Error from "../alerts/Error";
import Info from "../alerts/Info";
import Breadcrumbs from "../Breadcrumbs";
import IUIDBadge from "../IUIDBadge";
import PillTabs from "../tabs/PillTabs";
import GroupSubscription from "./GroupSubscription";
import ServiceRequestModal from "./ServiceRequestModal";
import TierPicker from "./TierPicker";

const Subscription = () => {
  const [player, setPlayer] = createSignal();
  const [subscription, setSubscription] = createSignal();

  const [ageRestricted, setAgeRestricted] = createSignal(false);

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

  const seasonQuery = createQuery(() => ["current-season"], fetchCurrentSeason);
  const season = () => seasonQuery.data ?? undefined;

  // Every price and every "can they buy this" comes from here. The page
  // renders the server's answer and never works one out for itself.
  const plansQuery = createQuery(
    () => ["season-plans", season()?.id, player()?.id],
    () => fetchSeasonPlans(season().id, player().id),
    {
      get enabled() {
        return Boolean(season()?.id && player()?.id);
      }
    }
  );

  createEffect(() => {
    const age = getAge(player()?.date_of_birth, new Date(season()?.end_date));
    setAgeRestricted(age < minAge);
  });

  const onSale = () => plansQuery.data ?? [];

  return (
    <div>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Subscription" }
        ]}
      />
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h1 class="text-2xl font-bold text-blue-500">Subscription</h1>
        <IUIDBadge id={player()?.iu_id} />
      </div>

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
              <li>Coaching &amp; Workshops</li>
              <li>Governance &amp; Voice</li>
              <li>
                Credibility of your participation -- Certificates &amp;
                recognition
              </li>
              <li>
                Updates &amp; Content - IU newsletter + access to Hub
                (rostering, stats, schedules, scores)
              </li>
              <li>Contribute to growth of Flying Disc in India</li>
            </ul>
          </div>
        </details>
      </div>

      <Show
        when={season()}
        fallback={
          <div class="my-4">
            <Show when={seasonQuery.isError}>
              <Error text="Could not load the current season. Please try again." />
            </Show>
            <Show when={seasonQuery.isSuccess}>
              <Info text="There is no subscription season running right now. Please check back later." />
            </Show>
          </div>
        }
      >
        <h2 class="mt-4 text-lg font-semibold text-gray-900 dark:text-white">
          {season().name}
        </h2>
        <p class="mb-4 text-sm text-gray-500 dark:text-gray-400">
          {displayDate(season().start_date)} to {displayDate(season().end_date)}
        </p>

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
            <h3 class="text-lg font-semibold text-blue-500">
              Individual Subscription
            </h3>
            <p class="text-sm italic">Subscription for {player()?.full_name}</p>

            <Show
              when={
                subscription()?.is_active &&
                subscription()?.tier &&
                subscription()?.season === season()?.id
              }
            >
              <div id="subscription-exist" class="mt-4">
                {player()?.full_name} holds {subscription().tier_name} until{" "}
                {displayDate(subscription().end_date)}
              </div>
            </Show>

            <Show when={ageRestricted()}>
              <div
                class="my-4 rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-gray-800 dark:text-red-400"
                role="alert"
              >
                {minAgeWarning}
              </div>
            </Show>

            <Show
              when={onSale().length > 0}
              fallback={
                <div class="my-4">
                  <Info text="No subscriptions are on sale for this season." />
                </div>
              }
            >
              <TierPicker
                plans={onSale()}
                season={season()}
                playerId={player().id}
                heldSlug={
                  subscription()?.season === season()?.id
                    ? subscription()?.tier
                    : null
                }
                disabled={ageRestricted()}
                setStatus={setStatus}
                onPaid={() => {
                  playerQuery.refetch();
                  plansQuery.refetch();
                }}
              />
            </Show>
            <p class="mt-2 text-sm">{status()}</p>

            {/* Open to anyone: a request can cover this person, others, or
                both, whatever they hold now. */}
            <section class="mt-10 flex flex-col gap-4 rounded-2xl border border-blue-100 bg-blue-50 p-6 dark:border-gray-700 dark:bg-gray-800 sm:flex-row sm:items-center sm:justify-between">
              <div class="flex gap-4">
                <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-gray-700">
                  <Icon
                    path={heart}
                    class="h-5 w-5 text-blue-600 dark:text-blue-400"
                    aria-hidden="true"
                  />
                </span>
                <div>
                  <h2 class="text-base font-semibold text-gray-900 dark:text-white">
                    Need help with the fee?
                  </h2>
                  <p class="mt-1 max-w-xl text-sm text-gray-600 dark:text-gray-300">
                    If you'd like to request a discounted subscription for
                    yourself and/or others, send us a request. Each approval
                    covers one season.
                  </p>
                </div>
              </div>
              <div class="shrink-0">
                <ServiceRequestModal
                  currentPlayer={player()}
                  season={season()}
                  buttonText="Request a discounted subscription"
                />
              </div>
            </section>
          </div>
        </Show>

        <Show when={activeTab() === "group"}>
          <div class="space-y-2">
            <div>
              <h3 class="text-lg font-semibold text-blue-500">
                Group Subscription
              </h3>
              <p class="text-sm italic">Pay for a group of players</p>
            </div>

            <div class="mb-4">
              <ServiceRequestModal currentPlayer={player()} season={season()} />
            </div>

            <GroupSubscription
              season={season()}
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
