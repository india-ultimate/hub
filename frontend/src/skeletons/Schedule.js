import { For } from "solid-js";

import { Bar, Loading } from "./primitives";

const DaySchedule = () => (
  <Loading label="Loading schedule" class="relative mb-8 overflow-x-auto">
    <div class="grid grid-cols-4 bg-gray-50 py-3 dark:bg-gray-700">
      <For each={[0, 1, 2, 3]}>
        {() => (
          <div class="flex justify-center px-2">
            <Bar class="h-4 w-12" />
          </div>
        )}
      </For>
    </div>
    <For each={[0, 1, 2, 3, 4, 5]}>
      {() => (
        <div class="grid grid-cols-4 items-center border-b bg-white py-4 dark:border-gray-700 dark:bg-gray-800">
          <div class="flex justify-center px-2">
            <Bar class="h-2.5 w-10 !rounded-full" />
          </div>
          <For each={[0, 1, 2]}>
            {() => (
              <div class="px-2">
                <Bar class="h-8 w-full" />
              </div>
            )}
          </For>
        </div>
      )}
    </For>
  </Loading>
);

export default DaySchedule;
