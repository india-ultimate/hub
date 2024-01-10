import { For } from "solid-js";
const Standings = () => {
  return (
    <For each={new Array(6)}>
      {/* eslint-disable-next-line no-unused-vars */}
      {_ => (
        <div class="border-b bg-white py-5 pl-6 pr-6 dark:border-gray-700 dark:bg-gray-800">
          <div class="h-6 w-full animate-pulse self-center rounded-md bg-gray-400 dark:bg-gray-700/50" />
        </div>
      )}
    </For>
  );
};

const SpiritStandings = () => {
  return (
    <div class="relative overflow-x-auto rounded-lg shadow-md">
      <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
        <tbody>
          <For each={new Array(6)}>
            {/* eslint-disable-next-line no-unused-vars */}
            {_ => (
              <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                <th
                  scope="row"
                  class="whitespace-nowrap px-3 py-4 font-normal "
                >
                  <div class="h-2.5 w-6 animate-pulse  self-center rounded-full bg-gray-300 dark:bg-gray-700" />
                </th>
                <td class="px-3 py-4">
                  <div class="flex animate-pulse justify-start">
                    <div class="mr-3 h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500" />
                    <div class="h-2.5 w-24 self-center rounded-full bg-gray-300 dark:bg-gray-700" />
                  </div>
                </td>
                <td class="px-3 py-4 ">
                  <div class="h-2.5 w-6  self-center rounded-full bg-gray-300 dark:bg-gray-700" />
                </td>
              </tr>
            )}
          </For>
        </tbody>
      </table>
    </div>
  );
};

export { SpiritStandings, Standings };
