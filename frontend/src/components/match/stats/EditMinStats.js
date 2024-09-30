import { A, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { clsx } from "clsx";
import { createEffect, createSignal, Show } from "solid-js";

import {
  matchCardColorToButtonStyles,
  matchCardColorToRingColorMap
} from "../../../colors";
import {
  fetchMatch,
  fetchMatchStats,
  fetchTournamentBySlug,
  matchStatsFullTime,
  matchStatsHalfTime,
  matchStatsSwitchOffense,
  matchStatsUndo
} from "../../../queries";
import ButtonWithModal from "../../modal/ButtonWithModal";
import BlockForm from "./BlockForm";
import EventsDisplay from "./EventsDisplay";
import ScoreForm from "./ScoreForm";

const EditStats = () => {
  const queryClient = useQueryClient();
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

  const matchStatsHalfTimeMutation = createMutation({
    mutationFn: matchStatsHalfTime,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["match", params.matchId] });
    }
  });

  const matchStatsFullTimeMutation = createMutation({
    mutationFn: matchStatsFullTime,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["match", params.matchId] });
    }
  });

  const matchStatsUndoMutation = createMutation({
    mutationFn: matchStatsUndo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["match", params.matchId] });
    }
  });

  const matchStatsSwitchOffenseMutation = createMutation({
    mutationFn: matchStatsSwitchOffense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["match", params.matchId] });
    }
  });

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
              <span class="text-sm font-bold text-rose-500">
                {matchStatsQuery.data?.status === "FH"
                  ? "First Half"
                  : matchStatsQuery.data?.status === "SH"
                  ? "Second Half"
                  : "Completed"}
              </span>
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
        <div class="col-span-4 flex items-center justify-center">
          <div class="grid grid-cols-2 gap-x-6 gap-y-1">
            <span class="text-4xl font-bold text-blue-600">
              {matchStatsQuery.data?.score_team_1}
            </span>
            <span class="text-4xl font-bold text-green-600">
              {" "}
              {matchStatsQuery.data?.score_team_2}
            </span>
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

      <div class="mb-2 mt-6 flex flex-col flex-wrap space-y-2 rounded-lg bg-gray-100 px-4 py-3 text-sm">
        <div class="italic">
          <span class="font-bold">
            {matchStatsQuery.data?.initial_possession?.name}
          </span>{" "}
          <span>started on offense.</span>
        </div>
      </div>

      <div class="mb-2 mt-2 flex flex-row items-center justify-between gap-x-4 rounded-lg bg-blue-100 px-4 py-2 text-sm">
        <div class="text-md font-semibold text-blue-600">
          {matchQuery.data?.team_1?.name}
        </div>
        <div class="mt-2">
          <Show
            when={
              matchStatsQuery.data?.current_possession?.id ===
              matchQuery.data?.team_1?.id
            }
            fallback={
              <div class="flex justify-center">
                <ButtonWithModal
                  button={{ text: "Block" }}
                  buttonColor={matchCardColorToButtonStyles["blue"]}
                  disabled={matchStatsSwitchOffenseMutation.isLoading}
                  onClose={() => {
                    queryClient.invalidateQueries({
                      queryKey: ["match", params.matchId]
                    });
                  }}
                >
                  <BlockForm
                    match={matchQuery.data}
                    tournament={tournamentQuery.data}
                    team={matchQuery.data?.team_1}
                  />
                </ButtonWithModal>
              </div>
            }
          >
            <div class="flex justify-center">
              <button
                type="button"
                class={clsx(
                  "group relative mb-2 mr-2 inline-flex items-center justify-center overflow-hidden rounded-lg p-0.5 font-medium",
                  "bg-blue-600 text-xs text-gray-900 focus:outline-none focus:ring-4 disabled:bg-gray-400 dark:text-white"
                )}
                disabled={matchStatsSwitchOffenseMutation.isLoading}
                onClick={() =>
                  matchStatsSwitchOffenseMutation.mutate({
                    match_id: matchQuery.data?.id
                  })
                }
              >
                <span
                  class={clsx(
                    "relative inline-flex items-center rounded-md px-3 py-2.5 transition-all duration-75 ease-in ",
                    "bg-white group-hover:bg-opacity-0 group-disabled:bg-gray-300 dark:bg-gray-800"
                  )}
                >
                  Throwaway
                </span>
              </button>
              <ButtonWithModal
                button={{ text: "Score" }}
                buttonColor={matchCardColorToButtonStyles["blue"]}
                disabled={matchStatsSwitchOffenseMutation.isLoading}
                onClose={() => {
                  queryClient.invalidateQueries({
                    queryKey: ["match", params.matchId]
                  });
                }}
              >
                <ScoreForm
                  match={matchQuery.data}
                  tournament={tournamentQuery.data}
                  team={matchQuery.data?.team_1}
                />
              </ButtonWithModal>
            </div>
          </Show>
        </div>
      </div>

      <div class="my-2 flex flex-row items-center justify-between gap-x-4 rounded-lg bg-green-100 px-4 py-2 text-sm">
        <div class="text-md font-semibold text-green-600">
          {matchQuery.data?.team_2?.name}
        </div>
        <div class="mt-2">
          <Show
            when={
              matchStatsQuery.data?.current_possession?.id ===
              matchQuery.data?.team_2?.id
            }
            fallback={
              <div class="flex justify-center">
                <ButtonWithModal
                  button={{ text: "Block" }}
                  buttonColor={matchCardColorToButtonStyles["green"]}
                  disabled={matchStatsSwitchOffenseMutation.isLoading}
                  onClose={() => {
                    queryClient.invalidateQueries({
                      queryKey: ["match", params.matchId]
                    });
                  }}
                >
                  <BlockForm
                    match={matchQuery.data}
                    tournament={tournamentQuery.data}
                    team={matchQuery.data?.team_2}
                  />
                </ButtonWithModal>
              </div>
            }
          >
            <div class="flex justify-center">
              <button
                type="button"
                class={clsx(
                  "group relative mb-2 mr-2 inline-flex items-center justify-center overflow-hidden rounded-lg p-0.5 font-medium",
                  "bg-green-600 text-xs text-gray-900 focus:outline-none focus:ring-4 disabled:bg-gray-400 dark:text-white"
                )}
                disabled={matchStatsSwitchOffenseMutation.isLoading}
                onClick={() =>
                  matchStatsSwitchOffenseMutation.mutate({
                    match_id: matchQuery.data?.id
                  })
                }
              >
                <span
                  class={clsx(
                    "relative inline-flex items-center rounded-md px-3 py-2.5 transition-all duration-75 ease-in",
                    "bg-white group-hover:bg-opacity-0 group-disabled:bg-gray-300 dark:bg-gray-800"
                  )}
                >
                  Throwaway
                </span>
              </button>
              <ButtonWithModal
                button={{ text: "Score" }}
                buttonColor={matchCardColorToButtonStyles["green"]}
                disabled={matchStatsSwitchOffenseMutation.isLoading}
                onClose={() => {
                  queryClient.invalidateQueries({
                    queryKey: ["match", params.matchId]
                  });
                }}
              >
                <ScoreForm
                  match={matchQuery.data}
                  tournament={tournamentQuery.data}
                  team={matchQuery.data?.team_2}
                />
              </ButtonWithModal>
            </div>
          </Show>
        </div>
      </div>

      <div class="my-6 flex w-full flex-wrap justify-end gap-2">
        <button
          class="rounded-lg bg-blue-500 px-4 py-3 text-sm text-white disabled:bg-gray-300"
          onClick={() =>
            matchStatsHalfTimeMutation.mutate({
              match_id: params.matchId
            })
          }
          disabled={matchStatsHalfTimeMutation.isLoading}
        >
          Half Time
        </button>
        <button
          class="rounded-lg bg-blue-500 px-4 py-3 text-sm text-white disabled:bg-gray-300"
          onClick={() =>
            matchStatsFullTimeMutation.mutate({
              match_id: params.matchId
            })
          }
          disabled={matchStatsFullTimeMutation.isLoading}
        >
          Full Time
        </button>
        <button
          type="button"
          class="rounded-lg bg-yellow-300 px-4 py-3 text-sm font-medium text-gray-800 focus:outline-none focus:ring-4 focus:ring-yellow-300 disabled:bg-gray-300"
          onClick={() =>
            matchStatsUndoMutation.mutate({ match_id: matchQuery.data?.id })
          }
          disabled={matchStatsUndoMutation.isLoading}
        >
          Undo last event
        </button>
      </div>

      <div class="inline-flex w-full items-center justify-center">
        <hr class="my-8 h-px w-64 border-0 bg-gray-200 dark:bg-gray-700" />
        <span class="absolute left-1/2 -translate-x-1/2 bg-white px-3 font-sans text-sm uppercase tracking-widest text-gray-500 dark:bg-gray-900 dark:text-white">
          Latest Events
        </span>
      </div>

      <EventsDisplay match={matchQuery.data} />
    </Show>
  );
};

export default EditStats;
