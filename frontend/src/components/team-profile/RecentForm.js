import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { chevronRight } from "solid-heroicons/solid";
import { For, Show } from "solid-js";

import { formatDates } from "../../dates";
import Avatar from "./Avatar";

const RESULT = {
  W: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  L: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  D: "bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-200"
};
const WORD = { W: "Win", L: "Loss", D: "Draw" };

const RecentForm = props => (
  <Show when={props.form.length}>
    <section aria-labelledby="form-heading">
      <h2
        id="form-heading"
        class="mt-7 text-lg font-bold text-gray-900 dark:text-white"
      >
        Recent matches
      </h2>
      <ol
        role="list"
        class="mt-3 divide-y divide-gray-100 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm dark:divide-gray-700 dark:border-gray-700 dark:bg-gray-800"
      >
        <For each={props.form}>
          {f => (
            <li>
              <A
                href={`/team/${f.opponent.slug}`}
                class="flex min-h-[56px] items-center gap-3 px-3 py-2 transition-colors duration-200 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-600 active:bg-gray-100 motion-reduce:transition-none dark:hover:bg-gray-700"
              >
                <span
                  aria-hidden="true"
                  class={`inline-flex h-7 w-7 flex-none items-center justify-center rounded-md text-sm font-bold ${RESULT[f.result]}`}
                >
                  {f.result}
                </span>
                <span class="sr-only">{WORD[f.result]}</span>
                <span class="w-14 flex-none text-sm font-semibold tabular-nums text-gray-900 dark:text-white">
                  {f.score_for}–{f.score_against}
                </span>
                <Avatar
                  src={f.opponent.image || f.opponent.image_url}
                  name={f.opponent.name}
                  size="h-7 w-7"
                />
                <span class="min-w-0 flex-1">
                  <span class="block break-words text-sm font-medium text-gray-900 dark:text-white">
                    {f.opponent.name}
                  </span>
                  <span class="block text-xs text-gray-600 dark:text-gray-300">
                    {f.tournament_title} · {formatDates(f.date, f.date)}
                  </span>
                </span>
                <Icon
                  class="h-4 w-4 flex-none text-gray-500"
                  path={chevronRight}
                  aria-hidden="true"
                />
              </A>
            </li>
          )}
        </For>
      </ol>
    </section>
  </Show>
);

export default RecentForm;
