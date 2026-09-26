import { useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { heart, inboxStack } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import { minAge, minAgeWarning } from "../../constants";
import { fetchPlayerById, fetchSeasonPlans, fetchSeasons } from "../../queries";
import { displayDate, getAge } from "../../utils";
import Info from "../alerts/Info";
import Breadcrumbs from "../Breadcrumbs";
import PillTabs from "../tabs/PillTabs";
import GroupMembership from "./GroupMembership";
import ServiceRequestModal from "./ServiceRequestModal";
import TierPicker from "./TierPicker";

const Membership = () => {
  const [player, setPlayer] = createSignal();
  const [membership, setMembership] = createSignal();

  const [season, setSeason] = createSignal();
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
      setMembership(playerQuery.data?.membership);
    }
  });

  const seasonsQuery = createQuery(() => ["seasons"], fetchSeasons);

  createEffect(() => {
    if (seasonsQuery.isSuccess && seasonsQuery.data?.length > 0) {
      setSeason(seasonsQuery.data[0]);
    }
  });

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

  const handleSeasonChange = e => {
    setSeason(
      seasonsQuery.data?.filter(
        season => season.id === Number(e.target.value)
      )[0]
    );
  };

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
          { name: "Membership" }
        ]}
      />
      <h1 class="text-2xl font-bold text-blue-500">Membership</h1>

      <Show when={player()?.membership_number}>
        <p id="membership-number" class="mt-1 text-sm text-gray-500">
          Membership number: {player().membership_number}
        </p>
      </Show>

      <div class="my-2 rounded-lg bg-blue-50 p-4 text-sm " role="alert">
        <details>
          <summary class="text-blue-600">
            More Information about India Ultimate Membership
          </summary>
          <div class="my-2 space-y-2 text-sm">
            <p>
              Membership fees help cover India Ultimate's essential costs: WFDF
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
            { id: "individual", label: "Individual Membership" },
            { id: "group", label: "Group Membership" }
          ]}
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        <Show when={activeTab() === "individual"}>
          <div>
            <h1 class="text-lg font-semibold text-blue-500">
              Individual Membership
            </h1>
            <h3 class="text-sm italic">Membership for {player()?.full_name}</h3>
            <p class="mt-1 text-sm">
              Validity: {displayDate(season()?.start_date)} to{" "}
              {displayDate(season()?.end_date)}
            </p>

            <Show when={membership()?.is_active && membership()?.tier}>
              <div id="membership-exist" class="mt-4">
                {player()?.full_name} holds {membership().tier_name} until{" "}
                {displayDate(membership().end_date)}
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
                  <Info text="No memberships are on sale for this season." />
                </div>
              }
            >
              <TierPicker
                plans={onSale()}
                season={season()}
                playerId={player().id}
                heldSlug={
                  membership()?.season === season()?.id
                    ? membership()?.tier
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
                    If you'd like to request a discounted membership for
                    yourself and/or others, send us a request. Each approval
                    covers one season.
                  </p>
                </div>
              </div>
              <div class="shrink-0">
                <ServiceRequestModal
                  currentPlayer={player()}
                  season={season()}
                  buttonText="Request a discounted membership"
                />
              </div>
            </section>
          </div>
        </Show>

        <Show when={activeTab() === "group"}>
          <div class="space-y-2">
            <div>
              <h1 class="text-lg font-semibold text-blue-500">
                Group Membership
              </h1>
              <h3 class="text-sm italic">Pay for a group of players</h3>
            </div>

            <div class="mb-4">
              <ServiceRequestModal currentPlayer={player()} season={season()} />
            </div>

            <GroupMembership
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

export default Membership;
