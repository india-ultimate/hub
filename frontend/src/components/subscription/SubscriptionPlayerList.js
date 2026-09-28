import { Icon } from "solid-heroicons";
import { trash } from "solid-heroicons/solid";
import { For, Show } from "solid-js";

const SubscriptionPlayerList = props => {
  return (
    <div>
      <div class="relative my-4 overflow-x-auto">
        <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
          <caption class="bg-white py-2 text-left text-lg font-semibold text-blue-500 rtl:text-right dark:bg-gray-800 dark:text-white">
            Selected Players
            <p class="mt-1 text-sm font-normal text-gray-500 dark:text-gray-400">
              List of players for whom subscription is being paid
            </p>
          </caption>
          <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
            <tr>
              <th scope="col" class="px-6 py-3">
                Player
              </th>
              <th scope="col" class="px-6 py-3">
                Tier
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
                <td colspan={4} class="text-center italic">
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
                    <select
                      class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      value={props.tierFor(player.id)}
                      onChange={e =>
                        props.onTierChange(player.id, e.target.value)
                      }
                    >
                      <For each={props.plansFor(player.id)}>
                        {/* `selected`, not just the select's `value`: Solid
                            sets that value before these options exist, so
                            the browser would show the first tier instead. */}
                        {plan => (
                          <option
                            value={plan.slug}
                            selected={plan.slug === props.tierFor(player.id)}
                          >
                            {plan.name}
                          </option>
                        )}
                      </For>
                    </select>
                  </td>
                  {/* The server's price for the chosen tier, never one this
                      page worked out. */}
                  <td class="px-6 py-4">
                    ₹{" "}
                    {(
                      (props.planFor(player.id)?.amount ?? 0) / 100
                    ).toLocaleString("en-IN")}
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
      <p class="mt-8 font-bold">Paying India Ultimate subscription fee:</p>
      <p class="mt-1">Number of players: {props.players.length}</p>
      <p class="mt-1">
        Validity: {props.startDate} to {props.endDate}
      </p>
      <p class="mt-1 font-extrabold">Total Amount: ₹{props.fee}</p>
    </div>
  );
};
export default SubscriptionPlayerList;
