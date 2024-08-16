import { createMutation, createQuery } from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import {
  createMatchStatsEvent,
  fetchTournamentTeamBySlug
} from "../../../queries";
import Error from "../../alerts/Error";

const SelectLineForm = props => {
  const [selectedPlayers, setSelectedPlayers] = createSignal([]);
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const rosterQuery = createQuery(
    () => ["tournament-roster", props.tournament?.slug, props.team?.slug],
    () =>
      fetchTournamentTeamBySlug(
        props.tournament?.event?.slug,
        props.team?.slug,
        props.tournament?.use_uc_registrations
      ),
    {
      get enabled() {
        return props.tournament?.use_uc_registrations !== undefined;
      }
    }
  );

  const addToSelected = player => {
    setSelectedPlayers([
      ...selectedPlayers().filter(p => p.id !== player.id),
      player
    ]);
  };

  const removeFromSelected = player => {
    setSelectedPlayers(selectedPlayers().filter(p => p.id !== player.id));
  };

  const createMatchStatsEventMutation = createMutation({
    mutationFn: createMatchStatsEvent,
    onSuccess: () => {
      setStatus("Saved! You can now close this.");
    },
    onError: e => {
      console.log(e);
      setError(e);
    }
  });

  const handleSubmit = async () => {
    setStatus("");
    setError("");

    createMatchStatsEventMutation.mutate({
      match_id: props.match?.id,
      body: {
        type: "LS",
        team_id: props.team?.id,
        player_ids: selectedPlayers().map(p => p.id)
      }
    });
  };

  return (
    <>
      <h2 class="mb-2 text-lg font-bold text-blue-500">Selected Players</h2>
      <Show
        when={selectedPlayers().length > 0}
        fallback={<Error text="No Players Selected" />}
      >
        <For each={selectedPlayers()}>
          {player => (
            <div class="flex justify-between">
              <span>{player?.full_name}</span>
              <button onClick={() => removeFromSelected(player)}>Remove</button>
            </div>
          )}
        </For>
      </Show>
      <button
        type="submit"
        disabled={selectedPlayers().length !== 7}
        onClick={handleSubmit}
        class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 disabled:bg-gray-500"
      >
        Submit
      </button>
      <Show when={error()}>
        <p class="my-2 text-sm text-red-600 dark:text-red-500">
          <span class="font-medium">Oops!</span> {error()}
        </p>
      </Show>
      <p>{status()}</p>
      <h2 class="mb-2 text-lg font-bold text-blue-500">All Players</h2>
      <For each={rosterQuery.data || []}>
        {reg => (
          <Show
            when={
              selectedPlayers().filter(p => p.id === reg.player?.id).length ===
              0
            }
          >
            <div class="flex justify-between">
              <span>{reg.player?.full_name}</span>
              <button onClick={() => addToSelected(reg.player)}>Add</button>
            </div>
          </Show>
        )}
      </For>
    </>
  );
};

export default SelectLineForm;
