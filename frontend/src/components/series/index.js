import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { arrowUpRight } from "solid-heroicons/solid";
import { For, Match, Show, Switch } from "solid-js";

import { fetchSeasons } from "../../queries";
import { displayDate } from "../../utils";

const SeriesCard = props => {
  return (
    <A href={`/series/${props.series?.slug}`}>
      <div class="mt-4 rounded-lg border border-gray-300 px-4 py-4 shadow-sm transition-all hover:cursor-pointer hover:shadow-md">
        <div class="flex items-center justify-between">
          <h4 class="text-lg font-bold text-gray-600">{props.series.name}</h4>
          <span>
            <Icon
              path={arrowUpRight}
              class="h-5 w-5 text-gray-700"
              stroke-width="10"
            />
          </span>
        </div>
        <div>
          <span class="inline-block">
            {displayDate(props.series.start_date)}
          </span>
          {"  "}
          to{"  "}
          <span class="inline-block">{displayDate(props.series.end_date)}</span>
        </div>
        <div class="mb-1 mt-4 space-x-2">
          <span class="rounded-md border border-blue-300 bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-300">
            {props.series.category}
          </span>
          <Switch>
            <Match when={props.series.type === "Mixed"}>
              <span class="rounded-md border border-yellow-300 bg-yellow-100 px-3 py-1 text-sm font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
                Mixed
              </span>
            </Match>
            <Match when={props.series.type === "Opens"}>
              <span class="rounded-md border border-green-300 bg-green-100 px-3 py-1 text-sm font-medium text-green-800 dark:bg-green-900 dark:text-green-300">
                Opens
              </span>
            </Match>
            <Match when={props.series.type === "Womens"}>
              <span class="rounded-md border border-purple-300 bg-purple-100 px-3 py-1 text-sm font-medium text-purple-800 dark:bg-purple-900 dark:text-purple-300">
                Womens
              </span>
            </Match>
          </Switch>
        </div>
      </div>
    </A>
  );
};

const AllSeries = () => {
  const seasonsQuery = createQuery(() => ["seasons"], fetchSeasons);

  return (
    <div class="mx-auto max-w-4xl">
      <h1 class="mt-2 select-none px-2 sm:px-0 sm:text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-3xl font-extrabold text-transparent">
          Series
        </span>
      </h1>

      <div class="mt-6 select-none lg:mt-10">
        <For each={seasonsQuery.data}>
          {season => (
            <Show when={season?.series?.length !== 0}>
              <details open class="group mb-4 open:mb-8">
                <summary class="custom mt-2 rounded-lg border border-gray-400/50 bg-gray-50 px-4 py-3 transition-all group-open:bg-gray-200">
                  <h3 class="text-lg font-bold text-gray-700">
                    {season?.name}
                  </h3>
                </summary>
                <For each={season?.series}>
                  {series => <SeriesCard series={series} />}
                </For>
              </details>
            </Show>
          )}
        </For>
      </div>
    </div>
  );
};

export default AllSeries;
