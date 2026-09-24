import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { For, Show } from "solid-js";

import { fetchMine } from "../queries";

const BADGE_COLOURS = {
  green: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  blue: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  amber: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
  gray: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
};

// Every badge carries its own words - colour never carries the meaning by
// itself, for anyone who can't tell these colours apart.
const STATUS_BADGES = {
  Detected: ["Waiting to be reviewed", "amber"],
  Notified: ["Ready to review", "blue"],
  Resolved: ["Merged", "green"],
  Dismissed: ["Closed", "gray"]
};

// A group resolves when a deletion or a merge elsewhere leaves nothing to
// do, too - so only say "Merged" when something did, as the group page does.
// An open group past its link's expiry can't be acted on; asking again
// for the same address starts a fresh one.
const statusBadge = group =>
  group.expired
    ? ["Link expired", "gray"]
    : group.status === "Resolved" && !group.anything_merged
    ? ["Sorted out", "gray"]
    : STATUS_BADGES[group.status] || [group.status, "gray"];

const RELATIVE_TIME = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const DIVISIONS = [
  [60, "second"],
  [60, "minute"],
  [24, "hour"],
  [30, "day"],
  [12, "month"],
  [Number.POSITIVE_INFINITY, "year"]
];

const timeAgo = iso => {
  let value = (Date.now() - new Date(iso).getTime()) / 1000;
  for (const [amount, unit] of DIVISIONS) {
    if (Math.abs(value) < amount)
      return RELATIVE_TIME.format(-Math.round(value), unit);
    value /= amount;
  }
  return "";
};

const startedLabel = group =>
  `${group.origin === "requested" ? "You asked" : "We found it"}, ${timeAgo(
    group.started_at
  )}`;

const PRIMARY_BUTTON =
  "inline-flex min-h-[44px] items-center rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800";

export default function MergeList() {
  const query = createQuery(() => ["merge-accounts-mine"], fetchMine);
  const groups = () => query.data || [];

  return (
    <div class="mx-auto max-w-3xl px-4 py-8">
      <div class="mb-6 flex items-center justify-between gap-4">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
          Merge accounts
        </h1>
        <A
          id="merge-list-new"
          href="/merge-accounts/new"
          class={PRIMARY_BUTTON}
        >
          Start a merge
        </A>
      </div>

      <Show when={query.isLoading}>
        <p class="text-gray-500 dark:text-gray-400">Loading…</p>
      </Show>

      <Show when={query.isError}>
        <p
          id="merge-list-error"
          role="alert"
          class="text-red-600 dark:text-red-400"
        >
          Something went wrong. Please try again.
        </p>
      </Show>

      <Show when={query.isSuccess && groups().length === 0}>
        <p id="merge-list-empty" class="text-gray-700 dark:text-gray-300">
          Nothing to merge right now.{" "}
          <A
            href="/merge-accounts/new"
            class="text-blue-700 underline hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
          >
            Start a merge
          </A>
        </p>
      </Show>

      <Show when={query.isSuccess && groups().length > 0}>
        <div class="overflow-x-auto">
          <table
            id="merge-list-table"
            class="w-full text-left text-sm text-gray-500 dark:text-gray-400"
          >
            <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
              <tr>
                <th scope="col" class="px-6 py-3">
                  Account
                </th>
                <th scope="col" class="px-6 py-3">
                  Started
                </th>
                <th scope="col" class="px-6 py-3">
                  Status
                </th>
                <th scope="col" class="px-6 py-3">
                  <span class="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <For each={groups()}>
                {group => {
                  const [text, colour] = statusBadge(group);
                  return (
                    <tr
                      id={`merge-list-row-${group.token}`}
                      class="relative border-b bg-white hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-gray-700"
                    >
                      <td class="px-6 py-4 font-mono text-gray-900 dark:text-white">
                        <A
                          href={`/merge-accounts/${group.token}`}
                          class="absolute inset-0 rounded focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-700"
                        >
                          <span class="sr-only">
                            {group.other_email
                              ? `View merge with ${group.other_email}`
                              : "View this merge"}
                          </span>
                        </A>
                        {group.other_email || "—"}
                        <Show when={group.other_count > 1}>
                          <span class="block text-xs text-gray-500 dark:text-gray-400">
                            and {group.other_count - 1} more
                          </span>
                        </Show>
                      </td>
                      <td class="px-6 py-4">{startedLabel(group)}</td>
                      <td class="px-6 py-4">
                        <span
                          class={`inline-flex items-center rounded px-2.5 py-0.5 text-xs font-medium ${BADGE_COLOURS[colour]}`}
                        >
                          {text}
                        </span>
                        <Show when={group.expired}>
                          {/* Above the row's full-size link, or it can't
                              be clicked. */}
                          <A
                            id={`merge-list-start-again-${group.token}`}
                            href="/merge-accounts/new"
                            class="relative z-10 flex min-h-[44px] items-center text-blue-700 underline hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
                          >
                            Start again
                          </A>
                        </Show>
                      </td>
                      <td
                        aria-hidden="true"
                        class="px-6 py-4 text-right text-gray-400 dark:text-gray-500"
                      >
                        →
                      </td>
                    </tr>
                  );
                }}
              </For>
            </tbody>
          </table>
        </div>
      </Show>
    </div>
  );
}
