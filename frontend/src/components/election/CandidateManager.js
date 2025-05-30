import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import { createCandidate, fetchCandidates, searchUsers } from "../../queries";
import Error from "../alerts/Error";
import Info from "../alerts/Info";

const CandidateManager = props => {
  const queryClient = useQueryClient();
  const [selectedUserId, setSelectedUserId] = createSignal("");
  const [bio, setBio] = createSignal("");
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");
  const [searchText, setSearchText] = createSignal("");

  // Fetch users based on search
  const usersQuery = createQuery({
    queryKey: () => ["users", "search", searchText()],
    queryFn: () => searchUsers(searchText())
  });

  // Fetch candidates for the selected election
  const candidatesQuery = createQuery({
    queryKey: () => ["election", props.electionId, "candidates"],
    queryFn: () => fetchCandidates(props.electionId)
  });

  // Mutation for creating a new candidate
  const createCandidateMutation = createMutation({
    mutationFn: () =>
      createCandidate(props.electionId, {
        user_id: parseInt(selectedUserId()),
        bio: bio()
      }),
    onSuccess: () => {
      setStatus("Candidate added successfully!");
      setSelectedUserId("");
      setBio("");
      setSearchText("");
      queryClient.invalidateQueries({
        queryKey: ["election", props.electionId, "candidates"]
      });
    },
    onError: error => {
      setError(error.message);
    }
  });

  const handleSubmit = e => {
    e.preventDefault();
    setStatus("");
    setError("");
    createCandidateMutation.mutate();
  };

  return (
    <div class="mt-8">
      <h3 class="text-xl font-semibold text-blue-500">Manage Candidates</h3>

      {/* Add Candidate Form */}
      <form onSubmit={handleSubmit} class="mt-4">
        <div class="flex flex-col space-y-4">
          <div>
            <label
              for="user-search"
              class="block text-sm font-medium text-gray-700 dark:text-gray-200"
            >
              Search User
            </label>
            <input
              type="text"
              id="user-search"
              value={searchText()}
              onChange={e => setSearchText(e.target.value)}
              class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:focus:border-blue-400 dark:focus:ring-blue-400"
              placeholder="Search by name or username"
            />
          </div>

          <Show when={usersQuery.data?.length > 0}>
            <div>
              <label
                for="user-select"
                class="block text-sm font-medium text-gray-700 dark:text-gray-200"
              >
                Select User
              </label>
              <select
                id="user-select"
                value={selectedUserId()}
                onChange={e => setSelectedUserId(e.target.value)}
                class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:focus:border-blue-400 dark:focus:ring-blue-400"
                required
              >
                <option value="">Select a user</option>
                {
                  <For each={usersQuery.data}>
                    {user => (
                      <option value={user.id}>
                        {user.full_name} ({user.username})
                      </option>
                    )}
                  </For>
                }
              </select>
            </div>
          </Show>

          <Show when={selectedUserId()}>
            <div>
              <label
                for="candidate-bio"
                class="block text-sm font-medium text-gray-700 dark:text-gray-200"
              >
                Bio
              </label>
              <textarea
                id="candidate-bio"
                value={bio()}
                onChange={e => setBio(e.target.value)}
                class="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:focus:border-blue-400 dark:focus:ring-blue-400"
                rows="3"
                placeholder="Enter candidate bio"
                required
              />
            </div>

            <button
              type="submit"
              disabled={createCandidateMutation.isPending}
              class="rounded-md bg-blue-500 px-4 py-2 text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
            >
              {createCandidateMutation.isPending
                ? "Adding..."
                : "Add Candidate"}
            </button>
          </Show>
        </div>
      </form>

      {/* Status Messages */}
      <Show when={status()}>
        <Info text={status()} />
      </Show>
      <Show when={error()}>
        <Error text={error()} />
      </Show>

      {/* Candidates List */}
      <div class="mt-6">
        <h4 class="mb-2 text-lg font-medium">Current Candidates</h4>
        <Show when={candidatesQuery.isLoading}>
          <p class="text-center">Loading candidates...</p>
        </Show>
        <Show when={candidatesQuery.error}>
          <Error text={candidatesQuery.error.message} />
        </Show>
        <Show when={candidatesQuery.data}>
          <div class="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
            <For each={candidatesQuery.data}>
              {candidate => (
                <div class="rounded-lg bg-gray-200 p-4 dark:bg-gray-700/50">
                  <p class="font-medium">{candidate.user.full_name}</p>
                  <p class="text-sm text-gray-600 dark:text-gray-300">
                    {candidate.user.username}
                  </p>
                  <p class="mt-1 text-sm text-gray-600 dark:text-gray-300">
                    {candidate.bio}
                  </p>
                </div>
              )}
            </For>
          </div>
        </Show>
        <Show when={candidatesQuery.data?.length === 0}>
          <p class="text-center text-gray-500">No candidates added yet.</p>
        </Show>
      </div>
    </div>
  );
};

export default CandidateManager;
