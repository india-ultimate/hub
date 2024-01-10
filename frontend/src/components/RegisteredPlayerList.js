import { Icon } from "solid-heroicons";
import {
  checkBadge,
  magnifyingGlass,
  xCircle
} from "solid-heroicons/solid-mini";
import { createSignal, For, Match, Switch } from "solid-js";
import { onMount } from "solid-js";

import { Spinner } from "../icons";
import { useStore } from "../store";
import { fetchUrl, playerMatches } from "../utils";

const RegisteredPlayerList = () => {
  const [store] = useStore();
  const [players, setPlayers] = createSignal([]);
  const [loading, setLoading] = createSignal(false);
  const [searchText, setSearchText] = createSignal("");

  const playersSuccessHandler = async response => {
    const data = await response.json();
    setLoading(false);
    if (response.ok) {
      setPlayers(data);
    } else {
      console.log(data);
    }
  };

  onMount(() => {
    console.log("Fetching players info...");
    setLoading(true);
    // FIXME: Paginate
    fetchUrl("/api/players?full_schema=1", playersSuccessHandler, error => {
      console.log(error);
      setLoading(false);
    });
  });

  return (
    <div id="accordion-collapse" data-accordion="collapse">
      <h2
        class="text-4xl font-bold text-blue-500"
        id="accordion-collapse-heading-1"
      >
        Registered Players{" "}
        {players()?.length > 0 ? `(${players().length})` : ""}
      </h2>
      <div class="my-4 border border-gray-200 p-5 dark:border-gray-700 dark:bg-gray-900">
        <div class="relative overflow-x-auto">
          <Switch>
            <Match when={loading()}>
              <Spinner />
            </Match>
            <Match when={!store.data.is_staff}>
              <p>You are not an admin!</p>
            </Match>
            <Match when={!loading()}>
              <div class="p-3">
                <label for="input-group-search" class="sr-only">
                  Search
                </label>
                <div class="relative">
                  <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <Icon path={magnifyingGlass} style={{ width: "24px" }} />
                  </div>
                  <input
                    type="text"
                    id="input-group-search"
                    class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2 pl-10 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-500 dark:bg-gray-600 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
                    placeholder="Search player"
                    onChange={e => setSearchText(e.target.value)}
                  />
                </div>
              </div>

              <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                  <tr>
                    <th scope="col" class="px-6 py-3">
                      Player
                    </th>
                    <th scope="col" class="px-6 py-3">
                      Team
                    </th>
                    <th scope="col" class="px-6 py-3">
                      City
                    </th>
                    <th scope="col" class="px-6 py-3">
                      Active Membership
                    </th>
                    <th scope="col" class="px-6 py-3">
                      UC ID
                    </th>
                    <th scope="col" class="px-6 py-3">
                      Vaccinated
                    </th>
                    <th scope="col" class="px-6 py-3">
                      Waiver signed
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <For
                    each={
                      searchText()
                        ? players().filter(p => playerMatches(p, searchText()))
                        : players()
                    }
                  >
                    {player => (
                      <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                        <th
                          scope="row"
                          class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
                        >
                          {player.full_name}
                        </th>
                        <td class="px-6 py-4">
                          {player.teams.map(team => team["name"]).join(", ")}
                        </td>
                        <td class="px-6 py-4">{player.city}</td>
                        <td class="px-6 py-4">
                          {
                            <Icon
                              path={
                                player?.membership?.is_active
                                  ? checkBadge
                                  : xCircle
                              }
                              style={{ width: "20px" }}
                              class={
                                player?.membership?.is_active
                                  ? "text-green-600 dark:text-green-500"
                                  : "text-red-600 dark:text-red-500"
                              }
                            />
                          }
                        </td>
                        <td class="px-6 py-4">{player?.ultimate_central_id}</td>
                        <td class="px-6 py-4">
                          {
                            <Icon
                              path={
                                player?.vaccination?.is_vaccinated
                                  ? checkBadge
                                  : xCircle
                              }
                              style={{ width: "20px" }}
                              class={
                                player?.vaccination?.is_vaccinated
                                  ? "text-green-600 dark:text-green-500"
                                  : "text-red-600 dark:text-red-500"
                              }
                            />
                          }
                        </td>
                        <td class="px-6 py-4">
                          {
                            <Icon
                              path={
                                player?.membership?.waiver_valid
                                  ? checkBadge
                                  : xCircle
                              }
                              style={{ width: "20px" }}
                              class={
                                player?.membership?.waiver_valid
                                  ? "text-green-600 dark:text-green-500"
                                  : "text-red-600 dark:text-red-500"
                              }
                            />
                          }
                        </td>
                      </tr>
                    )}
                  </For>
                </tbody>
              </table>
            </Match>
          </Switch>
        </div>
      </div>
    </div>
  );
};
export default RegisteredPlayerList;
