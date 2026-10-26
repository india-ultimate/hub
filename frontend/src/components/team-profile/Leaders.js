import { For, Show } from "solid-js";

import { PlayerLink } from "../../playerLinks";
import Avatar from "./Avatar";

const CATEGORIES = [
  ["goals", "Goals"],
  ["assists", "Assists"],
  ["blocks", "Blocks"],
  ["mvp", "MVP"],
  ["msp", "MSP"]
];

const Leaders = props => {
  const from = () => ({ label: props.team.name });
  const shown = () => CATEGORIES.filter(([key]) => props.leaders[key].length);
  return (
    <Show when={shown().length}>
      <section
        aria-labelledby="leaders-heading"
        class="min-w-0 md:only:col-span-2"
      >
        <h2
          id="leaders-heading"
          class="text-lg font-bold text-gray-900 dark:text-white"
        >
          Team leaders
        </h2>
        <div class="mt-3 grid gap-3 sm:grid-cols-2 md:grid-cols-1 lg:grid-cols-2">
          <For each={shown()}>
            {([key, label]) => (
              <div
                data-leaders={key}
                class="rounded-xl border border-gray-200 bg-white p-3 shadow-sm dark:border-gray-700 dark:bg-gray-800"
              >
                <h3 class="px-1 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300">
                  {label}
                </h3>
                <ol role="list" class="mt-1">
                  <For each={props.leaders[key]}>
                    {(entry, i) => (
                      <li class="flex min-h-[44px] items-center gap-2 px-1 text-sm">
                        <span class="w-4 flex-none text-xs font-semibold tabular-nums text-gray-600 dark:text-gray-300">
                          {i() + 1}
                        </span>
                        <PlayerLink
                          slug={entry.player.slug}
                          from={from()}
                          class="flex min-h-[44px] min-w-0 flex-1 items-center gap-2 rounded-lg hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 active:bg-gray-100"
                        >
                          <Avatar
                            src={entry.player.profile_pic_url}
                            name={entry.player.full_name}
                            size="h-8 w-8"
                          />
                          <span class="min-w-0 break-words font-medium text-gray-800 dark:text-gray-200">
                            {entry.player.full_name}
                          </span>
                        </PlayerLink>
                        <b class="flex-none tabular-nums text-gray-900 dark:text-white">
                          {entry.value}
                        </b>
                      </li>
                    )}
                  </For>
                </ol>
              </div>
            )}
          </For>
        </div>
      </section>
    </Show>
  );
};

export default Leaders;
