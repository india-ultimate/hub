import { createMutation, createQuery } from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import {
  createMatchStatsEvent,
  fetchTournamentTeamBySlug
} from "../../../queries";
import Error from "../../alerts/Error";
import Info from "../../alerts/Info";

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
            <div class="my-2 flex flex-wrap justify-between text-base font-bold">
              <span>{`${player?.full_name} (${player?.gender || ""}) | # ${
                player?.commentary_info?.jersey_number || ""
              }`}</span>
              <button
                class="rounded-lg bg-red-600 px-2 text-white"
                onClick={() => removeFromSelected(player)}
              >
                Remove
              </button>
              <hr class="m-1 w-full" />
            </div>
          )}
        </For>
      </Show>
      <button
        type="submit"
        disabled={selectedPlayers().length !== 7}
        onClick={handleSubmit}
        class="mb-2 w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 disabled:bg-gray-500"
      >
        Submit
      </button>
      <Show when={error()}>
        <Error text={`Oops ! ${error()}`} />
      </Show>
      <Show when={status()}>
        <Info text={status()} />
      </Show>
      <h2 class="mb-2 mt-4 text-lg font-bold text-blue-500">All Players</h2>
      <For each={rosterQuery.data || []}>
        {reg => (
          <Show
            when={
              selectedPlayers().filter(p => p.id === reg.player?.id).length ===
              0
            }
          >
            <div class="my-2 flex flex-wrap justify-between text-base font-bold">
              <span>{`${reg.player?.full_name} (${
                reg.player?.gender || ""
              }) | # ${
                reg.player?.commentary_info?.jersey_number || ""
              }`}</span>
              <button
                class="rounded-lg bg-blue-600 px-2 text-white"
                onClick={() => addToSelected(reg.player)}
              >
                Add
              </button>
              <hr class="m-1 w-full" />
            </div>
          </Show>
        )}
      </For>
    </>
  );
};

export default SelectLineForm;
