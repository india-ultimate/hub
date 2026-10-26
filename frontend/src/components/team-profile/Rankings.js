import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { chevronRight } from "solid-heroicons/solid";
import { For, Show } from "solid-js";

import { ordinal } from "../../dates";
import { eventLine } from "../../rankings";

const MEDAL = {
  1: "border-l-amber-400",
  2: "border-l-slate-400",
  3: "border-l-orange-500"
};

const CIRCLE = {
  1: "bg-amber-100",
  2: "bg-slate-200",
  3: "bg-orange-100"
};

const circle = r =>
  r.tier === "Challenger" ? "bg-gray-100" : (CIRCLE[r.rank] ?? "bg-gray-100");

const edge = r =>
  r.tier === "Challenger"
    ? "border-l-gray-200"
    : (MEDAL[r.rank] ?? "border-l-gray-200");

const Rankings = props => (
  <Show when={props.rankings.length}>
    <ul
      aria-label="National rankings"
      class="mt-3 grid grid-cols-1 gap-2 text-left sm:grid-cols-[repeat(auto-fill,minmax(15rem,1fr))]"
    >
      <For each={props.rankings}>
        {r => (
          <li class="min-w-0">
            <A
              href={`/tournament/${r.tournament_slug}/team/${props.team.slug}`}
              data-ranking
              class={`flex min-h-[44px] items-center gap-2 rounded-xl border border-l-4 border-gray-200 bg-white px-3 py-1.5 transition-colors duration-200 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 active:bg-gray-100 motion-reduce:transition-none dark:bg-gray-800 ${edge(r)}`}
            >
              <span
                aria-hidden="true"
                class={`inline-flex h-7 min-w-[1.75rem] flex-none items-center justify-center rounded-full px-1 text-sm font-bold tabular-nums text-gray-900 ${circle(r)}`}
              >
                #{r.rank}
              </span>
              <span class="min-w-0 flex-1 leading-tight">
                <span class="block text-sm font-semibold text-gray-900 dark:text-white">
                  <span class="sr-only">Ranked {ordinal(r.rank)}, </span>
                  {r.label}
                  <Show when={r.tier}> · {r.tier}</Show>
                </span>
                <span class="block break-words text-xs text-gray-700 dark:text-gray-300">
                  {eventLine(r)}
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
    </ul>
  </Show>
);

export default Rankings;
