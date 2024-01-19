import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import {
  arrowSmallDown,
  arrowSmallUp,
  arrowUpRight,
  calendar,
  mapPin,
  trophy
} from "solid-heroicons/solid";
import {
  createEffect,
  createSignal,
  For,
  Match,
  onMount,
  Show,
  Suspense,
  Switch
} from "solid-js";

import {
  fetchTeams,
  fetchTournamentBySlug,
  fetchUserAccessByTournamentSlug
} from "../queries";
import {
  SpiritStandings as SpiritStandingsSkeleton,
  Standings as StandingsSkeleton
} from "../skeletons/Standings";
import { TournamentPageSkeleton } from "../skeletons/TournamentPage";
import Breadcrumbs from "./Breadcrumbs";

/**
 * @param {object} props
 * @param {number} props.currentSeed
 * @param {number} props.initialSeed
 */
const TeamSeedingChange = props => {
  return (
    <Switch>
      <Match when={props.currentSeed < props.initialSeed}>
        <div class="flex w-fit items-center justify-center space-x-1 text-green-500">
          <Icon path={arrowSmallUp} class="inline w-5 scale-90" />
          <span class="text-lg font-medium">
            {props.initialSeed - props.currentSeed}
          </span>
        </div>
      </Match>
      <Match when={props.currentSeed > props.initialSeed}>
        <div class="flex w-fit items-center justify-center space-x-1 text-red-500">
          <Icon path={arrowSmallDown} class="inline w-5 scale-90" />
          <span class="text-lg font-medium">
            {props.currentSeed - props.initialSeed}
          </span>
        </div>
      </Match>
    </Switch>
  );
};

const LocationAndDate = props => {
  const startDate = () =>
    new Date(Date.parse(props.startDate)).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      timeZone: "UTC"
    });

  const endDate = () =>
    new Date(Date.parse(props.endDate)).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      timeZone: "UTC"
    });

  return (
    <div class="mb-2 flex flex-col gap-2">
      <Suspense
        fallback={
          <div class="h-5 w-52 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
        }
      >
        <div class="text-sm">
          <Icon path={mapPin} class="mr-2 inline w-4" />
          <span>{props.location}</span>
        </div>
      </Suspense>

      <Suspense
        fallback={
          <div class="h-5 w-52 animate-pulse rounded-md bg-gray-400 dark:bg-gray-700/50" />
        }
      >
        <div class="text-sm">
          <Icon path={calendar} class="mr-2 inline w-4" />
          <span>
            {startDate()}
            <Show when={props.startDate !== props.endDate}>
              {" "}
              to {endDate()}
            </Show>
          </span>
        </div>
      </Suspense>
    </div>
  );
};

