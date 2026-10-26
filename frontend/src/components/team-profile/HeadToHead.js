import { A } from "@solidjs/router";
import { For, Show } from "solid-js";

import Avatar from "./Avatar";

const HeadToHead = props => (
  <Show when={props.rivals.length}>
    <section aria-labelledby="h2h-heading">
      <h2
        id="h2h-heading"
        class="mt-7 text-lg font-bold text-gray-900 dark:text-white"
      >
        Head to head
      </h2>
      <ul
        role="list"
        class="mt-3 divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white shadow-sm dark:divide-gray-700 dark:border-gray-700 dark:bg-gray-800"
      >
        <For each={props.rivals}>
          {r => (
            <li class="px-3 pb-3 pt-1">
              <div class="flex min-h-[44px] items-center gap-3">
                <A
                  href={`/team/${r.team.slug}`}
                  class="flex min-h-[44px] min-w-0 flex-1 items-center gap-2 rounded text-sm font-medium text-gray-900 underline decoration-gray-300 underline-offset-4 hover:decoration-blue-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 active:bg-gray-100 dark:text-white"
                >
                  <Avatar
                    src={r.team.image || r.team.image_url}
                    name={r.team.name}
                    size="h-7 w-7"
                  />
                  <span class="min-w-0 break-words">{r.team.name}</span>
                </A>
                <span class="flex-none text-xs text-gray-600 dark:text-gray-300">
                  {r.played} {r.played === 1 ? "game" : "games"}
                </span>
                <b class="w-12 flex-none text-right text-sm tabular-nums text-gray-900 dark:text-white">
                  <span class="sr-only">Won–lost </span>
                  {r.wins}–{r.losses}
                </b>
              </div>
              <div
                class="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700"
                aria-hidden="true"
              >
                <div
                  class="h-full bg-green-500"
                  style={{ width: `${(r.wins / r.played) * 100}%` }}
                />
              </div>
            </li>
          )}
        </For>
      </ul>
    </section>
  </Show>
);

export default HeadToHead;
