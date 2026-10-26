import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { chevronRight } from "solid-heroicons/solid";
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
            <li>
              <A
                href={`/team/${r.team.slug}`}
                class="block min-h-[56px] px-3 py-2 transition-colors duration-200 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-600 active:bg-gray-100 motion-reduce:transition-none dark:hover:bg-gray-700"
              >
                <span class="flex min-h-[40px] items-center gap-3">
                  <Avatar
                    src={r.team.image || r.team.image_url}
                    name={r.team.name}
                    size="h-7 w-7"
                  />
                  <span class="min-w-0 flex-1 break-words text-sm font-medium text-gray-900 dark:text-white">
                    {r.team.name}
                  </span>
                  <span class="flex-none text-xs text-gray-600 dark:text-gray-300">
                    {r.played} {r.played === 1 ? "game" : "games"}
                  </span>
                  <b class="w-12 flex-none text-right text-sm tabular-nums text-gray-900 dark:text-white">
                    <span class="sr-only">Won–lost </span>
                    {r.wins}–{r.losses}
                  </b>
                  <Icon
                    class="h-4 w-4 flex-none text-gray-500"
                    path={chevronRight}
                    aria-hidden="true"
                  />
                </span>
                <span
                  class="mt-1 block h-1.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700"
                  aria-hidden="true"
                >
                  <span
                    class="block h-full bg-green-600"
                    style={{ width: `${(r.wins / r.played) * 100}%` }}
                  />
                </span>
              </A>
            </li>
          )}
        </For>
      </ul>
    </section>
  </Show>
);

export default HeadToHead;
