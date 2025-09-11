import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import { Spinner } from "../../icons";
import {
  createServiceRequest,
  fetchServiceRequests,
  searchPlayers
} from "../../queries";
import Info from "../alerts/Info";

const ServiceRequestModal = props => {
  const [isOpen, setIsOpen] = createSignal(false);
  const [message, setMessage] = createSignal("");
  const [selectedPlayers, setSelectedPlayers] = createSignal([]);
  const [search, setSearch] = createSignal("");
  const [searchResults, setSearchResults] = createSignal([]);
  const [isSubmitting, setIsSubmitting] = createSignal(false);
  const [status, setStatus] = createSignal("");

  // Fetch existing service requests
  const serviceRequestsQuery = createQuery(
    () => ["service-requests"],
    () => fetchServiceRequests()
  );

  // Search players when search term changes
  createEffect(() => {
    if (search().trim().length > 2) {
      searchPlayers(search(), { pageIndex: 0, pageSize: 10 })
        .then(results => {
          setSearchResults(results?.items || []);
        })
        .catch(() => {
          setSearchResults([]);
        });
    } else {
      setSearchResults([]);
    }
  });

  const openModal = () => {
    setIsOpen(true);
    setMessage("");
    setSelectedPlayers([]);
    setSearch("");
    setStatus("");
  };

  const closeModal = () => {
    setIsOpen(false);
    setMessage("");
    setSelectedPlayers([]);
    setSearch("");
    setStatus("");
  };

  const addPlayer = player => {
    if (!selectedPlayers().find(p => p.id === player.id)) {
      setSelectedPlayers([...selectedPlayers(), player]);
    }
    setSearch("");
  };

  const removePlayer = playerId => {
    setSelectedPlayers(selectedPlayers().filter(p => p.id !== playerId));
  };

  const submitServiceRequest = async () => {
    if (!message().trim()) {
      setStatus("Please enter a message");
      return;
    }

    if (selectedPlayers().length === 0) {
      setStatus("Please add at least one player to the request");
      return;
    }

    setIsSubmitting(true);
    setStatus("");

    try {
      await createServiceRequest({
        type: "REQUEST_SPONSORED_MEMBERSHIP",
        message: message().trim(),
        service_player_ids: selectedPlayers().map(p => p.id)
      });

      setStatus("Service request submitted successfully!");

      // Clear the form
      setMessage("");
      setSelectedPlayers([]);

      // Refresh the service requests list
      serviceRequestsQuery.refetch();
    } catch (error) {
      setStatus(`Error: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      {/* Trigger Button */}
      <button
        onClick={openModal}
        class="mb-2 me-2 rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
      >
        Request Supported Membership
      </button>

      {/* Modal */}
      <Show when={isOpen()}>
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div class="relative max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl dark:bg-gray-800">
            {/* Header */}
            <div class="mb-4 flex items-center justify-between border-b border-gray-200 pb-4 dark:border-gray-700">
              <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
                Supported Membership Requests
              </h3>
              <button
                onClick={closeModal}
                class="rounded-lg p-1.5 text-gray-400 hover:bg-gray-200 hover:text-gray-900 dark:hover:bg-gray-700 dark:hover:text-white"
              >
                <Icon path={xMark} style={{ width: "24px" }} />
              </button>
            </div>

            {/* Existing Requests Section */}
            <div class="mb-8">
              <h4 class="mb-4 text-lg font-medium text-gray-900 dark:text-white">
                Your Existing Requests
              </h4>
              <Show
                when={serviceRequestsQuery.isLoading}
                fallback={
                  <Show
                    when={serviceRequestsQuery.data?.length > 0}
                    fallback={
                      <Info text="No service requests found. Create your first request below." />
                    }
                  >
                    <div class="space-y-4">
                      <For each={serviceRequestsQuery.data}>
                        {request => (
                          <div class="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
                            <div class="flex items-center justify-between">
                              <div>
                                <h5 class="font-medium text-gray-900 dark:text-white">
                                  {request.type.replace(/_/g, " ")}
                                </h5>
                                <p class="text-sm text-gray-600 dark:text-gray-400">
                                  {request.message}
                                </p>
                                <p class="text-xs text-gray-500">
                                  Created:{" "}
                                  {new Date(
                                    request.created_at
                                  ).toLocaleDateString()}
                                </p>
                                <Show
                                  when={request.service_players?.length > 0}
                                >
                                  <p class="text-xs text-gray-500">
                                    Players:{" "}
                                    {request.service_players
                                      .map(p => p.full_name)
                                      .join(", ")}
                                  </p>
                                </Show>
                              </div>
                              <span
                                class={`rounded-full px-2 py-1 text-xs font-medium ${
                                  request.status === "APPROVED"
                                    ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
                                    : request.status === "REJECTED"
                                    ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300"
                                    : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
                                }`}
                              >
                                {request.status}
                              </span>
                            </div>
                          </div>
                        )}
                      </For>
                    </div>
                  </Show>
                }
              >
                <Spinner />
              </Show>
            </div>

            {/* Divider */}
            <div class="mb-8 border-t border-gray-200 dark:border-gray-700" />

            {/* Create New Request Section */}
            <div class="space-y-4">
              <h4 class="text-lg font-medium text-gray-900 dark:text-white">
                Create New Supported Membership Request
              </h4>

              {/* Message Input */}
              <div>
                <label class="mb-2 block text-sm font-medium text-gray-900 dark:text-white">
                  Request Message <span class="text-red-500">*</span>
                </label>
                <textarea
                  class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
                  rows="4"
                  placeholder="Please elaborate on why you/other players added need supported membership?"
                  value={message()}
                  onInput={e => setMessage(e.target.value)}
                />
              </div>

              {/* Player Search */}
              <div>
                <label class="mb-2 block text-sm font-medium text-gray-900 dark:text-white">
                  Add Players <span class="text-red-500">*</span>
                  <span class="ml-2 text-sm text-gray-500">
                    (At least 1 player required)
                  </span>
                </label>

                {/* Add Current User Button */}
                <Show
                  when={
                    props.currentPlayer &&
                    !selectedPlayers().find(
                      p => p.id === props.currentPlayer.id
                    )
                  }
                >
                  <button
                    onClick={() => addPlayer(props.currentPlayer)}
                    class="mb-2 rounded-lg bg-blue-100 px-3 py-1.5 text-sm font-medium text-blue-800 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-300 dark:hover:bg-blue-800"
                  >
                    + Add Myself ({props.currentPlayer.full_name})
                  </button>
                </Show>

                <div class="relative">
                  <input
                    type="text"
                    class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
                    placeholder="Search players by name or email..."
                    value={search()}
                    onInput={e => setSearch(e.target.value)}
                  />
                </div>

                {/* Search Results */}
                <Show when={searchResults().length > 0}>
                  <div class="mt-2 max-h-40 overflow-y-auto rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
                    <For each={searchResults()}>
                      {player => (
                        <button
                          class="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-700"
                          onClick={() => addPlayer(player)}
                        >
                          <div class="font-medium">{player.full_name}</div>
                          <div class="text-xs text-gray-500">
                            {player.email}
                          </div>
                        </button>
                      )}
                    </For>
                  </div>
                </Show>
              </div>

              {/* Selected Players */}
              <Show when={selectedPlayers().length > 0}>
                <div>
                  <label class="mb-2 block text-sm font-medium text-gray-900 dark:text-white">
                    Selected Players
                  </label>
                  <div class="space-y-2">
                    <For each={selectedPlayers()}>
                      {player => (
                        <div class="flex items-center justify-between rounded-lg bg-blue-50 p-2 dark:bg-blue-900">
                          <span class="text-sm font-medium text-blue-900 dark:text-blue-100">
                            {player.full_name}
                          </span>
                          <button
                            onClick={() => removePlayer(player.id)}
                            class="rounded-full p-1 text-blue-600 hover:bg-blue-200 dark:text-blue-400 dark:hover:bg-blue-800"
                          >
                            <Icon path={xMark} style={{ width: "16px" }} />
                          </button>
                        </div>
                      )}
                    </For>
                  </div>
                </div>
              </Show>

              {/* Status Message */}
              <Show when={status()}>
                <div
                  class={`rounded-lg p-3 text-sm ${
                    status().includes("Error")
                      ? "bg-red-50 text-red-800 dark:bg-red-900 dark:text-red-300"
                      : status().includes("successfully")
                      ? "bg-green-50 text-green-800 dark:bg-green-900 dark:text-green-300"
                      : "bg-blue-50 text-blue-800 dark:bg-blue-900 dark:text-blue-300"
                  }`}
                >
                  {status()}
                </div>
              </Show>

              {/* Action Buttons */}
              <div class="flex justify-end space-x-3 pt-4">
                <button
                  onClick={closeModal}
                  class="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-4 focus:ring-gray-200 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700 dark:focus:ring-gray-700"
                >
                  Cancel
                </button>
                <button
                  onClick={submitServiceRequest}
                  disabled={
                    isSubmitting() ||
                    !message().trim() ||
                    selectedPlayers().length === 0
                  }
                  class="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                >
                  <Show when={isSubmitting()} fallback="Submit Request">
                    <div class="flex items-center">
                      <Spinner />
                      <span class="ml-2">Submitting...</span>
                    </div>
                  </Show>
                </button>
              </div>
            </div>
          </div>
        </div>
      </Show>
    </>
  );
};

export default ServiceRequestModal;
