import { useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import { star, trophy } from "solid-heroicons/solid";
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
  fetchTournamentTeamMatches,
  fetchTournamentTeamPointsBySlugV2
} from "../queries";
import RosterSkeleton from "../skeletons/Roster";
import { TournamentTeamMatches as TournamentTeamMatchesSkeleton } from "../skeletons/TournamentMatch";
import { getTournamentBreadcrumbName } from "../utils";
import Info from "./alerts/Info";
import Breadcrumbs from "./Breadcrumbs";
import MatchCard from "./match/MatchCard";
import Registration from "./roster/Registration";
import UCRegistration from "./roster/UCRegistration";

const TournamentTeam = () => {
  const params = useParams();
  const [tournamentDates, setTournamentDates] = createSignal([]);
  const [matchesGroupedByDate, setMatchesGroupedByDate] = createSignal({});
  const [doneFetching, setDoneFetching] = createSignal(false);

  const tournamentQuery = createQuery(
    () => ["tournaments", params.tournament_slug],
    () => fetchTournamentBySlug(params.tournament_slug)
  );
  const teamQuery = createQuery(
    () => ["teams", params.team_slug],
    () => fetchTeamBySlug(params.team_slug)
  );
  const rosterQuery = createQuery(
    () => ["tournament-roster", params.tournament_slug, params.team_slug],
    () =>
      fetchTournamentTeamBySlug(
        params.tournament_slug,
        params.team_slug,
        tournamentQuery.data.use_uc_registrations
      ),
    {
      get enabled() {
        return tournamentQuery.data?.use_uc_registrations !== undefined;
      }
    }
  );
  const rosterPointsQuery = createQuery(
    () => [
      "tournament-roster-points",
      params.tournament_slug,
      params.team_slug
    ],
    () =>
      fetchTournamentTeamPointsBySlugV2(
        params.tournament_slug,
        params.team_slug
      ),
    {
      get enabled() {
        return tournamentQuery.data?.use_uc_registrations === false;
      }
    }
  );
  const matchesQuery = createQuery(
    () => ["team-matches", params.tournament_slug, params.team_slug],
    () => fetchTournamentTeamMatches(params.tournament_slug, params.team_slug)
  );

  const currTeamNo = match => {
    if (match.team_1) {
      return params.team_slug === match.team_1.slug ? 1 : 2;
    }
    return params.team_slug === match.team_2.slug ? 2 : 1;
  };

  const oppTeamNo = match => (currTeamNo(match) === 1 ? 2 : 1);

  const matchOutcomeColor = match => {
    if (match.status === "SCH" || match.status === "YTF") {
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

  const players = () => {
    if (tournamentQuery.data?.use_uc_registrations) {
      return rosterQuery.data?.filter(r => r?.roles?.includes("player"));
    } else {
      return rosterQuery.data?.filter(r => r?.is_playing);
    }
  };

  const nonPlayers = () => {
    if (tournamentQuery.data?.use_uc_registrations) {
      return rosterQuery.data?.filter(
        r =>
          r?.roles?.includes("coach") || r?.roles?.includes("assistant coach")
      );
    } else {
      return rosterQuery.data?.filter(r => !r?.is_playing);
    }
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
              tournamentQuery.data?.event?.slug || ""
            )
          }
        ]}
      />
      <div class="flex justify-center">
        <img
          class="mr-3 inline-block h-24 w-24 rounded-full p-1 ring-2 ring-blue-600 dark:ring-blue-500"
          src={teamQuery.data?.image ?? teamQuery.data?.image_url}
          alt="Bordered avatar"
        />
      </div>
      <h1 class="mt-2 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-2xl font-extrabold text-transparent">
          <Suspense
            fallback={
              <span class="inline-block h-2 w-60 animate-pulse rounded-full bg-gray-200 dark:bg-gray-700" />
            }
          >
            {teamQuery.data?.name}
          </Suspense>
        </span>
      </h1>
      <div class="my-2 flex w-full justify-center">
        <p class="mr-2 inline-flex items-center rounded bg-blue-100 p-1.5 text-sm font-semibold text-blue-600 dark:bg-blue-200 dark:text-blue-800">
          <Icon path={star} class="mr-1 h-4" />
          {rosterPointsQuery.data?.points || 0}
        </p>
      </div>

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
          <Show
            when={doneFetching()}
            fallback={<TournamentTeamMatchesSkeleton />}
          >
            <For each={Object.entries(matchesGroupedByDate())}>
              {([tournamentDate, matches]) => (
                <div class="mb-10">
                  <Show when={tournamentDates().length > 1}>
                    <div class="mb-5 ml-1">
                      <h3 class="text-center text-lg font-bold">
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
                        <MatchCard
                          match={match}
                          currentTeamNo={currTeamNo(match)}
                          opponentTeamNo={oppTeamNo(match)}
                          tournamentSlug={params.tournament_slug}
                          useUCRegistrations={
                            tournamentQuery.data?.use_uc_registrations
                          }
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
            <h2 class="my-4 text-xl font-bold underline underline-offset-2">
              Players {`(${players()?.length || "-"})`}
            </h2>
            <Show
              when={players()?.length !== 0}
              fallback={<Info text="No Players in the roster" />}
            >
              <div class="w-full divide-y sm:divide-y-0">
                <For each={players()}>
                  {registration => (
                    <Show
                      when={tournamentQuery.data?.use_uc_registrations}
                      fallback={<Registration registration={registration} />}
                    >
                      <UCRegistration registration={registration} />
                    </Show>
                  )}
                </For>
              </div>
            </Show>
            <h2 class="mb-4 mt-8 text-xl font-bold underline underline-offset-2">
              {tournamentQuery.data?.use_uc_registrations
                ? "Coaches"
                : "Non-players"}{" "}
              {`(${nonPlayers()?.length || "-"})`}
            </h2>
            <Show
              when={nonPlayers()?.length !== 0}
              fallback={
                <Info
                  text={`No ${
                    tournamentQuery.data?.use_uc_registrations
                      ? "Coaches"
                      : "Non-players"
                  } in roster`}
                />
              }
            >
              <div class="w-full divide-y sm:divide-y-0">
                <For each={nonPlayers()}>
                  {registration => (
                    <Show
                      when={tournamentQuery.data?.use_uc_registrations}
                      fallback={<Registration registration={registration} />}
                    >
                      <UCRegistration registration={registration} />
                    </Show>
                  )}
                </For>
              </div>
            </Show>
          </Suspense>
        </div>
      </div>
    </Show>
  );
};

export default TournamentTeam;
