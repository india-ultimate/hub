import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import {
  addTournamentDirector,
  fetchTournamentDirectors,
  removeTournamentDirector,
  searchUsers
} from "../../queries";

const TournamentDirectors = props => {
  const queryClient = useQueryClient();
  const [searchText, setSearchText] = createSignal("");
  const [selectedUserId, setSelectedUserId] = createSignal("");
  const [error, setError] = createSignal("");

  const directorsQuery = createQuery({
    queryKey: () => ["tournament-directors", props.tournamentId],
    queryFn: () => fetchTournamentDirectors(props.tournamentId),
    get enabled() {
      return Boolean(props.tournamentId);
    }
  });

  const usersQuery = createQuery({
    queryKey: () => ["users", "search", searchText()],
    queryFn: () => searchUsers(searchText()),
    get enabled() {
      return searchText().trim().length > 0;
    }
  });

  const addMutation = createMutation({
    mutationFn: addTournamentDirector,
    onSuccess: () => {
      setError("");
      setSelectedUserId("");
      setSearchText("");
      queryClient.invalidateQueries({
        queryKey: ["tournament-directors", props.tournamentId]
      });
    },
    onError: e => setError(e.message)
  });

  const removeMutation = createMutation({
    mutationFn: removeTournamentDirector,
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({
        queryKey: ["tournament-directors", props.tournamentId]
      });
    },
    onError: e => setError(e.message)
  });

  return (
    <div class="my-6 rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <h2 class="mb-3 text-xl font-bold text-blue-500">Tournament directors</h2>
      <p class="mb-3 text-sm text-gray-600 dark:text-gray-400">
        Directors can manage this tournament and use the AI agent. They cannot
        create or delete tournaments, or appoint other directors.
      </p>
      <Show when={directorsQuery.data?.length}>
        <ul class="mb-4 space-y-2">
          <For each={directorsQuery.data}>
            {user => (
              <li class="flex items-center justify-between text-sm">
                <span>
                  {user.full_name || user.username}{" "}
                  <span class="text-gray-500">({user.username})</span>
                </span>
                <button
                  type="button"
                  class="rounded-lg bg-red-700 px-3 py-1 text-xs font-medium text-white hover:bg-red-800"
                  disabled={removeMutation.isLoading}
                  onClick={() =>
                    removeMutation.mutate({
                      tournamentId: props.tournamentId,
                      userId: user.id
                    })
                  }
                >
                  Remove
                </button>
              </li>
            )}
          </For>
        </ul>
      </Show>
      <div class="grid gap-3 md:grid-cols-2">
        <input
          type="text"
          value={searchText()}
          onInput={e => setSearchText(e.target.value)}
          placeholder="Search by name or username"
          class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
        />
        <select
          value={selectedUserId()}
          onChange={e => setSelectedUserId(e.target.value)}
          class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
        >
          <option value="">Select a user</option>
          <For each={usersQuery.data || []}>
            {user => (
              <option value={user.id}>
                {user.full_name || user.username} ({user.username})
              </option>
            )}
          </For>
        </select>
      </div>
      <button
        type="button"
        class="mt-3 rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-800 disabled:bg-gray-400"
        disabled={!selectedUserId() || addMutation.isLoading}
        onClick={() =>
          addMutation.mutate({
            tournamentId: props.tournamentId,
            userId: parseInt(selectedUserId(), 10)
          })
        }
      >
        Add director
      </button>
      <Show when={error()}>
        <p class="mt-2 text-sm text-red-600">{error()}</p>
      </Show>
    </div>
  );
};

export default TournamentDirectors;
