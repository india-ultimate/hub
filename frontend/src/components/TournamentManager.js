import { useStore } from "../store";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import {
  createTournament,
  deleteTournament,
  fetchEvents,
  fetchTeams,
  fetchTournaments,
  updateSeeding
} from "../queries";
import { createEffect, createSignal, For, Show } from "solid-js";

const TournamentManager = () => {
  const queryClient = useQueryClient();
  const [store] = useStore();
  const [event, setEvent] = createSignal(0);
  const [selectedTeams, setSelectedTeams] = createSignal([]);
  const [selectedTournament, setSelectedTournament] = createSignal();
  const [tournamentSeeding, setTournamentSeeding] = createSignal([]);
  const [teamsMap, setTeamsMap] = createSignal({});

  createEffect(() => {
    if (tournamentsQuery.status === "success") {
      const tournament = tournamentsQuery.data?.filter(
        t => t.id === selectedTournament()
      )[0];
      const seeding = tournament?.initial_seeding;

      if (seeding) setTournamentSeeding(seeding);
    }
  });

  createEffect(() => {
    if (teamsQuery.status === "success") {
      let newTeamsMap = {};
      teamsQuery.data.map(team => {
        newTeamsMap[team.id] = team.name;
      });
      setTeamsMap(newTeamsMap);
    }
  });

  const eventsQuery = createQuery(() => ["events"], fetchEvents);
  const teamsQuery = createQuery(() => ["teams"], fetchTeams);
  const tournamentsQuery = createQuery(() => ["tournaments"], fetchTournaments);

  const createTournamentMutation = createMutation({
    mutationFn: createTournament,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournaments"] })
  });

  const updateSeedingMutation = createMutation({
    mutationFn: updateSeeding,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournaments"] })
  });

  const deleteTournamentMutation = createMutation({
    mutationFn: deleteTournament,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournaments"] })
  });

  return (
    <Show when={store?.data?.is_staff} fallback={<p>Not Authorised!</p>}>
      <div>
        <h1>New Tournament</h1>
        <label
          for="events"
          class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
        >
          Select an Event
        </label>
        <select
          id="events"
          onChange={e => setEvent(parseInt(e.target.value))}
          class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
        >
          <option value={0} selected>
            Choose an event
          </option>
          <For each={eventsQuery.data}>
            {e => <option value={e.id}>{e.title}</option>}
          </For>
        </select>
        <div class="grid grid-cols-4 gap-4">
          <For each={teamsQuery.data}>
            {t => (
              <div class="flex items-center pl-4 border border-gray-200 rounded dark:border-gray-700">
                <input
                  id={"team-" + t.id}
                  type="checkbox"
                  value={t.id}
                  onChange={e =>
                    e.target.checked
                      ? setSelectedTeams([
                          ...selectedTeams().filter(
                            t => t !== parseInt(e.target.value)
                          ),
                          parseInt(e.target.value)
                        ])
                      : setSelectedTeams(
                          selectedTeams().filter(
                            t => t !== parseInt(e.target.value)
                          )
                        )
                  }
                  class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
                />
                <label
                  for={"team-" + t.id}
                  class="w-full py-4 ml-2 text-sm font-medium text-gray-900 dark:text-gray-300"
                >
                  {t.name}
                </label>
              </div>
            )}
          </For>
        </div>
        <button
          type="button"
          onClick={() =>
            createTournamentMutation.mutate({
              event_id: event(),
              team_ids: selectedTeams()
            })
          }
          class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700"
        >
          Create Tournament
        </button>
      </div>
      <div>
        <h1>Existing Tournaments</h1>
        <select
          id="tournaments"
          onChange={e => setSelectedTournament(parseInt(e.target.value))}
          class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
        >
          <option value={0} selected>
            Choose a tournament
          </option>
          <For each={tournamentsQuery.data}>
            {t => <option value={t.id}>{t.event.title}</option>}
          </For>
        </select>

        <div class="relative overflow-x-auto">
          <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
            <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
              <tr>
                <th scope="col" class="px-6 py-3">
                  Seeding
                </th>
                <th scope="col" class="px-6 py-3">
                  Team Name
                </th>
                <th scope="col" class="px-6 py-3">
                  Team ID
                </th>
              </tr>
            </thead>
            <tbody>
              <For each={Object.keys(tournamentSeeding())}>
                {seed => (
                  <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                    <th
                      scope="row"
                      class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                    >
                      {seed}
                    </th>
                    <td class="px-6 py-4">
                      {teamsMap()[tournamentSeeding()[seed]]}
                    </td>
                    <td class="px-6 py-4">{tournamentSeeding()[seed]}</td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>

          <label
            for="message"
            class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
          >
            Raw Seeding JSON
          </label>
          <textarea
            id="message"
            rows="4"
            class="block p-2.5 w-full text-sm text-gray-900 bg-gray-50 rounded-lg border border-gray-300 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            placeholder="Seeding JSON Here..."
            onChange={e => setTournamentSeeding(JSON.parse(e.target.value))}
          >
            {JSON.stringify(tournamentSeeding())}
          </textarea>
          <button
            type="button"
            onClick={() =>
              updateSeedingMutation.mutate({
                id: selectedTournament(),
                body: { seeding: tournamentSeeding() }
              })
            }
            class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700"
          >
            Update Seeding
          </button>
          <button
            type="button"
            onClick={() =>
              deleteTournamentMutation.mutate({
                id: selectedTournament()
              })
            }
            class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700"
          >
            Delete Tournament
          </button>
        </div>
      </div>
    </Show>
  );
};

export default TournamentManager;
