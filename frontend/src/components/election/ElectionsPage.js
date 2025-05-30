import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { For, Show } from "solid-js";

import { fetchElections } from "../../queries";
import { displayDateShort } from "../../utils";
import Error from "../alerts/Error";

const ElectionsPage = () => {
  // Fetch all elections
  const electionsQuery = createQuery({
    queryKey: () => ["elections"],
    queryFn: fetchElections
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

  return (
    <div class="container mx-auto px-4 py-8">
      <h1 class="mb-8 text-center text-3xl font-bold text-blue-500">
        Elections
      </h1>

      <Show when={electionsQuery.isLoading}>
        <p class="text-center">Loading elections...</p>
      </Show>

      <Show when={electionsQuery.error}>
        <Error message={electionsQuery.error.message} />
      </Show>

      <Show when={electionsQuery.data}>
        <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <For each={electionsQuery.data}>
            {election => {
              const status = getElectionStatus(election);
              return (
                <A
                  href={`/election/${election.id}`}
                  class="block overflow-hidden rounded-lg bg-white shadow transition hover:shadow-lg dark:bg-gray-800"
                >
                  <div class="p-6">
                    <div class="mb-4 flex items-center justify-between">
                      <h2 class="text-xl font-semibold text-gray-900 dark:text-white">
                        {election.title}
                      </h2>
                      <span
                        class={`inline-flex rounded-full px-3 py-1 text-sm font-medium ${status.color}`}
                      >
                        {status.status}
                      </span>
                    </div>
                    <p class="mb-4 text-gray-600 dark:text-gray-300">
                      {election.description}
                    </p>
                    <div class="space-y-2 text-sm text-gray-500 dark:text-gray-400">
                      <p>
                        {displayDateShort(election.start_date)} to{" "}
                        {displayDateShort(election.end_date)}
                      </p>
                    </div>
                  </div>
                </A>
              );
            }}
          </For>
        </div>
        <Show when={electionsQuery.data.length === 0}>
          <p class="text-center text-gray-500">No elections found.</p>
        </Show>
      </Show>
    </div>
  );
};

export default ElectionsPage;
