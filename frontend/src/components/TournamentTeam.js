import { useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { initFlowbite } from "flowbite";
import { trophy } from "solid-heroicons/solid";
import {
  createEffect,
  createSignal,
  For,
  onMount,
  Show,
  Suspense
} from "solid-js";

import { matchCardColorToBorderColorMap } from "../colors";
import {
  fetchTeamBySlug,
  fetchTournamentBySlug,
  fetchTournamentTeamBySlug,
  fetchTournamentTeamMatches
} from "../queries";
import RosterSkeleton from "../skeletons/Roster";
import TournamentMatchesSkeleton from "../skeletons/TournamentMatch";
import { getTournamentBreadcrumbName } from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import TournamentMatch from "./TournamentMatch";

const TournamentTeam = () => {
  const params = useParams();
  const [tournamentDates, setTournamentDates] = createSignal([]);
  const [matchesGroupedByDate, setMatchesGroupedByDate] = createSignal({});
  const [doneFetching, setDoneFetching] = createSignal(false);

  const tournamentQuery = createQuery(
    () => ["tournament", params.tournament_slug],
    () => fetchTournamentBySlug(params.tournament_slug)
  );
  const teamQuery = createQuery(
    () => ["team", params.team_slug],
    () => fetchTeamBySlug(params.team_slug)
  );
  const rosterQuery = createQuery(
    () => ["tournament-roster", params.tournament_slug, params.team_slug],
    () => fetchTournamentTeamBySlug(params.tournament_slug, params.team_slug)
  );
  const matchesQuery = createQuery(
    () => ["team-matches", params.tournament_slug, params.team_slug],
    () => fetchTournamentTeamMatches(params.tournament_slug, params.team_slug)
  );

  const currTeamNo = match =>
    params.team_slug === match.team_1.ultimate_central_slug ? 1 : 2;

  const oppTeamNo = match =>
    params.team_slug === match.team_1.ultimate_central_slug ? 2 : 1;

  const matchOutcomeColor = match => {
    if (match.status === "SCH") {
      return "blue";
    }
    if (match.status === "COM") {
      const currTeamScore = match[`score_team_${currTeamNo(match)}`];
      const oppTeamScore = match[`score_team_${oppTeamNo(match)}`];

      if (currTeamScore > oppTeamScore) {
        return "green";
      } else if (currTeamScore == oppTeamScore) {
        return "gray";
      } else {
        return "red";
      }
    }
  };

  createEffect(() => {
    if (
      tournamentQuery.status === "success" &&
      !tournamentQuery.data?.message
    ) {
      let dates = [];
      const start = new Date(
        Date.parse(tournamentQuery.data?.event?.start_date)
      );
      const end = new Date(Date.parse(tournamentQuery.data?.event?.end_date));

      for (let d = start; d <= end; d.setDate(d.getDate() + 1)) {
        dates.push(new Date(d).getUTCDate());
      }

      setTournamentDates(dates);

      setTimeout(() => initFlowbite(), 500);
    }
  });

  createEffect(() => {
    setDoneFetching(false);
    if (matchesQuery.status === "success" && !matchesQuery.data?.message) {
      const teamMatches = matchesQuery.data;
      let groupedMatches = {};

      for (const match of teamMatches) {
        // Object.keys returns a list of strings, so converting date to a string
        const date = new Date(Date.parse(match?.time)).getUTCDate().toString();
        if (!Object.keys(groupedMatches).includes(date)) {
          groupedMatches[date] = [];
        }
        groupedMatches[date].push(match);
      }

      setMatchesGroupedByDate(groupedMatches);
      setDoneFetching(true);
    }
  });

  onMount(() => {
    setTimeout(() => initFlowbite(), 100);
    setTimeout(() => initFlowbite(), 500);
    setTimeout(() => initFlowbite(), 1000);
    setTimeout(() => initFlowbite(), 3000);
    setTimeout(() => initFlowbite(), 5000);
    setTimeout(() => initFlowbite(), 8000);
  });

  const isPlayer = registration => {
    return registration?.roles?.indexOf("player") > -1;
  };

  const isCaptain = registration => {
    return registration?.roles?.indexOf("captain") > -1;
  };

  const isSpiritCaptain = registration => {
    return registration?.roles?.indexOf("spirit captain") > -1;
  };

  const isCoach = registration => {
    return (
      registration?.roles?.indexOf("coach") > -1 ||
      registration?.roles?.indexOf("assistant coach") > -1
    );
  };

  return (
    <Show when={!teamQuery.data?.message}>
      <Breadcrumbs
        icon={trophy}
        pageList={[
          { url: "/tournaments", name: "All Tournaments" },
          {
            url: `/tournament/${params.tournament_slug}`,
            name: getTournamentBreadcrumbName(
              tournamentQuery.data?.event?.ultimate_central_slug || ""
            )
          }
        ]}
      />
      <div class="flex justify-center">
        <img
          class="mr-3 inline-block h-24 w-24 rounded-full p-1 ring-2 ring-blue-600 dark:ring-blue-500"
          src={teamQuery.data?.image_url}
          alt="Bordered avatar"
        />
      </div>
      <h1 class="my-5 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-2xl font-extrabold text-transparent">
          {teamQuery.data?.name}
        </span>
      </h1>
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
              id="tab-matches"
              data-tabs-target="#matches"
              type="button"
              role="tab"
              aria-controls="matches"
              aria-selected="false"
            >
              Matches
            </button>
          </li>
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 p-4"
              id="tab-roster"
              data-tabs-target="#roster"
              type="button"
              role="tab"
              aria-controls="roster"
              aria-selected="false"
            >
              Roster
            </button>
          </li>
        </ul>
      </div>
      <div id="myTabContent">
        <div
          class="hidden rounded-lg"
          id="matches"
          role="tabpanel"
          aria-labelledby="tab-matches"
        >
          <Show when={doneFetching()} fallback={<TournamentMatchesSkeleton />}>
            <For each={Object.entries(matchesGroupedByDate())}>
              {([tournamentDate, matches]) => (
                <div class="mb-10">
                  <Show when={tournamentDates().length > 1}>
                    <div class="mb-5 ml-1">
                      <h3 class="text-center text-lg font-bold">
                        {/* Object.groupBy coerces the keys to strings */}
                        Day -{" "}
                        {tournamentDates().indexOf(parseInt(tournamentDate)) +
                          1}
                      </h3>
                    </div>
                  </Show>
                  <For each={matches}>
                    {match => (
                      <div
                        class={clsx(
                          "mb-5 block w-full rounded-lg border bg-white px-1 py-2 shadow dark:bg-gray-800",
                          matchCardColorToBorderColorMap[
                            matchOutcomeColor(match)
                          ]
                        )}
                      >
                        <TournamentMatch
                          match={match}
                          currentTeamNo={currTeamNo(match)}
                          opponentTeamNo={oppTeamNo(match)}
                          tournamentSlug={params.tournament_slug}
                          imgRingColor={"gray"}
                          matchCardColorOverride={matchOutcomeColor(match)}
                          buttonColor={matchOutcomeColor(match)}
                        />
                      </div>
                    )}
                  </For>
                </div>
              )}
            </For>
          </Show>
        </div>

        <div
          class="hidden rounded-lg"
          id="roster"
          role="tabpanel"
          aria-labelledby="tab-roster"
        >
          <Suspense fallback={<RosterSkeleton />}>
            <Show when={rosterQuery.data?.filter(r => isPlayer(r)).length > 0}>
              <h2 class="text-center text-xl font-bold">Players</h2>
            </Show>

            <For each={rosterQuery.data?.filter(r => isPlayer(r))}>
              {registration => (
                <div class="mx-4 my-3 flex items-center space-x-4">
                  <div class="flex items-center space-x-4">
                    <img
                      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                      src={registration.person.image_url}
                      alt="Bordered avatar"
                    />
                    <div class="font-medium">
                      <div>
                        {registration.person.first_name +
                          " " +
                          registration.person.last_name}
                        <Show
                          when={registration.person?.player?.gender}
                        >{` (${registration.person?.player?.gender})`}</Show>
                      </div>
                    </div>
                    <Show when={isCaptain(registration)}>
                      <span class="me-2 h-fit rounded-full bg-blue-100 px-2.5 py-0.5 text-xs text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                        Captain
                      </span>
                    </Show>
                    <Show when={isSpiritCaptain(registration)}>
                      <span class="me-2 h-fit rounded-full bg-green-100 px-2.5 py-0.5 text-xs text-green-800 dark:bg-green-900 dark:text-green-300">
                        Spirit Captain
                      </span>
                    </Show>
                  </div>
                </div>
              )}
            </For>

            <Show when={rosterQuery.data?.filter(r => isCoach(r)).length > 0}>
              <h2 class="text-center text-xl font-bold">Coaches</h2>
            </Show>

            <For each={rosterQuery.data?.filter(r => isCoach(r))}>
              {registration => (
                <div class="mx-4 my-3 flex items-center space-x-4">
                  <div class="flex items-center space-x-4">
                    <img
                      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                      src={registration.person.image_url}
                      alt="Bordered avatar"
                    />
                    <div class="font-medium">
                      <div>
                        {registration.person.first_name +
                          " " +
                          registration.person.last_name}
                        <Show
                          when={registration.person?.player?.gender}
                        >{` (${registration.person?.player?.gender})`}</Show>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </For>
          </Suspense>
        </div>
      </div>
    </Show>
  );
};

export default TournamentTeam;
