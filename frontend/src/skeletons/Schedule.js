import { For } from "solid-js";
const DaySchedule = () => {
  return (
    <div>
      <div class="relative mb-8 overflow-x-auto">
        <table class="w-full table-fixed text-left text-sm text-gray-500 dark:text-gray-400">
          <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
            <tr>
              <th scope="col" class="px-2 py-3 text-center">
                Time
              </th>
              <For each={new Array(3)}>
                {(
                  field,
                  id // eslint-disable-line no-unused-vars
                ) => (
                  <th scope="col" class="px-1 py-3 text-center">
                    Field {id() + 1}
                  </th>
                )}
              </For>
            </tr>
          </thead>
          <tbody>
            <For each={new Array(6)}>
              {(
                time // eslint-disable-line no-unused-vars
              ) => (
                <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                  <th scope="row" class="whitespace-nowrap px-2 py-4">
                    {/* match time */}
                    <div class="flex animate-pulse justify-center">
                      <div class="h-2.5 w-10 place-self-center rounded-full bg-gray-400 dark:bg-gray-600" />
                    </div>
                  </th>
                  <For each={new Array(3)}>
                    {(
                      field //eslint-disable-line no-unused-vars
                    ) => (
                      // match card
                      <td class="px-2 py-4">
                        <div class="flex h-8 w-full animate-pulse flex-wrap justify-center rounded bg-gray-400 px-2.5 py-2.5 dark:bg-gray-600" />
                      </td>
                    )}
                  </For>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default DaySchedule;
