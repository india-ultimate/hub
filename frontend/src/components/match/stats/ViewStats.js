import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { clsx } from "clsx";
import { trophy } from "solid-heroicons/solid";
import { createEffect, createSignal, Match, Show, Switch } from "solid-js";

import { matchCardColorToRingColorMap } from "../../../colors";
import { genderRatio } from "../../../constants";
import {
  fetchMatch,
  fetchMatchStats,
  fetchTournamentBySlug
} from "../../../queries";
import { getTournamentBreadcrumbName } from "../../../utils";
import Breadcrumbs from "../../Breadcrumbs";
import EventsDisplay from "./EventsDisplay";

const ViewStats = () => {
  const params = useParams();
  const [shouldRefetch, setShouldRefetch] = createSignal(false);

  const matchQuery = createQuery(
    () => ["match", params.matchId],
    () => fetchMatch(params.matchId)
  );

  const matchStatsQuery = createQuery(
    () => ["match-stats", params.matchId],
    () => fetchMatchStats(params.matchId),
    {
      refetchInterval: shouldRefetch ? 60000 : 2000000,
      staleTime: shouldRefetch ? 300000 : 5000000,
      refetchOnWindowFocus: true
    }
  );

  createEffect(() => {
    if (matchStatsQuery.isSuccess && matchStatsQuery.data) {
      if (matchStatsQuery.data.status !== "COM") {
        setShouldRefetch(true);
      }
    }
  });

  const tournamentQuery = createQuery(
    () => ["tournaments", params.tournamentSlug],
    () => fetchTournamentBySlug(params.tournamentSlug)
  );

  const getTeamImage = team => {
    return team?.image ?? team?.image_url;
  };

  return (
    <Show
      when={!matchQuery.data?.message}
      fallback={
        <div>
          Match could not be fetched. Error - {matchQuery.data?.message}
          <A href={"/tournaments"} class="text-blue-600 dark:text-blue-500">
            <br />
            Back to Tournaments Page
          </A>
        </div>
      }
    >
      <Breadcrumbs
        icon={trophy}
        pageList={[
          {
            url: `/tournament/${tournamentQuery.data?.event?.slug}`,
            name: getTournamentBreadcrumbName(
              tournamentQuery.data?.event?.slug || ""
            )
          },
          {
            url: `/tournament/${tournamentQuery.data?.event?.slug}/schedule`,
            name: "Schedule"
          },
          { name: matchQuery.data?.name }
        ]}
      />
      <div class="grid w-full grid-cols-12 gap-4">
        <Show
          when={matchStatsQuery.data?.status !== "COM"}
          fallback={
            <div class="col-span-12 flex justify-center">
              <div class="flex items-center justify-center rounded-xl bg-green-100 px-2 py-1">
                <span class="text-sm font-bold text-green-500">Completed</span>
              </div>
            </div>
          }
        >
          <div class="col-span-4 flex justify-center">
            <Show
              when={
                matchStatsQuery.data?.current_possession?.id ===
                matchQuery.data?.team_1?.id
              }
            >
              <div class="flex animate-bounce items-center justify-center rounded-xl bg-blue-100 px-2 py-1 text-sm font-bold text-blue-500">
                Offense
              </div>
            </Show>
          </div>
          <div class="col-span-4">
            <div class="flex items-center justify-center rounded-xl bg-red-100 py-1">
              <span class="relative flex h-2.5 w-2.5">
                <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500" />
              </span>
              <span class="ml-2 text-sm font-bold text-rose-500">Live</span>
            </div>
          </div>
          <div class="col-span-4 flex justify-center">
            <Show
              when={
                matchStatsQuery.data?.current_possession?.id ===
                matchQuery.data?.team_2?.id
              }
            >
              <div class="flex animate-bounce items-center justify-center rounded-xl bg-green-100 px-2 py-1 text-sm font-bold text-green-500">
                Offense
              </div>
            </Show>
          </div>
        </Show>

        <div class="col-span-4 flex justify-center">
          <img
            class={clsx(
              "mr-1 inline-block h-20 w-20 rounded-full p-1 ring-2",
              matchCardColorToRingColorMap["blue"]
            )}
            src={getTeamImage(matchQuery.data?.team_1)}
            alt="Bordered avatar"
          />
        </div>
        <div class="col-span-4 flex flex-wrap items-center justify-center">
          <div class="grid w-full grid-cols-2 gap-x-6 gap-y-1">
            <span class="text-center text-4xl font-bold text-blue-600">
              {matchStatsQuery.data?.score_team_1}
            </span>
            <span class="text-center text-4xl font-bold text-green-600">
              {" "}
              {matchStatsQuery.data?.score_team_2}
            </span>
          </div>
          <div class="whitespace-nowrap text-center text-sm italic">
            <Switch>
              <Match
                when={matchStatsQuery.data?.current_ratio === genderRatio.MALE}
              >
                4 Male / 3 Female
              </Match>
              <Match
                when={
                  matchStatsQuery.data?.current_ratio === genderRatio.FEMALE
                }
              >
                4 Female / 3 Male
              </Match>
            </Switch>
          </div>
        </div>
        <div class="col-span-4 flex justify-center">
          <img
            class={clsx(
              "mr-1 inline-block h-20 w-20 rounded-full p-1 ring-2",
              matchCardColorToRingColorMap["green"]
            )}
            src={getTeamImage(matchQuery.data?.team_2)}
            alt="Bordered avatar"
          />
        </div>
        <div class="col-span-5 flex justify-center">
          <span class="text-center font-bold text-blue-600 dark:text-gray-300">
            {`${matchQuery.data?.team_1?.name} (${matchQuery.data?.placeholder_seed_1})`}
          </span>
        </div>
        <div class="col-span-2 flex justify-center">vs</div>
        <div class="col-span-5 flex justify-center">
          <span class="text-center font-bold text-green-600 dark:text-gray-300">
            {`${matchQuery.data?.team_2?.name} (${matchQuery.data?.placeholder_seed_2})`}
          </span>
        </div>
      </div>

      <div class="my-2 rounded-lg bg-gray-50 p-4 text-sm " role="alert">
        <details>
          <summary class="text-gray-600">Match Info</summary>
          <div class="mt-4 space-y-2">
            <div>
              <span class="font-bold">Status:</span>{" "}
              {matchStatsQuery.data?.status === "FH"
                ? "First Half"
                : matchStatsQuery.data?.status === "SH"
                ? "Second Half"
                : "Completed"}
            </div>
            <div>
              <span class="font-bold">Team which started on Offense:</span>{" "}
              {matchStatsQuery.data?.initial_possession?.name}
            </div>
            <Show when={tournamentQuery.data?.event.type === "MXD"}>
              <div>
                <span class="font-bold">Starting Gender Ratio:</span>{" "}
                <Switch fallback={"NA"}>
                  <Match
                    when={
                      matchStatsQuery.data?.initial_ratio === genderRatio.MALE
                    }
                  >
                    4 Male / 3 Female
                  </Match>
                  <Match
                    when={
                      matchStatsQuery.data?.initial_ratio === genderRatio.FEMALE
                    }
                  >
                    4 Female / 3 Male
                  </Match>
                </Switch>
              </div>
            </Show>
          </div>
        </details>
      </div>

      <div class="inline-flex w-full items-center justify-center">
        <hr class="my-8 h-px w-64 border-0 bg-gray-200 dark:bg-gray-700" />
        <span class="absolute left-1/2 -translate-x-1/2 bg-white px-3 font-sans text-sm uppercase tracking-widest text-gray-500 dark:bg-gray-900 dark:text-white">
          Latest Events
        </span>
      </div>

      <EventsDisplay match={matchQuery.data} stats={matchStatsQuery.data} />
    </Show>
  );
};

export default ViewStats;