const Tournament = () => {
  const params = useParams();
  const [teamsMap, setTeamsMap] = createSignal({});
  const [teamsInitialSeeding, setTeamsInitialSeeding] = createSignal(undefined);

  const tournamentQuery = createQuery(
    () => ["tournament", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
  const teamsQuery = createQuery(() => ["teams"], fetchTeams);
  const userAccessQuery = createQuery(
    () => ["user-access", params.slug],
    () => fetchUserAccessByTournamentSlug(params.slug)
  );

  onMount(() => {
    setTimeout(() => initFlowbite(), 100);
    setTimeout(() => initFlowbite(), 500);
    setTimeout(() => initFlowbite(), 1000);
    setTimeout(() => initFlowbite(), 3000);
    setTimeout(() => initFlowbite(), 5000);
    setTimeout(() => initFlowbite(), 8000);
  });

  createEffect(() => {
    if (teamsQuery.status === "success") {
      let newTeamsMap = {};
      teamsQuery.data.map(team => {
        newTeamsMap[team.id] = team;
      });
      setTeamsMap(newTeamsMap);
    }
  });

  // using a derived signal instead, so we can use Suspense
  const derivedPlayingTeam = () => {
    const playingTeamID = userAccessQuery.data?.playing_team_id;
    if (playingTeamID !== 0) {
      return teamsMap()[playingTeamID];
    }
    return null;
  };

  createEffect(() => {
    if (tournamentQuery.status === "success" && !tournamentQuery.data.message) {
      const teamsInitialSeedingMap = {};

      Object.entries(tournamentQuery.data.initial_seeding).forEach(
        ([rank, teamId]) =>
          (teamsInitialSeedingMap[parseInt(teamId)] = parseInt(rank))
      );

      setTeamsInitialSeeding(teamsInitialSeedingMap);
    }
  });

  return (
    <Show
      when={!tournamentQuery.data?.message}
      fallback={
        <div>
          Tournament could not be fetched. Error -{" "}
          {tournamentQuery.data.message}
          <A href={"/tournaments"} class="text-blue-600 dark:text-blue-500">
            <br />
            Back to Tournaments Page
          </A>
        </div>
      }
    >
      <Breadcrumbs
        icon={trophy}
        pageList={[{ url: "/tournaments", name: "All Tournaments" }]}
      />
      <Suspense fallback={<TournamentPageSkeleton />}>
        {/* Tournament title and status badge */}
        <div class="px-1 py-3">
          <div class="mb-4 flex flex-col gap-2">
            <div>
              <Switch>
                <Match when={tournamentQuery.data?.status === "COM"}>
                  <span class="h-fit rounded bg-blue-100 px-2.5 py-1 text-sm font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                    Completed
                  </span>
                </Match>
                <Match when={tournamentQuery.data?.status === "LIV"}>
                  <span class="h-fit rounded bg-green-100 px-2.5 py-1 text-sm font-medium text-green-800 dark:bg-green-900 dark:text-green-300">
                    Live
                  </span>
                </Match>
              </Switch>
            </div>
            <h1 class="text-pretty text-2xl">
              <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text font-extrabold text-transparent">
                {tournamentQuery.data?.event?.title}
              </span>
            </h1>
          </div>

          {/* Tournament image or date+location */}
          <Show
            when={tournamentQuery.data?.logo_dark}
            fallback={
              <LocationAndDate
                location={tournamentQuery.data?.event?.location}
                startDate={tournamentQuery.data?.event?.start_date}
                endDate={tournamentQuery.data?.event?.end_date}
              />
            }
          >
            <div class="flex justify-start">
              <img
                src={tournamentQuery.data?.logo_dark}
                alt="Tournament logo"
                class="hidden aspect-square w-3/4 max-w-lg dark:block"
              />
              <img
                src={tournamentQuery.data?.logo_light}
                alt="Tournament logo"
                class="block aspect-square w-3/4 max-w-lg dark:hidden"
              />
            </div>
          </Show>
        </div>

        {/* Tournament sections buttons */}
        <div class="my-4 flex flex-col gap-4">
          <Show when={derivedPlayingTeam()}>
            <div class="w-full rounded-lg bg-gradient-to-br from-pink-600 to-orange-400 p-px shadow-md">
              <A
                href={`/tournament/${params.slug}/team/${
                  derivedPlayingTeam().ultimate_central_slug
                }`}
              >
                <div class="flex w-full flex-col items-start gap-2 rounded-lg bg-white px-3.5 py-4 text-center dark:bg-gray-800">
                  <div class="flex w-full flex-row justify-between">
                    <span class="text-left">
                      <span class="text-normal text-lg">{"Your team - "}</span>
                      <span class="inline-block bg-gradient-to-br from-orange-400 to-pink-500 bg-clip-text text-lg font-bold text-transparent">
                        {derivedPlayingTeam().name}
                      </span>
                    </span>
                    <span>
                      <Icon path={arrowUpRight} class="inline w-5" />
                    </span>
                  </div>
                  <div class="text-left text-sm capitalize">
                    the matches and roster of your team
                  </div>
                </div>
              </A>
            </div>
          </Show>
          <div class="w-full rounded-lg border border-blue-600 bg-white px-4 py-4 shadow-lg dark:border-blue-400/50 dark:bg-gray-800">
            <A href={`/tournament/${params.slug}/schedule`}>
              <div class="flex w-full flex-col items-start gap-2">
                <div class="flex w-full flex-row justify-between">
                  <span class="text-lg font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
                    Schedule
                  </span>
                  <span>
                    <Icon path={arrowUpRight} class="inline w-5" />
                  </span>
                </div>
                <div class="text-sm capitalize">
                  the detailed schedule of matches
                </div>
              </div>
            </A>
          </div>
          <div class="w-full rounded-lg border border-blue-600 bg-white px-4 py-4 shadow-lg dark:border-blue-400/50 dark:bg-gray-800">
            <A href={`/tournament/${params.slug}/standings`}>
              <div class="flex w-full flex-col items-start gap-2">
                <div class="flex w-full flex-row justify-between">
                  <span class="text-lg font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
                    Standings
                  </span>
                  <span>
                    <Icon path={arrowUpRight} class="inline w-5" />
                  </span>
                </div>
                <div class="text-sm capitalize">
                  the pools, brackets and the detailed standings
                </div>
              </div>
            </A>
          </div>
          <Show when={tournamentQuery.data?.rules}>
            <div class="w-full rounded-lg border border-blue-600 bg-white px-4 py-4 shadow-lg dark:border-blue-400/50 dark:bg-gray-800">
              <A href={`/tournament/${params.slug}/rules`}>
                <div class="flex w-full flex-col items-start gap-2">
                  <div class="flex w-full flex-row justify-between">
                    <span class="text-lg font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
                      Rules
                    </span>
                    <span>
                      <Icon path={arrowUpRight} class="inline w-5" />
                    </span>
                  </div>
                  <div class="text-sm capitalize">
                    the rules and format of the tournament
                  </div>
                </div>
              </A>
            </div>
          </Show>
        </div>

        <h2 class="mb-2 mt-8 px-1 text-xl font-bold">Overall Standings</h2>
      </Suspense>

      <div class="mb-4 border-b border-gray-200 px-1 dark:border-gray-700">
        <ul
          class="-mb-px flex flex-wrap justify-start space-x-4 text-sm font-medium"
          id="myTab"
          data-tabs-toggle="#myTabContent"
          role="tablist"
        >
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 py-4 pl-1 pr-4"
              id={"tab-current"}
              data-tabs-target={"#current"}
              type="button"
              role="tab"
              aria-controls={"current"}
              aria-selected="false"
            >
              <Suspense fallback={"Current"}>
                <Switch>
                  <Match when={tournamentQuery.data?.status === "COM"}>
                    Final
                  </Match>
                  <Match when={tournamentQuery.data?.status === "LIV"}>
                    Current
                  </Match>
                </Switch>
              </Suspense>
            </button>
          </li>
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 py-4 pl-1 pr-4"
              id={"tab-initial"}
              data-tabs-target={"#initial"}
              type="button"
              role="tab"
              aria-controls={"initial"}
              aria-selected="false"
            >
              Initial
            </button>
          </li>
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 py-4 pl-1 pr-4"
              id={"tab-sotg"}
              data-tabs-target={"#sotg"}
              type="button"
              role="tab"
              aria-controls={"sotg"}
              aria-selected="false"
            >
              SoTG
            </button>
          </li>
        </ul>
      </div>
      <div id="myTabContent">
        <div
          class="hidden rounded-lg py-2"
          id={"current"}
          role="tabpanel"
          aria-labelledby={"tab-current"}
        >
          <div class="relative overflow-x-auto rounded-lg shadow-md">
            <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
              <tbody>
                <Suspense fallback={<StandingsSkeleton />}>
                  <For
                    each={Object.entries(
                      tournamentQuery.data?.current_seeding || {}
                    )}
                  >
                    {([rank, team_id]) => (
                      <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                        <th
                          scope="row"
                          class="whitespace-nowrap py-4 pl-4 pr-2 font-normal"
                        >
                          {rank}
                        </th>
                        <td class="px-2 py-4">
                          <A
                            href={`/tournament/${params.slug}/team/${
                              teamsMap()[team_id]?.ultimate_central_slug
                            }`}
                          >
                            <img
                              class="mr-3 inline-block h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                              src={teamsMap()[team_id]?.image_url}
                              alt="Bordered avatar"
                            />
                            {teamsMap()[team_id]?.name}
                          </A>
                        </td>
                        <Show when={teamsInitialSeeding()}>
                          <td class="px-2">
                            <TeamSeedingChange
                              initialSeed={teamsInitialSeeding()[team_id]}
                              currentSeed={parseInt(rank)}
                            />
                          </td>
                        </Show>
                      </tr>
                    )}
                  </For>
                </Suspense>
              </tbody>
            </table>
          </div>
        </div>
        <div
          class="hidden rounded-lg py-2"
          id={"initial"}
          role="tabpanel"
          aria-labelledby={"tab-initial"}
        >
          <div class="relative overflow-x-auto rounded-lg shadow-md">
            <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
              <tbody>
                <Suspense fallback={<StandingsSkeleton />}>
                  <For
                    each={Object.entries(
                      tournamentQuery.data?.initial_seeding || {}
                    )}
                  >
                    {([rank, team_id]) => (
                      <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                        <th
                          scope="row"
                          class="whitespace-nowrap py-4 pl-4 font-normal"
                        >
                          {rank}
                        </th>
                        <td class="px-2 py-4">
                          <A
                            href={`/tournament/${params.slug}/team/${
                              teamsMap()[team_id]?.ultimate_central_slug
                            }`}
                          >
                            <img
                              class="mr-3 inline-block h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                              src={teamsMap()[team_id]?.image_url}
                              alt="Bordered avatar"
                            />
                            {teamsMap()[team_id]?.name}
                          </A>
                        </td>
                      </tr>
                    )}
                  </For>
                </Suspense>
              </tbody>
            </table>
          </div>
        </div>
        <div
          class="hidden rounded-lg py-2"
          id={"sotg"}
          role="tabpanel"
          aria-labelledby={"tab-sotg"}
        >
          <Suspense fallback={<SpiritStandingsSkeleton />}>
            <Show
              when={tournamentQuery.data?.spirit_ranking.length > 0}
              fallback={
                <div
                  class="my-4 rounded-lg bg-blue-50 p-2 text-sm dark:bg-gray-800"
                  role="alert"
                >
                  <p class="text-center">
                    Spirit rankings is not yet available.
                    <br />
                    Please check after some time!
                  </p>
                </div>
              }
            >
              <div class="relative overflow-x-auto rounded-lg shadow-md">
                <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                  <tbody>
                    <For each={tournamentQuery.data?.spirit_ranking}>
                      {spirit => (
                        <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                          <th
                            scope="row"
                            class="whitespace-nowrap px-2 py-4 font-normal"
                          >
                            {spirit.rank}
                          </th>
                          <td class="px-3 py-4">
                            <A
                              href={`/tournament/${params.slug}/team/${
                                teamsMap()[spirit.team_id]
                                  ?.ultimate_central_slug
                              }`}
                            >
                              <img
                                class="mr-3 inline-block h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                                src={teamsMap()[spirit.team_id]?.image_url}
                                alt="Bordered avatar"
                              />
                              {teamsMap()[spirit.team_id]?.name}
                            </A>
                          </td>
                          <td class="px-3 py-4">
                            {spirit.points}
                            <Show when={spirit.self_points}>
                              ({spirit.self_points})
                            </Show>
                          </td>
                        </tr>
                      )}
                    </For>
                  </tbody>
                </table>
              </div>
              <p class="mt-2 text-right text-sm italic">
                * Self scores are in brackets
              </p>
            </Show>
          </Suspense>
        </div>
      </div>
    </Show>
  );
};

export default Tournament;
