import { A, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { clsx } from "clsx";
import { Show } from "solid-js";

import {
  matchCardColorToButtonStyles,
  matchCardColorToRingColorMap
} from "../../../colors";
import {
  fetchMatch,
  fetchTournamentBySlug,
  matchStatsFullTime,
  matchStatsHalfTime,
  matchStatsUndo
} from "../../../queries";
import ButtonWithModal from "../../modal/ButtonWithModal";
import BlockForm from "./BlockForm";
import EventsDisplay from "./EventsDisplay";
import ScoreForm from "./ScoreForm";

const EditStats = () => {
  const queryClient = useQueryClient();
  const params = useParams();

  const matchQuery = createQuery(
    () => ["match", params.matchId],
    () => fetchMatch(params.matchId)
  );

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
          when={matchQuery.data?.stats?.status !== "COM"}
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
                matchQuery.data?.stats?.current_possession?.id ===
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
                matchQuery.data?.stats?.current_possession?.id ===
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
              {matchQuery.data?.stats?.score_team_1}
            </span>
            <span class="text-4xl font-bold text-green-600">
              {" "}
              {matchQuery.data?.stats?.score_team_2}
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

      <div class="my-2 mt-6 rounded-lg bg-gray-50 p-4 text-sm" role="alert">
        <details>
          <summary class="text-gray-600">Match Info</summary>
          <div class="mt-4 space-y-2">
            <div>
              <span class="font-bold">Status:</span>{" "}
              {matchQuery.data?.stats?.status === "FH"
                ? "First Half"
                : matchQuery.data?.stats?.status === "SH"
                ? "Second Half"
                : "Completed"}
            </div>
            <div>
              <span class="font-bold">
                Team which started the game on Offense:
              </span>{" "}
              {matchQuery.data?.stats?.initial_possession?.name}
            </div>
          </div>
          <button
            class="mt-2 rounded-lg bg-blue-500 px-2 py-1 text-white"
            onClick={() =>
              matchStatsHalfTimeMutation.mutate({
                match_id: params.matchId
              })
            }
          >
            Half Time
          </button>
          <button
            class="mx-2 rounded-lg bg-blue-500 px-2 py-1 text-white"
            onClick={() =>
              matchStatsFullTimeMutation.mutate({
                match_id: params.matchId
              })
            }
          >
            Full Time
          </button>
        </details>
      </div>

      <div class="my-2 flex flex-row items-center justify-between gap-x-4 rounded-lg bg-blue-50 px-6 py-2 text-sm">
        <div class="text-md font-semibold text-blue-600">
          {matchQuery.data?.team_1?.name}
        </div>
        <div class="mt-2">
          <Show
            when={
              matchQuery.data?.stats?.current_possession?.id ===
              matchQuery.data?.team_1?.id
            }
            fallback={
              <div class="flex justify-center">
                <ButtonWithModal
                  button={{ text: "Block" }}
                  buttonColor={matchCardColorToButtonStyles["blue"]}
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
              <ButtonWithModal
                button={{ text: "Score" }}
                buttonColor={matchCardColorToButtonStyles["blue"]}
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

      <div class="my-2 flex flex-row items-center justify-between gap-x-4 rounded-lg bg-green-50 px-4 py-2 text-sm">
        <div class="text-md font-semibold text-green-600">
          {matchQuery.data?.team_2?.name}
        </div>
        <div class="mt-2">
          <Show
            when={
              matchQuery.data?.stats?.current_possession?.id ===
              matchQuery.data?.team_2?.id
            }
            fallback={
              <div class="flex justify-center">
                <ButtonWithModal
                  button={{ text: "Block" }}
                  buttonColor={matchCardColorToButtonStyles["green"]}
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
              <ButtonWithModal
                button={{ text: "Score" }}
                buttonColor={matchCardColorToButtonStyles["green"]}
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

      <button
        type="button"
        class="my-2 rounded-lg bg-yellow-400 px-5 py-2.5 text-sm font-medium text-white hover:bg-yellow-500 focus:outline-none focus:ring-4 focus:ring-yellow-300 disabled:bg-gray-300"
        onClick={() =>
          matchStatsUndoMutation.mutate({ match_id: matchQuery.data?.id })
        }
        disabled={matchStatsUndoMutation.isLoading}
      >
        Undo last event
      </button>

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
