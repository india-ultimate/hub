import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { trophy } from "solid-heroicons/solid";
import { For, onMount, Show } from "solid-js";

import {
  fetchPlayerAssists,
  fetchPlayerScores,
  fetchTournamentBySlug
} from "../../../queries";
import { getTournamentBreadcrumbName } from "../../../utils";
import Breadcrumbs from "../../Breadcrumbs";

const TournamentStandings = () => {
  const params = useParams();

  const tournamentQuery = createQuery(
    () => ["tournaments", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );

  const playerScoresQuery = createQuery(
    () => ["tournaments", params.slug, "scores"],
    () => fetchPlayerScores(params.slug)
  );

  const playerAssistsQuery = createQuery(
    () => ["tournaments", params.slug, "assists"],
    () => fetchPlayerAssists(params.slug)
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
          Scoreboard
        </span>
      </h1>
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
              id={"tab-scores"}
              data-tabs-target={"#scores"}
              type="button"
              role="tab"
              aria-controls={"scores"}
              aria-selected="true"
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
        </ul>
      </div>
      <div id="myTabContent">
        <div
          class="hidden rounded-lg p-4"
          id={"scores"}
          role="tabpanel"
          aria-labelledby={"tab-scores"}
        >
          <div class="relative my-5 overflow-x-auto rounded-lg shadow-lg">
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
                    GLS
                  </th>
                </tr>
              </thead>
              <tbody>
                <For each={playerScoresQuery.data}>
                  {player => (
                    <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                      <td class="px-4 py-3 font-semibold">{`${player?.first_name.trim()} ${player?.last_name.trim()}`}</td>
                      <td class="px-4 py-3">{player?.team_name}</td>
                      <td class="px-4 py-3">{player?.num_scores}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
        </div>
        <div
          class="hidden rounded-lg p-4"
          id={"assists"}
          role="tabpanel"
          aria-labelledby={"tab-assists"}
        >
          <div class="relative my-5 overflow-x-auto rounded-lg shadow-lg">
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
                    AST
                  </th>
                </tr>
              </thead>
              <tbody>
                <For each={playerAssistsQuery.data}>
                  {player => (
                    <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                      <td class="px-4 py-3 font-semibold">{`${player?.first_name.trim()} ${player?.last_name.trim()}`}</td>
                      <td class="px-4 py-3">{player?.team_name}</td>
                      <td class="px-4 py-3">{player?.num_assists}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Show>
  );
};

export default TournamentStandings;
