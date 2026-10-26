import { A } from "@solidjs/router";
import { For, Show } from "solid-js";

import { formatDates } from "../../dates";
import Avatar from "./Avatar";

const RESULT = {
  W: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  L: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  D: "bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-200"
};
const WORD = { W: "Won", L: "Lost", D: "Drew" };

const SOLID = {
  W: "bg-green-700 text-white",
  L: "bg-red-700 text-white",
  D: "bg-gray-600 text-white"
};

const Badge = props => (
  <span
    aria-hidden="true"
    class={`inline-flex h-7 w-7 flex-none items-center justify-center rounded-md text-sm font-bold ${(props.solid ? SOLID : RESULT)[props.result]}`}
  >
    {props.result}
  </span>
);

const link =
  "rounded hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500";

const RecentForm = props => (
  <Show when={props.form.length}>
    <section aria-labelledby="form-heading">
      <div class="mt-7 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <h2
          id="form-heading"
          class="text-lg font-bold text-gray-900 dark:text-white"
        >
          Recent form
        </h2>
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-500 dark:text-gray-400">
            Latest first
          </span>
          <span class="sr-only">
            Last {props.form.length} results, latest first:{" "}
            {props.form.map(f => WORD[f.result]).join(", ")}
          </span>
          <div class="flex gap-1" aria-hidden="true">
            <For each={props.form}>
              {f => <Badge result={f.result} solid />}
            </For>
          </div>
        </div>
      </div>
      <ul
        role="list"
        class="mt-3 divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white shadow-sm dark:divide-gray-700 dark:border-gray-700 dark:bg-gray-800"
      >
        <For each={props.form}>
          {f => (
            <li class="flex min-h-[56px] items-center gap-3 px-3 py-1">
              <Badge result={f.result} />
              <span class="sr-only">{WORD[f.result]}</span>
              <span class="w-14 flex-none text-sm font-semibold tabular-nums text-gray-900 dark:text-white">
                {f.score_for}–{f.score_against}
              </span>
              <div class="min-w-0 flex-1">
                <A
                  href={`/team/${f.opponent.slug}`}
                  class={`flex min-h-[44px] items-center gap-2 text-sm font-medium text-gray-900 underline decoration-gray-300 underline-offset-4 hover:decoration-blue-500 dark:text-white ${link}`}
                >
                  <Avatar
                    src={f.opponent.image || f.opponent.image_url}
                    name={f.opponent.name}
                    size="h-7 w-7"
                  />
                  <span class="min-w-0 break-words">{f.opponent.name}</span>
                </A>
                <p class="pb-1.5 text-xs text-gray-600 dark:text-gray-300">
                  {f.tournament_title} · {formatDates(f.date, f.date)}
                </p>
              </div>
            </li>
          )}
        </For>
      </ul>
    </section>
  </Show>
);

export default RecentForm;
