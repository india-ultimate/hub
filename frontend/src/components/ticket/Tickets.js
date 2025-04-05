import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { chatBubbleOvalLeftEllipsis } from "solid-heroicons/outline";
import { Show } from "solid-js";

import { fetchUser } from "../../queries";
import TicketList from "./TicketList";

const Tickets = () => {
  const userQuery = createQuery(() => ["me"], fetchUser);

  return (
    <div>
      <h1 class="mb-4 text-3xl font-bold text-blue-700 dark:text-white">
        <div class="flex items-center">
          Help Center
          <Icon path={chatBubbleOvalLeftEllipsis} class="ml-2 h-8 w-8" />
        </div>
      </h1>
      <p class="mb-4 text-sm text-gray-600 dark:text-gray-300">
        Welcome to India Ultimate Help Center. Here you can create help tickets
        and track their progress. Our Operations and Tech team are ready to
        assist you with any questions or issues you might have.
      </p>

      <Show
        when={userQuery.data}
        fallback={
          <div class="mt-4 rounded-lg bg-yellow-100 p-4 text-sm text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
            <div class="flex items-center">
              <svg
                class="mr-2 h-4 w-4"
                fill="currentColor"
                viewBox="0 0 20 20"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fill-rule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clip-rule="evenodd"
                />
              </svg>
              <h3 class="text-lg font-medium">Authentication Required</h3>
            </div>
            <div class="mt-2">
              <p>
                You need to be logged in to view and create support tickets.
              </p>
              <A
                href="/login"
                class="mt-3 inline-flex items-center rounded-lg bg-blue-700 px-4 py-2 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
              >
                Log In
              </A>
            </div>
          </div>
        }
      >
        <TicketList user={userQuery.data} />
      </Show>
    </div>
  );
};

export default Tickets;
