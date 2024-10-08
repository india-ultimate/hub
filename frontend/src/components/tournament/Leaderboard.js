import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { trophy } from "solid-heroicons/solid";
import { createSignal, For, onMount, Show } from "solid-js";

import {
  fetchTournamentBySlug,
  fetchTournamentLeaderboard
} from "../../queries";
import { getTournamentBreadcrumbName } from "../../utils";
import Breadcrumbs from "../Breadcrumbs";

const TournamentStandings = () => {
  const params = useParams();
  const [selectedTeam, setSelectedTeam] = createSignal("all");
  const [selectedGender, setSelectedGender] = createSignal("all");

  const tournamentQuery = createQuery(
    () => ["tournaments", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );

  const tournamentLeaderboardQuery = createQuery(
    () => ["tournaments", params.slug, "leaderboard"],
    () => fetchTournamentLeaderboard(params.slug)
  );

  onMount(() => {
    setTimeout(() => initFlowbite(), 100);
    setTimeout(() => initFlowbite(), 500);
    setTimeout(() => initFlowbite(), 1000);
    setTimeout(() => initFlowbite(), 3000);
    setTimeout(() => initFlowbite(), 5000);
    setTimeout(() => initFlowbite(), 8000);
  });

  return (
    <Show
      when={!tournamentQuery.data?.message}
      fallback={
        <div>
          Tournament could not be fetched. Error -{" "}
          {tournamentQuery.data.message}
          <A href={"/tournaments"} class="text-blue-600 dark:text-blue-500">
            <br />
            Back to Tournaments Page
          </A>
        </div>
      }
    >
      <Breadcrumbs
        icon={trophy}
        pageList={[
          { url: "/tournaments", name: "All Tournaments" },
          {
            url: `/tournament/${params.slug}`,
            name: getTournamentBreadcrumbName(
              tournamentQuery.data?.event?.slug || ""
            )
          }
        ]}
      />
      <h1 class="mb-5 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-2xl font-extrabold text-transparent">
          Leaderboard
        </span>
      </h1>
      <div class="grid w-full grid-cols-12 gap-2">
        <div class="col-span-8">
          <select
            id="teams"
            onChange={e => setSelectedTeam(e.target.value)}
            class=" block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          >
            <option selected value="all">
              All Teams
            </option>
            <For each={tournamentQuery.data?.teams}>
              {team => <option value={team.name}>{team.name}</option>}
            </For>
          </select>
        </div>
        <div class="col-span-4">
          <select
            id="gender"
            onChange={e => setSelectedGender(e.target.value)}
            class=" col-span-2 block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          >
            <option selected value="all">
              M/F
            </option>
            <option value="M">M</option>
            <option value="F">F</option>
          </select>
        </div>
      </div>

      <div class="mb-4 border-b border-gray-200 dark:border-gray-700">
        <ul
          class="-mb-px flex flex-wrap justify-center text-center text-sm font-medium"
          id="myTab"
          data-tabs-toggle="#myTabContent"
          role="tablist"
        >
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 p-4"
              id={"tab-total"}
              data-tabs-target={"#total"}
              type="button"
              role="tab"
              aria-controls={"total"}
              aria-selected="true"
            >
              Total
            </button>
          </li>
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 p-4"
              id={"tab-scores"}
              data-tabs-target={"#scores"}
              type="button"
              role="tab"
              aria-controls={"scores"}
              aria-selected="false"
            >
              Scores
            </button>
          </li>
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 p-4"
              id={"tab-assists"}
              data-tabs-target={"#assists"}
              type="button"
              role="tab"
              aria-controls={"assists"}
              aria-selected="false"
            >
              Assists
            </button>
          </li>
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 p-4"
              id={"tab-blocks"}
              data-tabs-target={"#blocks"}
              type="button"
              role="tab"
              aria-controls={"blocks"}
              aria-selected="false"
            >
              Blocks
            </button>
          </li>
        </ul>
      </div>
      <div id="myTabContent">
        <div
          class="hidden rounded-lg"
          id={"total"}
          role="tabpanel"
          aria-labelledby={"tab-total"}
        >
          <div class="relative overflow-x-auto rounded-lg shadow-lg">
            <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
              <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th scope="col" class="px-4 py-3">
                    Player
                  </th>
                  <th scope="col" class="px-4 py-3">
                    Team
                  </th>
                  <th scope="col" class="px-4 py-3">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody>
                <For
                  each={tournamentLeaderboardQuery.data?.total
                    ?.filter(
                      player =>
                        player?.team_name === selectedTeam() ||
                        selectedTeam() === "all"
                    )
                    .filter(
                      player =>
                        player?.gender === selectedGender() ||
                        selectedGender() === "all"
                    )}
                >
                  {player => (
                    <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                      <td class="px-4 py-3 font-semibold">{`${player?.first_name.trim()} ${player?.last_name.trim()} (${
                        player?.gender
                      })`}</td>
                      <td class="px-4 py-3">{player?.team_name}</td>
                      <td class="px-4 py-3">{player?.num_total}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
            <Show when={tournamentLeaderboardQuery.data?.total?.length === 0}>
              <div class="w-full py-2 text-center text-sm italic">
                No Players To Show
              </div>
            </Show>
          </div>
        </div>
        <div
          class="hidden rounded-lg"
          id={"scores"}
          role="tabpanel"
          aria-labelledby={"tab-scores"}
        >
          <div class="relative overflow-x-auto rounded-lg shadow-lg">
            <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
              <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th scope="col" class="px-4 py-3">
                    Player
                  </th>
                  <th scope="col" class="px-4 py-3">
                    Team
                  </th>
                  <th scope="col" class="px-4 py-3">
                    Goals
                  </th>
                </tr>
              </thead>
              <tbody>
                <For
                  each={tournamentLeaderboardQuery.data?.scores
                    ?.filter(
                      player =>
                        player?.team_name === selectedTeam() ||
                        selectedTeam() === "all"
                    )
                    .filter(
                      player =>
                        player?.gender === selectedGender() ||
                        selectedGender() === "all"
                    )}
                >
                  {player => (
                    <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                      <td class="px-4 py-3 font-semibold">{`${player?.first_name.trim()} ${player?.last_name.trim()} (${
                        player?.gender
                      })`}</td>
                      <td class="px-4 py-3">{player?.team_name}</td>
                      <td class="px-4 py-3">{player?.num_scores}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
            <Show when={tournamentLeaderboardQuery.data?.scores?.length === 0}>
              <div class="w-full py-2 text-center text-sm italic">
                No Players To Show
              </div>
            </Show>
          </div>
        </div>
        <div
          class="hidden rounded-lg"
          id={"assists"}
          role="tabpanel"
          aria-labelledby={"tab-assists"}
        >
          <div class="relative overflow-x-auto rounded-lg shadow-lg">
            <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
              <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th scope="col" class="px-4 py-3">
                    Player
                  </th>
                  <th scope="col" class="px-4 py-3">
                    Team
                  </th>
                  <th scope="col" class="px-4 py-3">
                    Assists
                  </th>
                </tr>
              </thead>
              <tbody>
                <For
                  each={tournamentLeaderboardQuery.data?.assists
                    ?.filter(
                      player =>
                        player?.team_name === selectedTeam() ||
                        selectedTeam() === "all"
                    )
                    .filter(
                      player =>
                        player?.gender === selectedGender() ||
                        selectedGender() === "all"
                    )}
                >
                  {player => (
                    <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                      <td class="px-4 py-3 font-semibold">{`${player?.first_name.trim()} ${player?.last_name.trim()} (${
                        player?.gender
                      })`}</td>
                      <td class="px-4 py-3">{player?.team_name}</td>
                      <td class="px-4 py-3">{player?.num_assists}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
            <Show when={tournamentLeaderboardQuery.data?.assists?.length === 0}>
              <div class="w-full py-2 text-center text-sm italic">
                No Players To Show
              </div>
            </Show>
          </div>
        </div>
        <div
          class="hidden rounded-lg"
          id={"blocks"}
          role="tabpanel"
          aria-labelledby={"tab-blocks"}
        >
          <div class="relative overflow-x-auto rounded-lg shadow-lg">
            <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
              <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th scope="col" class="px-4 py-3">
                    Player
                  </th>
                  <th scope="col" class="px-4 py-3">
                    Team
                  </th>
                  <th scope="col" class="px-4 py-3">
                    Blocks
                  </th>
                </tr>
              </thead>
              <tbody>
                <For
                  each={tournamentLeaderboardQuery.data?.blocks
                    ?.filter(
                      player =>
                        player?.team_name === selectedTeam() ||
                        selectedTeam() === "all"
                    )
                    .filter(
                      player =>
                        player?.gender === selectedGender() ||
                        selectedGender() === "all"
                    )}
                >
                  {player => (
                    <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                      <td class="px-4 py-3 font-semibold">{`${player?.first_name.trim()} ${player?.last_name.trim()} (${
                        player?.gender
                      })`}</td>
                      <td class="px-4 py-3">{player?.team_name}</td>
                      <td class="px-4 py-3">{player?.num_blocks}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
            <Show when={tournamentLeaderboardQuery.data?.blocks?.length === 0}>
              <div class="w-full py-2 text-center text-sm italic">
                No Players To Show
              </div>
            </Show>
          </div>
        </div>
      </div>
    </Show>
  );
};

export default TournamentStandings;
