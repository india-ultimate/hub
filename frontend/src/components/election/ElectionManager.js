import { createMutation, createQuery } from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import {
  fetchElection,
  fetchElections,
  generateElectionResults,
  getElectionResults,
  sendElectionNotification
} from "../../queries";
import { useStore } from "../../store";
import Error from "../alerts/Error";
import CandidateManager from "./CandidateManager";
import ElectionCreationForm from "./ElectionCreationForm";
import EligibleVotersManager from "./EligibleVotersManager";

const ElectionManager = () => {
  const [store] = useStore();
  const [selectedElectionId, setSelectedElectionId] = createSignal("");

  // Fetch all elections
  const electionsQuery = createQuery({
    queryKey: () => ["elections"],
    queryFn: fetchElections
  });

  // Fetch selected election details
  const electionQuery = createQuery({
    queryKey: () => ["election", selectedElectionId()],
    queryFn: () => fetchElection(selectedElectionId())
  });

  // Fetch election results
  const resultsQuery = createQuery({
    queryKey: () => ["election", selectedElectionId(), "results"],
    queryFn: () => getElectionResults(selectedElectionId()),
    get enabled() {
      return !!selectedElectionId();
    }
  });

  // Generate results mutation
  const generateResultsMutation = createMutation({
    mutationFn: electionId => generateElectionResults(electionId),
    onSuccess: () => {
      // Refetch results after generating
      resultsQuery.refetch();
    }
  });

  // Send notification mutation
  const sendNotificationMutation = createMutation({
    mutationFn: electionId => sendElectionNotification(electionId),
    onSuccess: () => {
      // Show success message
      alert("Email notifications sent successfully!");
    },
    onError: error => {
      alert(`Failed to send notifications: ${error.message}`);
    }
  });

  const handleGenerateResults = () => {
    if (selectedElectionId()) {
      generateResultsMutation.mutate(selectedElectionId());
    }
  };

  const handleSendNotification = () => {
    if (selectedElectionId()) {
      if (
        confirm(
          "Are you sure you want to send email notifications to all eligible voters?"
        )
      ) {
        sendNotificationMutation.mutate(selectedElectionId());
      }
    }
  };

  const electionOptions = () => {
    if (!electionsQuery.data) return [];
    return [
      { value: "", label: "Select an election" },
      ...electionsQuery.data.map(election => ({
        value: election.id.toString(),
        label: election.title
      }))
    ];
  };

  const handleElectionChange = e => {
    setSelectedElectionId(e.target.value);
  };

  return (
    <Show when={store?.data?.is_staff} fallback={<p>Not Authorised!</p>}>
      <div class="space-y-8">
        <div>
          <h1 class="text-center text-2xl font-bold text-blue-500">
            Create New Election
          </h1>
          <div class="mt-4">
            <ElectionCreationForm />
          </div>
        </div>

        <div class="mt-8">
          <h2 class="text-center text-2xl font-bold text-blue-500">
            View Election Details
          </h2>
          <div class="mt-4">
            <div class="flex flex-col space-y-2">
              <label
                for="election-select"
                class="text-sm font-medium text-gray-700 dark:text-gray-200"
              >
                Select Election
              </label>
              <select
                id="election-select"
                value={selectedElectionId()}
                onChange={handleElectionChange}
                class="rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:focus:border-blue-400 dark:focus:ring-blue-400"
              >
                <For each={electionOptions()}>
                  {option => (
                    <option value={option.value}>{option.label}</option>
                  )}
                </For>
              </select>
            </div>

            <Show when={electionQuery.isLoading}>
              <p class="mt-4 text-center">Loading election details...</p>
            </Show>

            <Show when={electionQuery.error}>
              <Error text={electionQuery.error.message} />
            </Show>

            <Show when={selectedElectionId() !== "" && electionQuery.data}>
              <div class="mt-4 rounded-lg bg-gray-200 p-6 dark:bg-gray-700/50">
                <h3 class="mb-4 text-xl font-semibold">
                  {electionQuery.data.title}
                </h3>
                <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <p class="font-medium">Description:</p>
                    <p class="mt-1">{electionQuery.data.description}</p>
                  </div>
                  <div>
                    <p class="font-medium">Voting Method:</p>
                    <p class="mt-1">{electionQuery.data.voting_method}</p>
                  </div>
                  <div>
                    <p class="font-medium">Start Date:</p>
                    <p class="mt-1">
                      {new Date(electionQuery.data.start_date).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p class="font-medium">End Date:</p>
                    <p class="mt-1">
                      {new Date(electionQuery.data.end_date).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p class="font-medium">Number of Winners:</p>
                    <p class="mt-1">{electionQuery.data.num_winners}</p>
                  </div>
                  <div>
                    <p class="font-medium">Status:</p>
                    <p class="mt-1">
                      {electionQuery.data.is_active ? "Active" : "Inactive"}
                    </p>
                  </div>
                </div>

                <Show when={electionQuery.data.winners}>
                  <div class="mt-4">
                    <p class="font-medium">Winners:</p>
                    <ul class="mt-1 list-inside list-disc">
                      <For each={electionQuery.data.winners}>
                        {winner => (
                          <li>
                            {winner.name} ({winner.votes} votes)
                          </li>
                        )}
                      </For>
                    </ul>
                  </div>
                </Show>

                {/* Results Section */}
                <div class="mt-8">
                  <div class="flex items-center justify-between">
                    <h4 class="text-lg font-semibold">Election Results</h4>
                    <div class="flex space-x-2">
                      <button
                        onClick={handleSendNotification}
                        disabled={sendNotificationMutation.isPending}
                        class="rounded-md bg-green-500 px-4 py-2 text-white hover:bg-green-600 disabled:bg-green-300"
                      >
                        {sendNotificationMutation.isPending
                          ? "Sending..."
                          : "📧 Send Notifications"}
                      </button>
                      <button
                        onClick={handleGenerateResults}
                        disabled={generateResultsMutation.isPending}
                        class="rounded-md bg-blue-500 px-4 py-2 text-white hover:bg-blue-600 disabled:bg-blue-300"
                      >
                        {generateResultsMutation.isPending
                          ? "Generating..."
                          : "Generate Results"}
                      </button>
                    </div>
                  </div>

                  <Show when={generateResultsMutation.error}>
                    <Error text={generateResultsMutation.error.message} />
                  </Show>

                  <Show when={resultsQuery.isLoading}>
                    <p class="mt-4 text-center">Loading results...</p>
                  </Show>

                  <Show when={resultsQuery.error}>
                    <Error text={resultsQuery.error.message} />
                  </Show>

                  <Show when={resultsQuery.data?.rounds}>
                    <div class="mt-4 space-y-6">
                      <For each={resultsQuery.data.rounds}>
                        {(round, index) => (
                          <div class="rounded-lg border border-gray-300 bg-white p-4 dark:border-gray-600 dark:bg-gray-800">
                            <h5 class="mb-3 font-medium">
                              Round {index() + 1}
                            </h5>
                            <div class="space-y-2">
                              <For each={round.candidates}>
                                {candidate => (
                                  <div class="flex items-center justify-between rounded-md bg-gray-100 px-3 py-2 dark:bg-gray-700">
                                    <span>{candidate.name}</span>
                                    <div class="flex items-center space-x-4">
                                      <span class="text-sm text-gray-600 dark:text-gray-300">
                                        {candidate.votes} votes
                                      </span>
                                      <span
                                        class={`rounded-full px-2 py-1 text-xs ${
                                          candidate.status === "winner"
                                            ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                                            : candidate.status === "eliminated"
                                            ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                                            : "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                                        }`}
                                      >
                                        {candidate.status}
                                      </span>
                                    </div>
                                  </div>
                                )}
                              </For>
                            </div>
                          </div>
                        )}
                      </For>
                    </div>
                  </Show>
                </div>
              </div>

              <CandidateManager electionId={selectedElectionId()} />
              <EligibleVotersManager electionId={selectedElectionId()} />
            </Show>
          </div>
        </div>
      </div>
    </Show>
  );
};

export default ElectionManager;
