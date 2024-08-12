import { Icon } from "solid-heroicons";
import { trash } from "solid-heroicons/solid";
import { For, Show } from "solid-js";

import {
  annualMembershipFee,
  sponsoredAnnualMembershipFee
} from "../../constants";

const MembershipPlayerList = props => {
  return (
    <div>
      <div class="relative my-4 overflow-x-auto">
        <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
          <caption class="bg-white py-2 text-left text-lg font-semibold text-blue-500 rtl:text-right dark:bg-gray-800 dark:text-white">
            Selected Players
            <p class="mt-1 text-sm font-normal text-gray-500 dark:text-gray-400">
              List of players for whom membership is being paid
            </p>
          </caption>
          <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
            <tr>
              <th scope="col" class="px-6 py-3">
                Player
              </th>
              <th scope="col" class="px-6 py-3">
                Fee
              </th>
              <th scope="col" class="px-2 py-3">
                Delete
              </th>
            </tr>
          </thead>
          <tbody>
            <Show when={props.players.length === 0}>
              <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                <td colspan={3} class="text-center italic">
                  No Players Selected
                </td>
              </tr>
            </Show>
            <For each={props.players}>
              {player => (
                <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                  <th
                    scope="row"
                    class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
                  >
                    {player.full_name} {player.is_minor ? "*" : ""}
                  </th>
                  <td class="px-6 py-4">
                    ₹
                    {player?.sponsored
                      ? sponsoredAnnualMembershipFee / 100
                      : annualMembershipFee / 100}
                  </td>
                  <td>
                    <button
                      class="flex w-full justify-center rounded-full text-center text-sm font-medium text-red-700"
                      onClick={() =>
                        props.onPlayerPayingStatusChange(player, false)
                      }
                    >
                      <Icon
                        path={trash}
                        style={{ width: "20px", display: "inline" }}
                      />
                    </button>
                  </td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>
      <p class="mt-8">
        Paying India Ultimate membership fee for {props.players.length} players
        (₹
        {props.fee}) valid for the period from {props.startDate} to{" "}
        {props.endDate}
      </p>
    </div>
  );
};
export default MembershipPlayerList;
