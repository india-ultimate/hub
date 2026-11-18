import { For } from "solid-js";

import { Bar, Circle, Loading } from "./primitives";

const rows = [0, 1, 2, 3, 4, 5];

const Standings = () => (
  <Loading label="Loading standings">
    <For each={rows}>
      {() => (
        <div class="border-b bg-white py-5 pl-6 pr-6 dark:border-gray-700 dark:bg-gray-800">
          <Bar class="h-6 w-full !rounded-md" />
        </div>
      )}
    </For>
  </Loading>
);

const SpiritStandings = () => (
  <Loading
    label="Loading standings"
    class="relative overflow-x-auto rounded-lg shadow-md"
  >
    <For each={rows}>
      {() => (
        <div class="flex items-center border-b bg-white px-3 py-4 dark:border-gray-700 dark:bg-gray-800">
          <Bar class="h-2.5 w-6 !rounded-full" />
          <Circle class="ml-6 mr-3 h-8 w-8" />
          <Bar class="h-2.5 w-24 !rounded-full" />
          <Bar class="ml-auto h-2.5 w-6 !rounded-full" />
        </div>
      )}
    </For>
  </Loading>
);

export { SpiritStandings, Standings };
