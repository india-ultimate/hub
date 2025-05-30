import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import { fetchEligibleVoters, importEligibleVoters } from "../../queries";
import Error from "../alerts/Error";
import Info from "../alerts/Info";

const EligibleVotersManager = props => {
  const queryClient = useQueryClient();
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");
  const [file, setFile] = createSignal(null);

  // Fetch eligible voters
  const votersQuery = createQuery({
    queryKey: () => ["election", props.electionId, "eligible-voters"],
    queryFn: () => fetchEligibleVoters(props.electionId)
  });

  // Mutation for importing voters
  const importVotersMutation = createMutation({
    mutationFn: () => {
      const formData = new FormData();
      formData.append("file", file());
      return importEligibleVoters(props.electionId, formData);
    },
    onSuccess: () => {
      setStatus("Voters imported successfully!");
      setFile(null);
      queryClient.invalidateQueries({
        queryKey: ["election", props.electionId, "eligible-voters"]
      });
    },
    onError: error => {
      setError(error.message);
    }
  });

  const handleFileChange = e => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type === "text/csv") {
      setFile(selectedFile);
      setError("");
    } else {
      setError("Please select a valid CSV file");
      setFile(null);
    }
  };

  const handleSubmit = e => {
    e.preventDefault();
    if (!file()) {
      setError("Please select a CSV file");
      return;
    }
    setStatus("");
    setError("");
    importVotersMutation.mutate();
  };

  return (
    <div class="mt-8">
      <h3 class="text-xl font-semibold text-blue-500">
        Manage Eligible Voters
      </h3>

      {/* Import Voters Form */}
      <form onSubmit={handleSubmit} class="mt-4">
        <div class="flex flex-col space-y-4">
          <div>
            <label
              for="voters-file"
              class="block text-sm font-medium text-gray-700 dark:text-gray-200"
            >
              Import Voters (CSV)
            </label>
            <input
              type="file"
              id="voters-file"
              accept=".csv"
              onChange={handleFileChange}
              class="block w-full cursor-pointer rounded-lg border border-gray-300 bg-gray-50 text-sm text-gray-900 focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-400 dark:placeholder-gray-400"
            />
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
              CSV should contain a list of voter email addresses
            </p>
          </div>

          <button
            type="submit"
            disabled={importVotersMutation.isPending || !file()}
            class="rounded-md bg-blue-500 px-4 py-2 text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          >
            {importVotersMutation.isPending ? "Importing..." : "Import Voters"}
          </button>
        </div>
      </form>

      {/* Status Messages */}
      <Show when={status()}>
        <Info text={status()} />
      </Show>
      <Show when={error()}>
        <Error text={error()} />
      </Show>

      {/* Voters List */}
      <div class="mt-6">
        <h4 class="mb-2 text-lg font-medium">Current Eligible Voters</h4>
        <Show when={votersQuery.isLoading}>
          <p class="text-center">Loading voters...</p>
        </Show>
        <Show when={votersQuery.error}>
          <Error text={votersQuery.error.message} />
        </Show>
        <Show when={votersQuery.data}>
          <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead class="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <th
                    scope="col"
                    class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400"
                  >
                    Name
                  </th>
                  <th
                    scope="col"
                    class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400"
                  >
                    Username
                  </th>
                  <th
                    scope="col"
                    class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400"
                  >
                    Added On
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200 bg-white dark:divide-gray-700 dark:bg-gray-900">
                <For each={votersQuery.data}>
                  {voter => (
                    <tr>
                      <td class="whitespace-nowrap px-6 py-4 text-sm text-gray-900 dark:text-gray-100">
                        {voter.user.full_name}
                      </td>
                      <td class="whitespace-nowrap px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                        {voter.user.username}
                      </td>
                      <td class="whitespace-nowrap px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                        {new Date(voter.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
        </Show>
        <Show when={votersQuery.data?.length === 0}>
          <p class="text-center text-gray-500">No eligible voters added yet.</p>
        </Show>
      </div>
    </div>
  );
};

export default EligibleVotersManager;
