import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { trophy } from "solid-heroicons/solid";
import { createEffect, createSignal, For, onMount, Show } from "solid-js";

import {
  fetchBracketsBySlug,
  fetchCrossPoolBySlug,
  fetchPoolsBySlug,
  fetchPositionPoolsBySlug,
  fetchTournamentBySlug
} from "../queries";
import { getTournamentBreadcrumbName } from "../utils";
import Breadcrumbs from "./Breadcrumbs";

const TournamentStandings = () => {
  const params = useParams();
  const [teamsMap, setTeamsMap] = createSignal({});
  const [poolsMap, setPoolsMap] = createSignal({});
  const [positionPoolsMap, setPositionPoolsMap] = createSignal({});

  const tournamentQuery = createQuery(
    () => ["tournaments", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
  const poolsQuery = createQuery(
    () => ["pools", params.slug],
    () => fetchPoolsBySlug(params.slug)
  );
  const crossPoolQuery = createQuery(
    () => ["cross-pool", params.slug],
    () => fetchCrossPoolBySlug(params.slug)
  );
  const bracketQuery = createQuery(
    () => ["brackets", params.slug],
    () => fetchBracketsBySlug(params.slug)
  );
  const postionPoolsQuery = createQuery(
    () => ["position-pools", params.slug],
    () => fetchPositionPoolsBySlug(params.slug)
  );

  createEffect(() => {
    if (tournamentQuery.status === "success" && !tournamentQuery.data.message) {
      let newTeamsMap = {};
      tournamentQuery.data?.teams.map(team => {
        newTeamsMap[team.id] = team;
      });
      setTeamsMap(newTeamsMap);
    }
  });

  createEffect(() => {
    if (poolsQuery.status === "success") {
      let newPoolsMap = {};
      poolsQuery.data.map(pool => {
        let results = pool.results;
        Object.keys(results).map(
          team_id => (results[team_id]["team_id"] = team_id)
        );
        results = Object.values(results);
        results.sort((a, b) => parseInt(a.rank) - parseInt(b.rank));

        const seeds_in_pool = Object.keys(pool.initial_seeding).sort(
          (a, b) => parseInt(a) - parseInt(b)
        );

        results.map((result, i) => (result["seed"] = seeds_in_pool[i]));

        newPoolsMap[pool.name] = results;
      });

      setPoolsMap(newPoolsMap);
    }
  });

  createEffect(() => {
    if (postionPoolsQuery.status === "success") {
      let newPoolsMap = {};
      postionPoolsQuery.data.map(pool => {
        let results = pool.results;
        Object.keys(results).map(
          team_id => (results[team_id]["team_id"] = team_id)
        );
        results = Object.values(results);
        results.sort((a, b) => parseInt(a.rank) - parseInt(b.rank));

        const seeds_in_pool = Object.keys(pool.initial_seeding).sort(
          (a, b) => parseInt(a) - parseInt(b)
        );

        results.map((result, i) => (result["seed"] = seeds_in_pool[i]));

        newPoolsMap[pool.name] = results;
      });

      setPositionPoolsMap(newPoolsMap);
    }
  });

  onMount(() => {
    setTimeout(() => initFlowbite(), 100);
    setTimeout(() => initFlowbite(), 500);
    setTimeout(() => initFlowbite(), 1000);
    setTimeout(() => initFlowbite(), 3000);
    setTimeout(() => initFlowbite(), 5000);
    setTimeout(() => initFlowbite(), 8000);
  });

  const getTeamImage = team => {
    return team?.image ?? team?.image_url;
  };

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
          Standings
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
              id={"tab-pools"}
              data-tabs-target={"#pools"}
              type="button"
              role="tab"
              aria-controls={"pools"}
              aria-selected="false"
            >
              Pools
            </button>
          </li>
          <Show when={!crossPoolQuery.data?.message}>
            <li class="mr-2" role="presentation">
              <button
                class="inline-block rounded-t-lg border-b-2 p-4"
                id={"tab-cross-pool"}
                data-tabs-target={"#cross-pool"}
                type="button"
                role="tab"
                aria-controls={"cross-pool"}
                aria-selected="false"
              >
                Cross Pool
              </button>
            </li>
          </Show>

          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 p-4"
              id={"tab-brackets"}
              data-tabs-target={"#brackets"}
              type="button"
              role="tab"
              aria-controls={"brackets"}
              aria-selected="false"
            >
              Brackets
            </button>
          </li>
        </ul>
      </div>
      <div id="myTabContent">
        <div
          class="hidden rounded-lg p-4"
          id={"pools"}
          role="tabpanel"
          aria-labelledby={"tab-pools"}
        >
          <For each={Object.keys(poolsMap())}>
            {poolName => (
              <div>
                <h2 class="text-center text-lg">Pool {poolName}</h2>

                <div class="relative my-5 overflow-x-auto rounded-lg shadow-lg">
                  <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                    <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                      <tr>
                        <th scope="col" class="px-4 py-3">
                          Seed
                        </th>
                        <th scope="col" class="px-4 py-3">
                          Team
                        </th>
                        <th scope="col" class="px-4 py-3">
                          W
                        </th>
                        <th scope="col" class="px-4 py-3">
                          L
                        </th>
                        <th scope="col" class="px-4 py-3">
                          GD
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <For each={poolsMap()[poolName]}>
                        {result => (
                          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                            <td class="px-4 py-4">{result.seed}</td>
                            <td class="px-4 py-4">
                              <A
                                href={`/tournament/${params.slug}/team/${
                                  teamsMap()[result.team_id]?.slug
                                }`}
                              >
                                {teamsMap()[result.team_id]?.name}
                              </A>
                            </td>
                            <td class="px-4 py-4">{result.wins}</td>
                            <td class="px-4 py-4">{result.losses}</td>
                            <td class="px-4 py-4">
                              {parseInt(result["GF"]) - parseInt(result["GA"])}
                            </td>
                          </tr>
                        )}
                      </For>
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </For>
        </div>
        <Show when={!crossPoolQuery.data?.message}>
          <div
            class="hidden rounded-lg p-4"
            id={"cross-pool"}
            role="tabpanel"
            aria-labelledby={"tab-cross-pool"}
          >
            <Show
              when={
                Object.keys(crossPoolQuery.data?.initial_seeding || {}).length >
                0
              }
              fallback={
                <p>Cross Pool stage in the tournament is not reached yet!</p>
              }
            >
              <h2 class="mt-5 text-center text-xl font-bold">
                Initial Standings
              </h2>
              <div class="relative mt-5 overflow-x-auto rounded-lg shadow-md">
                <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                  <tbody>
                    <For
                      each={Object.entries(
                        crossPoolQuery.data?.initial_seeding || {}
                      )}
                    >
                      {([rank, team_id]) => (
                        <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                          <th
                            scope="row"
                            class="whitespace-nowrap py-4 pl-10 pr-6 font-normal"
                          >
                            {rank}
                          </th>
                          <td class="px-6 py-4">
                            <img
                              class="mr-3 inline-block h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                              src={getTeamImage(teamsMap()[team_id])}
                              alt="Bordered avatar"
                            />
                            <A
                              href={`/tournament/${params.slug}/team/${
                                teamsMap()[team_id]?.slug
                              }`}
                            >
                              {teamsMap()[team_id]?.name}
                            </A>
                          </td>
                        </tr>
                      )}
                    </For>
                  </tbody>
                </table>
              </div>
              <h2 class="mt-5 text-center text-xl font-bold">
                Current Standings
              </h2>
              <div class="relative mt-5 overflow-x-auto rounded-lg shadow-md">
                <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                  <tbody>
                    <For
                      each={Object.entries(
                        crossPoolQuery.data?.current_seeding || {}
                      )}
                    >
                      {([rank, team_id]) => (
                        <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                          <th
                            scope="row"
                            class="whitespace-nowrap py-4 pl-10 pr-6 font-normal"
                          >
                            {rank}
                          </th>
                          <td class="px-6 py-4">
                            <img
                              class="mr-3 inline-block h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                              src={getTeamImage(teamsMap()[team_id])}
                              alt="Bordered avatar"
                            />
                            <A
                              href={`/tournament/${params.slug}/team/${
                                teamsMap()[team_id]?.slug
                              }`}
                            >
                              {teamsMap()[team_id]?.name}
                            </A>
                          </td>
                        </tr>
                      )}
                    </For>
                  </tbody>
                </table>
              </div>
            </Show>
          </div>
        </Show>
        <div
          class="hidden rounded-lg p-4"
          id={"brackets"}
          role="tabpanel"
          aria-labelledby={"tab-brackets"}
        >
          <For each={bracketQuery.data}>
            {bracket => (
              <div>
                <h2 class="mt-4 text-center text-lg font-bold text-blue-600 dark:text-blue-500">
                  Bracket {bracket.name}
                </h2>
                <Show
                  when={
                    Object.keys(bracket.initial_seeding || {}).length > 0 &&
                    bracket.initial_seeding[
                      Object.keys(bracket.initial_seeding)[0]
                    ] > 0
                  }
                  fallback={
                    <p class="my-5 text-center text-sm">
                      This Bracket is not generated yet!
                    </p>
                  }
                >
                  <h2 class="mt-5 text-center text-lg">Initial Standings</h2>
                  <div class="relative mt-5 overflow-x-auto rounded-lg shadow-md">
                    <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                      <tbody>
                        <For
                          each={Object.entries(bracket.initial_seeding || {})}
                        >
                          {([rank, team_id]) => (
                            <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                              <th
                                scope="row"
                                class="whitespace-nowrap py-4 pl-10 pr-6 font-normal"
                              >
                                {rank}
                              </th>
                              <Show when={team_id > 0}>
                                <td class="px-6 py-4">
                                  <img
                                    class="mr-3 inline-block h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                                    src={getTeamImage(teamsMap()[team_id])}
                                    alt="Bordered avatar"
                                  />
                                  <A
                                    href={`/tournament/${params.slug}/team/${
                                      teamsMap()[team_id]?.slug
                                    }`}
                                  >
                                    {teamsMap()[team_id]?.name}
                                  </A>
                                </td>
                              </Show>
                            </tr>
                          )}
                        </For>
                      </tbody>
                    </table>
                  </div>
                  <h2 class="mt-5 text-center text-lg">Current Standings</h2>
                  <div class="relative mt-5 overflow-x-auto rounded-lg shadow-md">
                    <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                      <tbody>
                        <For
                          each={Object.entries(bracket.current_seeding || {})}
                        >
                          {([rank, team_id]) => (
                            <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                              <th
                                scope="row"
                                class="whitespace-nowrap py-4 pl-10 pr-6 font-normal"
                              >
                                {rank}
                              </th>
                              <Show when={team_id > 0}>
                                <td class="px-6 py-4">
                                  <img
                                    class="mr-3 inline-block h-8 w-8 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                                    src={getTeamImage(teamsMap()[team_id])}
                                    alt="Bordered avatar"
                                  />
                                  <A
                                    href={`/tournament/${params.slug}/team/${
                                      teamsMap()[team_id]?.slug
                                    }`}
                                  >
                                    {teamsMap()[team_id]?.name}
                                  </A>
                                </td>
                              </Show>
                            </tr>
                          )}
                        </For>
                      </tbody>
                    </table>
                  </div>
                </Show>
              </div>
            )}
          </For>
          <For each={Object.keys(positionPoolsMap())}>
            {poolName => (
              <div class="mt-5">
                <h2 class="text-center text-lg">Position Pool {poolName}</h2>

                <div class="relative my-5 overflow-x-auto rounded-lg shadow-lg">
                  <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                    <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                      <tr>
                        <th scope="col" class="px-4 py-3">
                          Seed
                        </th>
                        <th scope="col" class="px-4 py-3">
                          Team
                        </th>
                        <th scope="col" class="px-4 py-3">
                          W
                        </th>
                        <th scope="col" class="px-4 py-3">
                          L
                        </th>
                        <th scope="col" class="px-4 py-3">
                          GD
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <For each={positionPoolsMap()[poolName]}>
                        {result => (
                          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                            <td class="px-4 py-4">{result.seed}</td>
                            <td class="px-4 py-4">
                              <A
                                href={`/tournament/${params.slug}/team/${
                                  teamsMap()[result.team_id]?.slug
                                }`}
                              >
                                {teamsMap()[result.team_id]?.name}
                              </A>
                            </td>
                            <td class="px-4 py-4">{result.wins}</td>
                            <td class="px-4 py-4">{result.losses}</td>
                            <td class="px-4 py-4">
                              {parseInt(result["GF"]) - parseInt(result["GA"])}
                            </td>
                          </tr>
                        )}
                      </For>
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </For>
        </div>
      </div>
    </Show>
  );
};

export default TournamentStandings;
