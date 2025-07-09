import { useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import {
  castRankedVote,
  castRankedVoteForWard,
  fetchCandidates,
  fetchElection,
  getElectionVoteCount,
  getMyWards,
  getVoterVerification
} from "../../queries";
import { useStore } from "../../store";
import { displayDateShort } from "../../utils";
import Error from "../alerts/Error";
import Info from "../alerts/Info";
import Success from "../alerts/Success";

const ElectionPage = () => {
  const params = useParams();
  const electionId = params.id;
  const [store] = useStore();
  const queryClient = useQueryClient();
  const [rankedChoices, setRankedChoices] = createSignal([]);
  const [error, setError] = createSignal("");
  const [status, setStatus] = createSignal("");

  // Guardian voting state
  const [selectedWard, setSelectedWard] = createSignal(null);
  const [wardRankedChoices, setWardRankedChoices] = createSignal([]);
  const [guardianError, setGuardianError] = createSignal("");
  const [guardianStatus, setGuardianStatus] = createSignal("");

  // Fetch election details
  const electionQuery = createQuery({
    queryKey: () => ["election", electionId],
    queryFn: () => fetchElection(electionId)
  });

  // Fetch candidates
  const candidatesQuery = createQuery({
    queryKey: () => ["election", electionId, "candidates"],
    queryFn: () => fetchCandidates(electionId)
  });

  // Get voter verification
  const verificationQuery = createQuery({
    queryKey: () => ["election", electionId, "verification"],
    queryFn: () => getVoterVerification(electionId),
    get enabled() {
      if (!store?.data || !electionQuery.data) return false;

      const now = new Date();
      const startDate = new Date(electionQuery.data.start_date);
      const endDate = new Date(electionQuery.data.end_date);

      return now >= startDate && now <= endDate;
    }
  });

  // Get guardian's wards
  const wardsQuery = createQuery({
    queryKey: () => ["election", electionId, "wards"],
    queryFn: () => getMyWards(electionId),
    get enabled() {
      if (!store?.data || !electionQuery.data) return false;

      const now = new Date();
      const startDate = new Date(electionQuery.data.start_date);
      const endDate = new Date(electionQuery.data.end_date);

      return now >= startDate && now <= endDate;
    }
  });

  // Get vote count
  const voteCountQuery = createQuery({
    queryKey: () => ["election", electionId, "vote-count"],
    queryFn: () => getElectionVoteCount(electionId),
    get enabled() {
      if (!electionQuery.data) return false;
      return true;
    }
  });

  // Cast vote mutation
  const castVoteMutation = createMutation({
    mutationFn: () =>
      castRankedVote(electionId, {
        verification_token: verificationQuery.data?.verification_token,
        choices: rankedChoices().map((candidateId, index) => ({
          candidate_id: candidateId,
          rank: index + 1
        }))
      }),
    onSuccess: () => {
      setStatus("Vote cast successfully!");
      setError("");
      // refetch verification token alone
      queryClient.invalidateQueries({
        queryKey: ["election", electionId, "verification"],
        exact: true
      });
    },
    onError: error => {
      setError(error.message);
      setStatus("");
    }
  });

  // Cast vote for ward mutation
  const castWardVoteMutation = createMutation({
    mutationFn: () => {
      const ward = selectedWard();
      if (!ward) throw new Error("No ward selected");

      return castRankedVoteForWard(electionId, ward.id, {
        verification_token: ward.verification_token,
        choices: wardRankedChoices().map((candidateId, index) => ({
          candidate_id: candidateId,
          rank: index + 1
        }))
      });
    },
    onSuccess: () => {
      setGuardianStatus("Vote cast successfully for ward!");
      setGuardianError("");
      setSelectedWard(null);
      setWardRankedChoices([]);
      // refetch wards to update voting status
      queryClient.invalidateQueries({
        queryKey: ["election", electionId, "wards"],
        exact: true
      });
    },
    onError: error => {
      setGuardianError(error.message);
      setGuardianStatus("");
    }
  });

  const getElectionStatus = election => {
    const now = new Date();
    const startDate = new Date(election.start_date);
    const endDate = new Date(election.end_date);

    if (now < startDate) {
      return {
        status: "Upcoming",
        color:
          "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300"
      };
    } else if (now >= startDate && now <= endDate) {
      return {
        status: "Active",
        color:
          "bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300"
      };
    } else {
      return {
        status: "Completed",
        color:
          "bg-gray-100 text-gray-800 dark:bg-gray-700/50 dark:text-gray-300"
      };
    }
  };

  const handleRankChange = (candidateId, newRank) => {
    const currentChoices = rankedChoices();
    const currentIndex = currentChoices.indexOf(candidateId);

    // Remove the candidate from their current position
    if (currentIndex !== -1) {
      currentChoices.splice(currentIndex, 1);
    }

    // Insert the candidate at their new position
    currentChoices.splice(newRank - 1, 0, candidateId);

    setRankedChoices([...currentChoices]);
  };

  const handleSubmitVote = e => {
    e.preventDefault();
    if (rankedChoices().length !== candidatesQuery.data.length) {
      setError("Please rank all candidates");
      return;
    }
    castVoteMutation.mutate();
  };

  const handleWardRankChange = (candidateId, newRank) => {
    const currentChoices = wardRankedChoices();
    const currentIndex = currentChoices.indexOf(candidateId);

    // Remove the candidate from their current position
    if (currentIndex !== -1) {
      currentChoices.splice(currentIndex, 1);
    }

    // Insert the candidate at their new position
    currentChoices.splice(newRank - 1, 0, candidateId);

    setWardRankedChoices([...currentChoices]);
  };

  const handleSubmitWardVote = e => {
    e.preventDefault();
    if (wardRankedChoices().length !== candidatesQuery.data.length) {
      setGuardianError("Please rank all candidates");
      return;
    }
    castWardVoteMutation.mutate();
  };

  const handleSelectWard = ward => {
    setSelectedWard(ward);
    setWardRankedChoices([]);
    setGuardianError("");
    setGuardianStatus("");
  };

  return (
    <div class="container mx-auto px-4 py-8">
      <Show when={electionQuery.isLoading}>
        <p class="text-center">Loading election details...</p>
      </Show>

      <Show when={electionQuery.error}>
        <Error text={electionQuery.error.message} />
      </Show>

      <Show when={electionQuery.data}>
        {election => {
          const electionStatus = getElectionStatus(election());
          return (
            <div class="space-y-8">
              {/* Election Header */}
              <div class="rounded-lg bg-white p-6 shadow dark:bg-gray-800">
                <div class="mb-4 flex items-center justify-between">
                  <h1 class="text-3xl font-bold text-gray-900 dark:text-white">
                    {election().title}
                  </h1>
                  <span
                    class={`inline-flex rounded-full px-3 py-1 text-sm font-medium ${electionStatus.color}`}
                  >
                    {electionStatus.status}
                  </span>
                </div>
                <p class="mb-6 text-lg text-gray-600 dark:text-gray-300">
                  {election().description}
                </p>
                <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  <div>
                    <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400">
                      Voting Period
                    </h3>
                    <p class="mt-1 text-gray-900 dark:text-white">
                      {displayDateShort(election().start_date)} to{" "}
                      {displayDateShort(election().end_date)}
                    </p>
                  </div>
                  <div>
                    <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400">
                      Number of Candidates
                    </h3>
                    <p class="mt-1 text-gray-900 dark:text-white">
                      {candidatesQuery.data?.length || 0}
                    </p>
                  </div>
                  <div>
                    <h3 class="text-sm font-medium text-gray-500 dark:text-gray-400">
                      Available seats
                    </h3>
                    <p class="mt-1 text-gray-900 dark:text-white">
                      {election().num_winners}
                    </p>
                  </div>
                </div>
              </div>

              {/* Vote Count Display */}
              {voteCountQuery.data && (
                <div class="mb-6 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                  <div class="flex flex-col md:flex-row md:items-center md:justify-between">
                    <div class="text-sm text-gray-600 dark:text-gray-300">
                      <span class="font-medium text-gray-900 dark:text-white">
                        {voteCountQuery.data.total_voted}
                      </span>{" "}
                      out of{" "}
                      <span class="font-medium text-gray-900 dark:text-white">
                        {voteCountQuery.data.total_eligible}
                      </span>{" "}
                      eligible voters have voted 🎉
                    </div>
                    {/* On md+ screens, show turnout inline; on mobile, hide here */}
                    <div class="hidden text-sm text-gray-600 dark:text-gray-300 md:block">
                      {voteCountQuery.data.turnout_percentage}% turnout
                    </div>
                  </div>
                  <div class="mt-2 h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      class="h-2 rounded-full bg-blue-600 transition-all duration-300"
                      style={`width: ${voteCountQuery.data.turnout_percentage}%`}
                    />
                  </div>
                  {/* On mobile, show turnout below the bar */}
                  <div class="mt-2 block text-center text-sm text-gray-600 dark:text-gray-300 md:hidden">
                    {voteCountQuery.data.turnout_percentage}% turnout
                  </div>
                </div>
              )}

              {/* Voting Section */}
              <Show when={electionStatus.status === "Active"}>
                <div class="rounded-lg bg-white p-6 shadow dark:bg-gray-800">
                  <h2 class="mb-6 text-2xl font-semibold text-gray-900 dark:text-white">
                    Cast Your Vote
                  </h2>

                  <Show when={!store?.data}>
                    <div class="rounded-lg bg-yellow-50 p-4 dark:bg-yellow-900/50">
                      <p class="text-yellow-800 dark:text-yellow-200">
                        Please log in to cast your vote.
                      </p>
                    </div>
                  </Show>

                  <Show when={store?.data}>
                    <Show when={verificationQuery.isLoading}>
                      <p class="text-center">Checking voting eligibility...</p>
                    </Show>

                    <Show when={verificationQuery.error}>
                      <Error text={verificationQuery.error.message} />
                    </Show>

                    <Show when={verificationQuery.isSuccess}>
                      <Show
                        when={!verificationQuery.data.is_used}
                        fallback={
                          <Success text="Your vote has been registered ✅" />
                        }
                      >
                        <form onSubmit={handleSubmitVote} class="space-y-6">
                          <div class="space-y-4">
                            <For each={candidatesQuery.data}>
                              {candidate => (
                                <div class="flex flex-col items-center space-y-2 rounded-lg border border-gray-200 p-4 dark:border-gray-700 md:flex-row md:space-x-4 md:space-y-0">
                                  <div class="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-xl text-blue-600 dark:bg-blue-900 dark:text-blue-300">
                                    {candidate.profile_pic_url ? (
                                      <img
                                        src={candidate.profile_pic_url}
                                        alt={candidate.user.full_name}
                                        class="h-full w-full rounded-full object-cover"
                                      />
                                    ) : (
                                      candidate.user.full_name.charAt(0)
                                    )}
                                  </div>
                                  <div class="flex-1">
                                    <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                                      {candidate.user.full_name}
                                    </h3>
                                  </div>
                                  <select
                                    value={
                                      rankedChoices().indexOf(candidate.id) +
                                        1 || ""
                                    }
                                    onChange={e =>
                                      handleRankChange(
                                        candidate.id,
                                        parseInt(e.target.value)
                                      )
                                    }
                                    class="rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:focus:border-blue-400 dark:focus:ring-blue-400"
                                  >
                                    <option value="">Select rank</option>
                                    {Array.from(
                                      { length: candidatesQuery.data.length },
                                      (_, i) => (
                                        <option value={i + 1}>
                                          Rank {i + 1}
                                        </option>
                                      )
                                    )}
                                  </select>
                                </div>
                              )}
                            </For>
                          </div>

                          <Show when={error()}>
                            <Error text={error()} />
                          </Show>

                          <Show when={status()}>
                            <Info text={status()} />
                          </Show>

                          <button
                            type="submit"
                            disabled={castVoteMutation.isPending}
                            class="w-full rounded-md bg-blue-500 px-4 py-2 text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
                          >
                            {castVoteMutation.isPending
                              ? "Casting Vote..."
                              : "Cast Vote"}
                          </button>
                        </form>
                      </Show>
                    </Show>
                  </Show>
                </div>
              </Show>

              {/* Guardian Voting Section */}
              <Show when={electionStatus.status === "Active" && store?.data}>
                <Show when={wardsQuery.isLoading}>
                  <div class="rounded-lg bg-white p-6 shadow dark:bg-gray-800">
                    <p class="text-center">Checking for eligible wards...</p>
                  </div>
                </Show>

                <Show when={wardsQuery.error}>
                  <div class="rounded-lg bg-white p-6 shadow dark:bg-gray-800">
                    <Error text={wardsQuery.error.message} />
                  </div>
                </Show>

                <Show when={wardsQuery.isSuccess && wardsQuery.data.length > 0}>
                  <div class="rounded-lg bg-white p-6 shadow dark:bg-gray-800">
                    <h2 class="mb-6 text-2xl font-semibold text-gray-900 dark:text-white">
                      Vote on Behalf of Your Wards
                    </h2>

                    <div class="mb-6">
                      <h3 class="mb-4 text-lg font-medium text-gray-900 dark:text-white">
                        Select a Ward to Vote For:
                      </h3>
                      <div class="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                        <For each={wardsQuery.data}>
                          {ward => (
                            <button
                              onClick={() => handleSelectWard(ward)}
                              disabled={ward.is_used}
                              class={`rounded-lg border p-4 text-left transition-colors ${
                                selectedWard()?.id === ward.id
                                  ? "border-blue-500 bg-blue-50 dark:border-blue-400 dark:bg-blue-900/50"
                                  : "border-gray-200 hover:border-gray-300 dark:border-gray-700 dark:hover:border-gray-600"
                              } ${
                                ward.is_used
                                  ? "cursor-not-allowed opacity-50"
                                  : "cursor-pointer"
                              }`}
                            >
                              <div class="font-medium text-gray-900 dark:text-white">
                                {ward.name}
                              </div>
                              <div class="text-sm text-gray-500 dark:text-gray-400">
                                {ward.email}
                              </div>
                              <div class="mt-2">
                                {ward.is_used ? (
                                  <span class="inline-flex items-center rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-800 dark:bg-green-900/50 dark:text-green-300">
                                    ✓ Voted
                                  </span>
                                ) : (
                                  <span class="inline-flex items-center rounded-full bg-yellow-100 px-2 py-1 text-xs font-medium text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300">
                                    ⏳ Pending
                                  </span>
                                )}
                              </div>
                            </button>
                          )}
                        </For>
                      </div>
                    </div>

                    <Show when={selectedWard() && !selectedWard().is_used}>
                      <div class="rounded-lg border border-gray-200 p-2 dark:border-gray-700">
                        <h3 class="mb-4 text-lg font-medium text-gray-900 dark:text-white">
                          Cast Vote for {selectedWard().name}
                        </h3>

                        <form onSubmit={handleSubmitWardVote} class="space-y-6">
                          <div class="space-y-4">
                            <For each={candidatesQuery.data}>
                              {candidate => (
                                <div class="flex flex-col  items-center space-y-2 rounded-lg border border-gray-200 p-4 dark:border-gray-700 md:flex-row md:space-x-4 md:space-y-0">
                                  <div class="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-xl text-blue-600 dark:bg-blue-900 dark:text-blue-300">
                                    {candidate.profile_pic_url ? (
                                      <img
                                        src={candidate.profile_pic_url}
                                        alt={candidate.user.full_name}
                                        class="h-full w-full rounded-full object-cover"
                                      />
                                    ) : (
                                      candidate.user.full_name.charAt(0)
                                    )}
                                  </div>
                                  <div class="flex-1">
                                    <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
                                      {candidate.user.full_name}
                                    </h3>
                                  </div>
                                  <select
                                    value={
                                      wardRankedChoices().indexOf(
                                        candidate.id
                                      ) + 1 || ""
                                    }
                                    onChange={e =>
                                      handleWardRankChange(
                                        candidate.id,
                                        parseInt(e.target.value)
                                      )
                                    }
                                    class="rounded-md border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:focus:border-blue-400 dark:focus:ring-blue-400"
                                  >
                                    <option value="">Select rank</option>
                                    {Array.from(
                                      { length: candidatesQuery.data.length },
                                      (_, i) => (
                                        <option value={i + 1}>
                                          Rank {i + 1}
                                        </option>
                                      )
                                    )}
                                  </select>
                                </div>
                              )}
                            </For>
                          </div>

                          <Show when={guardianError()}>
                            <Error text={guardianError()} />
                          </Show>

                          <Show when={guardianStatus()}>
                            <Info text={guardianStatus()} />
                          </Show>

                          <div class="flex space-x-4">
                            <button
                              type="submit"
                              disabled={castWardVoteMutation.isPending}
                              class="flex-1 rounded-md bg-green-500 px-4 py-2 text-white hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:opacity-50"
                            >
                              {castWardVoteMutation.isPending
                                ? "Casting Vote..."
                                : "Cast Vote for Ward"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedWard(null);
                                setWardRankedChoices([]);
                                setGuardianError("");
                                setGuardianStatus("");
                              }}
                              class="rounded-md border border-gray-300 bg-white px-4 py-2 text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
                            >
                              Cancel
                            </button>
                          </div>
                        </form>
                      </div>
                    </Show>
                  </div>
                </Show>
              </Show>

              {/* Candidates Section */}
              <div class=" bg-white dark:bg-gray-800">
                <h2 class="mb-6 text-2xl font-semibold text-gray-900 dark:text-white">
                  Candidates
                </h2>

                <Show when={candidatesQuery.isLoading}>
                  <p class="text-center">Loading candidates...</p>
                </Show>

                <Show when={candidatesQuery.error}>
                  <Error text={candidatesQuery.error.message} />
                </Show>

                <Show when={candidatesQuery.data}>
                  <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    <For each={candidatesQuery.data}>
                      {candidate => (
                        <div class="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
                          <div class="mb-2 flex items-center justify-center">
                            <div class="flex h-40 w-40 items-center justify-center rounded-full bg-blue-100 text-3xl text-blue-600 dark:bg-blue-900 dark:text-blue-300">
                              {candidate.profile_pic_url ? (
                                <img
                                  src={candidate.profile_pic_url}
                                  alt={candidate.user.full_name}
                                  class="h-full w-full rounded-full object-cover"
                                />
                              ) : (
                                candidate.user.full_name.charAt(0)
                              )}
                            </div>
                          </div>
                          <h3 class="text-center text-lg font-semibold text-gray-900 dark:text-white">
                            {candidate.user.full_name}
                          </h3>
                          <p class="my-3 whitespace-pre-wrap text-gray-600 dark:text-gray-300">
                            {candidate.bio}
                          </p>
                          <Show when={candidate.manifesto_link}>
                            <a
                              href={candidate.manifesto_link}
                              target="_blank"
                              rel="noopener noreferrer"
                              class="inline-flex items-center rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                            >
                              View Manifesto
                              <svg
                                class="ml-2 h-4 w-4"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  stroke-linecap="round"
                                  stroke-linejoin="round"
                                  stroke-width="2"
                                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                                />
                              </svg>
                            </a>
                          </Show>
                        </div>
                      )}
                    </For>
                  </div>
                  <Show when={candidatesQuery.data.length === 0}>
                    <p class="text-center text-gray-500">No candidates yet.</p>
                  </Show>
                </Show>
              </div>

              {/* Winners Section (if election is completed) */}
              {/* <Show when={election().winners}>
                <div class="rounded-lg bg-white p-6 shadow dark:bg-gray-800">
                  <h2 class="mb-6 text-2xl font-semibold text-gray-900 dark:text-white">
                    Winners
                  </h2>
                  <div class="space-y-4">
                    <For each={election().winners}>
                      {winner => (
                        <div class="flex items-center justify-between rounded-lg border border-gray-200 p-4 dark:border-gray-700">
                          <span class="text-lg font-medium text-gray-900 dark:text-white">
                            {winner.name}
                          </span>
                          <span class="text-sm text-gray-500 dark:text-gray-400">
                            {winner.votes} votes
                          </span>
                        </div>
                      )}
                    </For>
                  </div>
                </div>
              </Show> */}
            </div>
          );
        }}
      </Show>
    </div>
  );
};

export default ElectionPage;
