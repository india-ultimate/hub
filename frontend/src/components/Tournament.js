import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import { arrowSmallDown, arrowSmallUp, trophy } from "solid-heroicons/solid";
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
  fetchTournamentBySlug,
  fetchUserAccessByTournamentSlug
} from "../queries";
import {
  SpiritStandings as SpiritStandingsSkeleton,
  Standings as StandingsSkeleton
} from "../skeletons/Standings";
import { ifTodayInBetweenDates, latestDate } from "../utils";
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

const Tournament = () => {
  const params = useParams();
  const [teamsMap, setTeamsMap] = createSignal({});
  const [teamsInitialSeeding, setTeamsInitialSeeding] = createSignal(undefined);
  const [playingTeam, setPlayingTeam] = createSignal(null);

  const tournamentQuery = createQuery(
    () => ["tournaments", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
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
    if (userAccessQuery.status == "success") {
      const playingTeamID = userAccessQuery.data?.playing_team_id;
      if (playingTeamID !== 0) {
        setPlayingTeam(teamsMap()[playingTeamID]);
      }
    }
  });

  createEffect(() => {
    if (tournamentQuery.status === "success" && !tournamentQuery.data.message) {
      const teamsInitialSeedingMap = {};

      Object.entries(tournamentQuery.data.initial_seeding).forEach(
        ([rank, teamId]) =>
          (teamsInitialSeedingMap[parseInt(teamId)] = parseInt(rank))
      );

      setTeamsInitialSeeding(teamsInitialSeedingMap);

      let newTeamsMap = {};
      tournamentQuery.data?.teams.map(team => {
        newTeamsMap[team.id] = team;
      });
      setTeamsMap(newTeamsMap);
    }
  });

  const isPlayerRegInProgress = () => {
    return ifTodayInBetweenDates(
      tournamentQuery.data?.event?.player_registration_start_date,
      latestDate(
        tournamentQuery.data?.event?.player_late_penalty_end_date,
        tournamentQuery.data?.event?.player_registration_end_date
      )
    );
  };

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

      <h1 class="mb-5 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-2xl font-extrabold text-transparent">
          {tournamentQuery.data?.event?.title}
        </span>
      </h1>

      <Show
        when={tournamentQuery.data?.logo_dark}
        fallback={
          <div>
            <p class="mt-2 text-center text-sm">
              {tournamentQuery.data?.event?.location}
            </p>
            <p class="mt-2 text-center text-sm">
              {new Date(
                Date.parse(tournamentQuery.data?.event.start_date)
              ).toLocaleDateString("en-US", {
                year: "numeric",
                month: "short",
                day: "numeric",
                timeZone: "UTC"
              })}
              <Show
                when={
                  tournamentQuery.data?.event.start_date !==
                  tournamentQuery.data?.event.end_date
                }
              >
                {" "}
                to{" "}
                {new Date(
                  Date.parse(tournamentQuery.data?.event.end_date)
                ).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  timeZone: "UTC"
                })}
              </Show>
            </p>
          </div>
        }
      >
        <div class="flex justify-center">
          <img
            src={tournamentQuery.data?.logo_dark}
            alt="Tournament logo"
            class="hidden w-3/4 dark:block"
          />
          <img
            src={tournamentQuery.data?.logo_light}
            alt="Tournament logo"
            class="block w-3/4 dark:hidden"
          />
        </div>
      </Show>

      <div class="mt-5 flex justify-center">
        <Switch>
          <Match when={tournamentQuery.data?.status === "COM"}>
            <span class="mr-2 h-fit rounded bg-blue-100 px-2.5 py-0.5 text-sm font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-300">
              Completed
            </span>
          </Match>
          <Match when={tournamentQuery.data?.status === "LIV"}>
            <span class="mr-2 h-fit rounded bg-green-100 px-2.5 py-0.5 text-sm font-medium text-green-800 dark:bg-green-900 dark:text-green-300">
              Live
            </span>
          </Match>
        </Switch>
      </div>
      <Show when={playingTeam()}>
        <A
          href={`/tournament/${params.slug}/team/${playingTeam().slug}`}
          //
          class="mt-5 block w-full rounded-lg bg-gradient-to-br from-pink-600 to-orange-400 p-0.5 shadow-md"
        >
          <div class="rounded-md bg-white p-4 dark:bg-gray-800">
            <h5 class="mb-2 text-center text-xl tracking-tight">
              <span class="font-normal">Your team - </span>
              <span class="bg-gradient-to-br from-orange-400 to-pink-500 bg-clip-text font-bold text-transparent">
                {playingTeam().name}
              </span>
            </h5>
            <p class="text-center text-sm capitalize">
              View the matches and roster of your team
            </p>
          </div>
        </A>
      </Show>
      <A
        href={`/tournament/${params.slug}/schedule`}
        class="mt-5 block w-full rounded-lg  border border-blue-600 bg-white p-4 shadow-md dark:border-blue-400 dark:bg-gray-800"
      >
        <h5 class="mb-2 text-center text-xl font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
          Schedule
        </h5>
        <p class="text-center text-sm capitalize">
          View the detailed schedule of matches
        </p>
      </A>
      <A
        href={`/tournament/${params.slug}/standings`}
        class="mt-5 block w-full rounded-lg border border-blue-600 bg-white p-4 shadow-md dark:border-blue-400 dark:bg-gray-800"
      >
        <h5 class="mb-2 text-center text-xl font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
          Standings
        </h5>
        <p class="text-center text-sm capitalize">
          View the pools, brackets and the detailed standings
        </p>
      </A>
      <A
        href={`/tournament/${params.slug}/leaderboard`}
        class="mt-5 block w-full rounded-lg border border-blue-600 bg-white p-4 shadow-md dark:border-blue-400 dark:bg-gray-800"
      >
        <h5 class="mb-2 text-center text-xl font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
          Leaderboard
        </h5>
        <p class="text-center text-sm capitalize">
          View the players with the top scores, assists and blocks
        </p>
      </A>
      <Show when={tournamentQuery.data?.rules}>
        <A
          href={`/tournament/${params.slug}/rules`}
          class="mt-5 block w-full rounded-lg border border-blue-600 bg-white p-4 shadow dark:border-blue-400 dark:bg-gray-800"
        >
          <h5 class="mb-2 text-center text-xl font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
            Rules & Format
          </h5>
          <p class="text-center text-sm capitalize">
            View the detailed rules and format of the tournament
          </p>
        </A>
      </Show>
      <Show when={isPlayerRegInProgress()}>
        <A
          href={`/tournament/${params.slug}/register`}
          class="mt-5 block w-full rounded-lg border border-blue-600 bg-white p-4 shadow-md dark:border-blue-400 dark:bg-gray-800"
        >
          <h5 class="mb-2 text-center text-xl font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
            Player Registrations
          </h5>
          <p class="text-center text-sm capitalize">
            Open till{" "}
            <span class="inline-flex font-medium">
              {new Date(
                Date.parse(
                  tournamentQuery.data?.event?.player_registration_end_date
                )
              ).toLocaleDateString("en-US", {
                year: "numeric",
                month: "short",
                day: "numeric",
                timeZone: "UTC"
              })}
            </span>
          </p>
        </A>
      </Show>

      <h2 class="mt-5 text-center text-xl font-bold">Overall Standings</h2>

      <div class="mb-4 border-b border-gray-200 dark:border-gray-700">
        <ul
          class="-mb-px flex flex-wrap justify-center text-center text-sm font-medium"
          id="myTab"
          data-tabs-toggle="#myTabContent"
          role="tablist"
        >
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 p-4"
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
              class="inline-block rounded-t-lg border-b-2 p-4"
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
              class="inline-block rounded-t-lg border-b-2 p-4"
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
          class="hidden rounded-lg p-2"
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
                          class="w-14 whitespace-nowrap py-4 pl-6 pr-2 font-normal"
                        >
                          {rank}
                        </th>
                        <td class="px-2 py-4">
                          <A
                            href={`/tournament/${params.slug}/team/${
                              teamsMap()[team_id]?.slug
                            }`}
                          >
                            <img
                              class="mr-3 inline-block h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                              src={
                                teamsMap()[team_id]?.image ??
                                teamsMap()[team_id]?.image_url
                              }
                              alt="Bordered avatar"
                            />
                            {teamsMap()[team_id]?.name}
                          </A>
                        </td>
                        <Show when={teamsInitialSeeding()}>
                          <td class="pl-2 pr-6">
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
          class="hidden rounded-lg p-2"
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
                          class="w-14 whitespace-nowrap py-4 pl-6 pr-2 font-normal"
                        >
                          {rank}
                        </th>
                        <td class="px-2 py-4">
                          <A
                            href={`/tournament/${params.slug}/team/${
                              teamsMap()[team_id]?.slug
                            }`}
                          >
                            <img
                              class="mr-3 inline-block h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                              src={
                                teamsMap()[team_id]?.image ??
                                teamsMap()[team_id]?.image_url
                              }
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
          class="hidden rounded-lg p-2"
          id={"sotg"}
          role="tabpanel"
          aria-labelledby={"tab-sotg"}
        >
          <Suspense fallback={<SpiritStandingsSkeleton />}>
            <Show
              when={
                tournamentQuery.data?.spirit_ranking.length > 0 &&
                tournamentQuery.data?.status === "COM"
              }
              fallback={
                <div
                  class="my-4 rounded-lg bg-blue-50 p-2 text-sm dark:bg-gray-800"
                  role="alert"
                >
                  <p class="text-center">
                    Spirit rankings is not available during the tournament.
                    <br />
                    Please check after the tournament is completed!
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
                            class="w-14 whitespace-nowrap py-4 pl-6 pr-2 font-normal"
                          >
                            {spirit.rank}
                          </th>
                          <td class="px-2 py-4">
                            <A
                              href={`/tournament/${params.slug}/team/${
                                teamsMap()[spirit.team_id]?.slug
                              }`}
                            >
                              <img
                                class="mr-3 inline-block h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                                src={
                                  teamsMap()[spirit.team_id]?.image ??
                                  teamsMap()[spirit.team_id]?.image_url
                                }
                                alt="Bordered avatar"
                              />
                              {teamsMap()[spirit.team_id]?.name}
                            </A>
                          </td>
                          <td class="py-4 pl-2 pr-6">
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
