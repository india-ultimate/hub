import { A, useParams } from "@solidjs/router";
import { createEffect, createSignal, For, Show } from "solid-js";
import { createQuery } from "@tanstack/solid-query";
import {
  fetchBracketsBySlug,
  fetchCrossPoolBySlug,
  fetchPoolsBySlug,
  fetchPositionPoolsBySlug,
  fetchTeams,
  fetchTournamentBySlug
} from "../queries";
import { trophy } from "solid-heroicons/solid";
import Breadcrumbs from "./Breadcrumbs";

const TournamentStandings = () => {
  const params = useParams();
  const [teamsMap, setTeamsMap] = createSignal({});
  const [poolsMap, setPoolsMap] = createSignal({});
  const [positionPoolsMap, setPositionPoolsMap] = createSignal({});

  const tournamentQuery = createQuery(
    () => ["tournament", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
  const teamsQuery = createQuery(() => ["teams"], fetchTeams);
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
    if (teamsQuery.status === "success") {
      let newTeamsMap = {};
      teamsQuery.data.map(team => {
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
            name: tournamentQuery.data?.event?.ultimate_central_slug
              ?.split("-")
              .splice(-2)
              .map(word => word[0].toUpperCase() + word.slice(1))
              .join(" ")
          }
        ]}
      />
      <h1 class="text-center mb-5">
        <span class="font-extrabold text-transparent text-2xl bg-clip-text bg-gradient-to-r from-blue-500 to-green-500 w-fit">
          Standings
        </span>
      </h1>
      <div class="mb-4 border-b border-gray-200 dark:border-gray-700">
        <ul
          class="flex flex-wrap -mb-px text-sm font-medium text-center justify-center"
          id="myTab"
          data-tabs-toggle="#myTabContent"
          role="tablist"
        >
          <li class="mr-2" role="presentation">
            <button
              class="inline-block p-4 border-b-2 rounded-t-lg"
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
                class="inline-block p-4 border-b-2 rounded-t-lg"
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
              class="inline-block p-4 border-b-2 rounded-t-lg"
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
          class="hidden p-4 rounded-lg"
          id={"pools"}
          role="tabpanel"
          aria-labelledby={"tab-pools"}
        >
          <For each={Object.keys(poolsMap())}>
            {poolName => (
              <div>
                <h2 class="text-center text-lg">Pool {poolName}</h2>

                <div class="relative overflow-x-auto shadow-lg rounded-lg my-5">
                  <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
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
                          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                            <td class="px-4 py-4">{result.seed}</td>
                            <td class="px-4 py-4">
                              {teamsMap()[result.team_id]?.name}
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
            class="hidden p-4 rounded-lg"
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
              <h2 class="text-center mt-5 text-xl font-bold">
                Initial Standings
              </h2>
              <div class="relative overflow-x-auto shadow-md rounded-lg mt-5">
                <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                  <tbody>
                    <For
                      each={Object.entries(
                        crossPoolQuery.data?.initial_seeding || {}
                      )}
                    >
                      {([rank, team_id]) => (
                        <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                          <th
                            scope="row"
                            class="pr-6 pl-10 py-4 whitespace-nowrap font-normal"
                          >
                            {rank}
                          </th>
                          <td class="px-6 py-4">
                            <img
                              class="w-8 h-8 p-1 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 inline-block mr-3"
                              src={teamsMap()[team_id]?.image_url}
                              alt="Bordered avatar"
                            />
                            {teamsMap()[team_id]?.name}
                          </td>
                        </tr>
                      )}
                    </For>
                  </tbody>
                </table>
              </div>
              <h2 class="text-center mt-5 text-xl font-bold">
                Current Standings
              </h2>
              <div class="relative overflow-x-auto shadow-md rounded-lg mt-5">
                <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                  <tbody>
                    <For
                      each={Object.entries(
                        crossPoolQuery.data?.current_seeding || {}
                      )}
                    >
                      {([rank, team_id]) => (
                        <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                          <th
                            scope="row"
                            class="pr-6 pl-10 py-4 whitespace-nowrap font-normal"
                          >
                            {rank}
                          </th>
                          <td class="px-6 py-4">
                            <img
                              class="w-8 h-8 p-1 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 inline-block mr-3"
                              src={teamsMap()[team_id]?.image_url}
                              alt="Bordered avatar"
                            />
                            {teamsMap()[team_id]?.name}
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
          class="hidden p-4 rounded-lg"
          id={"brackets"}
          role="tabpanel"
          aria-labelledby={"tab-brackets"}
        >
          <For each={bracketQuery.data}>
            {bracket => (
              <div>
                <h2 class="text-center text-lg">Bracket {bracket.name}</h2>
                <Show
                  when={Object.keys(bracket.initial_seeding || {}).length > 0}
                  fallback={
                    <p class="text-sm text-center">
                      This Bracket is not generated yet!
                    </p>
                  }
                >
                  <h2 class="text-center mt-5 text-xl font-bold">
                    Initial Standings
                  </h2>
                  <div class="relative overflow-x-auto shadow-md rounded-lg mt-5">
                    <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                      <tbody>
                        <For
                          each={Object.entries(bracket.initial_seeding || {})}
                        >
                          {([rank, team_id]) => (
                            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                              <th
                                scope="row"
                                class="pr-6 pl-10 py-4 whitespace-nowrap font-normal"
                              >
                                {rank}
                              </th>
                              <Show when={team_id > 0}>
                                <td class="px-6 py-4">
                                  <img
                                    class="w-8 h-8 p-1 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 inline-block mr-3"
                                    src={teamsMap()[team_id]?.image_url}
                                    alt="Bordered avatar"
                                  />
                                  {teamsMap()[team_id]?.name}
                                </td>
                              </Show>
                            </tr>
                          )}
                        </For>
                      </tbody>
                    </table>
                  </div>
                  <h2 class="text-center mt-5 text-xl font-bold">
                    Current Standings
                  </h2>
                  <div class="relative overflow-x-auto shadow-md rounded-lg mt-5">
                    <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                      <tbody>
                        <For
                          each={Object.entries(bracket.current_seeding || {})}
                        >
                          {([rank, team_id]) => (
                            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                              <th
                                scope="row"
                                class="pr-6 pl-10 py-4 whitespace-nowrap font-normal"
                              >
                                {rank}
                              </th>
                              <Show when={team_id > 0}>
                                <td class="px-6 py-4">
                                  <img
                                    class="w-8 h-8 p-1 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 inline-block mr-3"
                                    src={teamsMap()[team_id]?.image_url}
                                    alt="Bordered avatar"
                                  />
                                  {teamsMap()[team_id]?.name}
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

                <div class="relative overflow-x-auto shadow-lg rounded-lg my-5">
                  <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
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
                          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                            <td class="px-4 py-4">{result.seed}</td>
                            <td class="px-4 py-4">
                              {teamsMap()[result.team_id]?.name}
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
