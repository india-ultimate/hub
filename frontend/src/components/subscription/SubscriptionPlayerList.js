import { Icon } from "solid-heroicons";
import { trash } from "solid-heroicons/solid";
import { For, Match, Show, Switch } from "solid-js";

import { inr } from "../../money";
import { Bar } from "../../skeletons/primitives";

// "Community Subscription" reads as "Community" under a Tier heading.
const tierWord = name => name?.replace(/ Subscription$/, "");

const SubscriptionPlayerList = props => {
  const pending = player => props.pricesPending || props.pendingFor(player.id);

  return (
    <div>
      <div class="relative my-4 overflow-x-auto">
        <table
          aria-busy={props.totalPending}
          class="w-full text-left text-sm text-gray-500 dark:text-gray-400"
        >
          <caption class="bg-white py-2 text-left text-lg font-semibold text-blue-500 dark:bg-gray-800 dark:text-white rtl:text-right">
            Selected Players
            <p class="mt-1 text-sm font-normal text-gray-500 dark:text-gray-400">
              List of players for whom subscription is being paid
            </p>
          </caption>
          <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
            <tr>
              <th scope="col" class="px-3 py-3 sm:px-6">
                Player
              </th>
              <th scope="col" class="px-3 py-3 sm:px-6">
                Tier
              </th>
              <th scope="col" class="px-3 py-3 sm:px-6">
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
                    class="whitespace-nowrap px-3 py-4 font-medium text-gray-900 dark:text-white sm:px-6"
                  >
                    {player.full_name} {player.is_minor ? "*" : ""}
                  </th>
                  <td class="px-3 py-4 sm:px-6">
                    <Switch>
                      <Match when={pending(player)}>
                        <Bar class="h-9 w-full" />
                      </Match>
                      <Match when={props.pricesFailed}>
                        <span class="text-sm text-gray-700 dark:text-gray-300">
                          Price not loaded
                        </span>
                      </Match>
                      <Match when={props.plansFor(player.id).length === 0}>
                        <span class="text-sm text-gray-700 dark:text-gray-300">
                          {props.heldFor(player.id)
                            ? `Holds ${props.heldFor(
                                player.id
                              )}; there is no higher tier`
                            : "No tier is on sale to them"}
                        </span>
                      </Match>
                      <Match when={true}>
                        <select
                          aria-label={`Tier for ${player.full_name}`}
                          aria-describedby={
                            props.planFor(player.id)?.kind === "upgrade"
                              ? `upgrade-note-${player.id}`
                              : undefined
                          }
                          class="block min-h-11 w-full min-w-[8.5rem] rounded-lg border border-gray-300 bg-gray-50 p-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
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
                                selected={
                                  plan.slug === props.tierFor(player.id)
                                }
                              >
                                {tierWord(plan.name)}
                              </option>
                            )}
                          </For>
                        </select>
                        <Show
                          when={props.planFor(player.id)?.kind === "upgrade"}
                        >
                          <p
                            id={`upgrade-note-${player.id}`}
                            class="mt-1 text-xs font-medium text-blue-700 dark:text-blue-400"
                          >
                            Upgrade from {tierWord(props.heldFor(player.id))}
                          </p>
                        </Show>
                      </Match>
                    </Switch>
                  </td>
                  {/* The server's price for the chosen tier, never one this
                      page worked out. */}
                  <td class="whitespace-nowrap px-3 py-4 sm:px-6">
                    <Switch>
                      <Match when={pending(player)}>
                        <Bar class="inline-block h-4 w-14" />
                      </Match>
                      <Match when={props.pricesFailed}>—</Match>
                      <Match when={!props.planFor(player.id)}>
                        <span class="text-gray-500 dark:text-gray-400">
                          No charge
                        </span>
                      </Match>
                      <Match when={true}>
                        <span class="font-medium text-gray-900 dark:text-white">
                          {inr(props.planFor(player.id).amount)}
                        </span>
                        <Show
                          when={props.planFor(player.id).kind === "upgrade"}
                        >
                          <span class="block text-xs text-gray-500 dark:text-gray-400">
                            Upgrade
                          </span>
                        </Show>
                      </Match>
                    </Switch>
                  </td>
                  <td>
                    <button
                      aria-label={`Remove ${player.full_name}`}
                      class="flex min-h-11 w-full min-w-11 items-center justify-center rounded-full text-center text-sm font-medium text-red-700 dark:text-red-400"
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
      <p class="mt-1">
        Players being charged:{" "}
        <Switch>
          <Match when={props.pricesFailed}>—</Match>
          <Match when={props.totalPending}>
            <Bar class="inline-block h-4 w-6 align-middle" />
          </Match>
          <Match when={true}>{props.count}</Match>
        </Switch>
      </p>
      <p class="mt-1">
        Validity: {props.startDate} to {props.endDate}
      </p>
      <p class="mt-1 font-extrabold">
        Total Amount:{" "}
        <Switch>
          <Match when={props.pricesFailed}>—</Match>
          <Match when={props.totalPending}>
            <Bar class="inline-block h-4 w-14 align-middle" />
          </Match>
          <Match when={true}>{inr(props.fee)}</Match>
        </Switch>
      </p>
    </div>
  );
};
export default SubscriptionPlayerList;
