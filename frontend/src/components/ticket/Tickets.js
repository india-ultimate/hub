import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { chatBubbleOvalLeftEllipsis, plus } from "solid-heroicons/outline";
import { Show } from "solid-js";

import { fetchUser } from "../../queries";
import TicketList from "./TicketList";

const Tickets = () => {
  const userQuery = createQuery(() => ["me"], fetchUser);

  return (
    <div class="mx-auto max-w-4xl">
      <div class="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 class="flex items-center gap-2 text-3xl font-bold text-blue-700 dark:text-white">
            Help Center
            <Icon
              path={chatBubbleOvalLeftEllipsis}
              class="h-8 w-8"
              aria-hidden="true"
            />
          </h1>
          <p class="mt-2 max-w-2xl text-sm text-gray-600 dark:text-gray-300">
            Need help with anything? Ask a question, report a problem or make a
            request, and the right people at India Ultimate will pick it up. If
            someone has already asked, upvote their ticket instead.
          </p>
        </div>
        <Show when={userQuery.data}>
          <A
            href="/tickets/new"
            class="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-blue-700 px-5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus-visible:ring-blue-800"
          >
            <Icon path={plus} class="h-5 w-5" aria-hidden="true" />
            New ticket
          </A>
        </Show>
      </div>

      <Show when={userQuery.data}>
        <TicketList user={userQuery.data} />
      </Show>
      <Show when={!userQuery.isLoading && !userQuery.data}>
        <div class="rounded-xl border border-yellow-300 bg-yellow-50 p-6 text-yellow-900 dark:border-yellow-700 dark:bg-yellow-900 dark:text-yellow-100">
          <h2 class="text-lg font-semibold">Log in to get help</h2>
          <p class="mt-1 text-sm">
            You need to be logged in to see tickets and ask for help.
          </p>
          <A
            href="/login"
            class="mt-4 inline-flex min-h-[44px] items-center rounded-lg bg-blue-700 px-5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300"
          >
            Log in
          </A>
        </div>
      </Show>
    </div>
  );
};

export default Tickets;
