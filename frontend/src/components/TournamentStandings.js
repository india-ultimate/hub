import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { trophy } from "solid-heroicons/solid";
import { createEffect, createMemo, createSignal, For, Show } from "solid-js";

import { matchCardColors, matchCardColorToBorderColorMap } from "../colors";
import {
  fetchBracketsBySlug,
  fetchCrossPoolBySlug,
  fetchMatchesBySlug,
  fetchPoolsBySlug,
  fetchPositionPoolsBySlug,
  fetchSwissRoundsBySlug,
  fetchTournamentBySlug
} from "../queries";
import { getTournamentBreadcrumbName } from "../utils";
import { getMatchCardColor } from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import MatchCard from "./match/MatchCard";
import PillTabs from "./tabs/PillTabs";
import VerticalTabs from "./tabs/VerticalTabs";

const TournamentStandings = () => {
  const params = useParams();
  const [teamsMap, setTeamsMap] = createSignal({});
  const [poolsMap, setPoolsMap] = createSignal({});
  const [positionPoolsMap, setPositionPoolsMap] = createSignal({});
  const [activeStage, setActiveStage] = createSignal(null);
  const [activeSwissGroup, setActiveSwissGroup] = createSignal(null);
  const [activeBracketTab, setActiveBracketTab] = createSignal(null);

  const tournamentQuery = createQuery(
    () => ["tournaments", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
  const matchesQuery = createQuery(
    () => ["matches", params.slug],
    () => fetchMatchesBySlug(params.slug)
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
  const swissRoundsQuery = createQuery(
    () => ["swiss-rounds", params.slug],
    () => fetchSwissRoundsBySlug(params.slug)
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

  const allQueriesSettled = () =>
    swissRoundsQuery.isSuccess &&
    poolsQuery.isSuccess &&
    crossPoolQuery.isSuccess &&
    bracketQuery.isSuccess &&
    matchesQuery.isSuccess;

  const stageTabs = createMemo(() => {
    const tabs = [];
    if (swissRoundsQuery.data?.length > 0)
      tabs.push({ id: "swiss", label: "Swiss" });
    if (poolsQuery.data?.length > 0) tabs.push({ id: "pools", label: "Pools" });
    if (crossPoolQuery.isSuccess && !crossPoolQuery.data?.message)
      tabs.push({ id: "cross-pool", label: "Cross Pool" });
    if (bracketQuery.data?.length > 0)
      tabs.push({ id: "brackets", label: "Brackets" });
    return tabs;
  });

  const inferActiveStage = () => {
    // Select the most advanced stage that has actual progress
    // Priority (highest to lowest): brackets > cross-pool > pools > swiss

    // Brackets: check if any bracket has been generated (initial_seeding with valid team ids)
    if (bracketQuery.data?.length > 0) {
      const anyGenerated = bracketQuery.data.some(
        b =>
          Object.keys(b.initial_seeding || {}).length > 0 &&
          b.initial_seeding[Object.keys(b.initial_seeding)[0]] > 0
      );
      if (anyGenerated) return "brackets";
    }

    // Cross Pool: has seeding data
    if (
      crossPoolQuery.isSuccess &&
      !crossPoolQuery.data?.message &&
      Object.keys(crossPoolQuery.data?.initial_seeding || {}).length > 0
    ) {
      return "cross-pool";
    }

    // Pools
    if (poolsQuery.data?.length > 0) return "pools";

    // Swiss (default)
    if (swissRoundsQuery.data?.length > 0) return "swiss";

    return null;
  };

  createEffect(() => {
    // Wait for all queries to settle before selecting the default tab
    if (!allQueriesSettled()) return;
    const tabs = stageTabs();
    if (tabs.length > 0 && activeStage() === null) {
      const inferred = inferActiveStage();
      const match = tabs.find(t => t.id === inferred);
      setActiveStage(match ? match.id : tabs[0].id);
    }
  });

  createEffect(() => {
    if (swissRoundsQuery.data?.length > 0 && activeSwissGroup() === null) {
      setActiveSwissGroup(swissRoundsQuery.data[0].name);
    }
  });

  const swissGroupTabs = createMemo(() => {
    if (!swissRoundsQuery.data) return [];
    return swissRoundsQuery.data.map(sr => ({
      id: sr.name,
      label: `Swiss ${sr.name}`
    }));
  });

  const activeSwissRound = createMemo(() => {
    if (!swissRoundsQuery.data) return null;
    return swissRoundsQuery.data.find(sr => sr.name === activeSwissGroup());
  });

  const bracketAndPoolTabs = createMemo(() => {
    const tabs = [];
    if (bracketQuery.data?.length > 0) {
      bracketQuery.data.forEach(b => {
        tabs.push({ id: `bracket-${b.name}`, label: `Bracket ${b.name}` });
      });
    }
    Object.keys(positionPoolsMap()).forEach(name => {
      tabs.push({ id: `pool-${name}`, label: `Position Pool ${name}` });
    });
    return tabs;
  });

  const activeBracketData = createMemo(() => {
    const tab = activeBracketTab();
    if (!tab?.startsWith("bracket-") || !bracketQuery.data) return null;
    const name = tab.replace("bracket-", "");
    return bracketQuery.data.find(b => b.name === name);
  });

  const activePoolName = createMemo(() => {
    const tab = activeBracketTab();
    if (!tab?.startsWith("pool-")) return null;
    return tab.replace("pool-", "");
  });

  createEffect(() => {
    const tabs = bracketAndPoolTabs();
    if (tabs.length > 0 && activeBracketTab() === null) {
      setActiveBracketTab(tabs[0].id);
    }
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

      <PillTabs
        tabs={stageTabs()}
        activeTab={activeStage}
        onTabChange={setActiveStage}
      />

      <Show
        when={activeStage() === "swiss" && swissRoundsQuery.data?.length > 0}
      >
        <div class="rounded-lg p-4">
          <Show
            when={swissGroupTabs().length > 1}
            fallback={
              <SwissGroupContent
                swissRound={activeSwissRound()}
                teamsMap={teamsMap}
                params={params}
                matchesQuery={matchesQuery}
                tournamentType={tournamentQuery.data?.event?.type}
                useUCRegistrations={tournamentQuery.data?.use_uc_registrations}
              />
            }
          >
            <VerticalTabs
              tabs={swissGroupTabs()}
              activeTab={activeSwissGroup}
              onTabChange={setActiveSwissGroup}
            >
              <Show when={activeSwissRound()}>
                <SwissGroupContent
                  swissRound={activeSwissRound()}
                  teamsMap={teamsMap}
                  params={params}
                  matchesQuery={matchesQuery}
                  tournamentType={tournamentQuery.data?.event?.type}
                  useUCRegistrations={
                    tournamentQuery.data?.use_uc_registrations
                  }
                />
              </Show>
            </VerticalTabs>
          </Show>
          <p class="mt-2 text-center text-xs text-gray-500 dark:text-gray-400">
            Pts = Win(2) + Draw(1). OS = sum of opponents' points (higher =
            faced stronger opponents). Tiebreaker: Pts &gt; H2H &gt; OS &gt; GD.
          </p>
        </div>
      </Show>

      <Show when={activeStage() === "pools" && poolsQuery.data?.length > 0}>
        <div class="rounded-lg p-4">
          <For each={Object.keys(poolsMap())}>
            {poolName => (
              <div class="mb-8">
                <h2 class="mb-2 text-center text-lg font-semibold">
                  Pool {poolName}
                </h2>
                <div class="relative my-3 overflow-x-auto rounded-lg shadow-lg">
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
                <Show when={matchesQuery.isSuccess}>
                  <div class="mt-4">
                    <h3 class="mb-2 text-center text-sm font-semibold text-gray-700 dark:text-gray-200">
                      Pool {poolName} matches
                    </h3>
                    <div class="space-y-3">
                      <For
                        each={matchesQuery.data?.filter(
                          m => m.pool && m.pool.name === poolName
                        )}
                      >
                        {match => (
                          <div
                            id={match.id}
                            class={`mb-3 block w-full rounded-lg border bg-white px-1 py-2 shadow dark:bg-gray-800 ${
                              matchCardColorToBorderColorMap[
                                getMatchCardColor(match)
                              ]
                            }`}
                          >
                            <MatchCard
                              match={match}
                              tournamentSlug={params.slug}
                              tournamentType={tournamentQuery.data?.event?.type}
                              useUCRegistrations={
                                tournamentQuery.data?.use_uc_registrations
                              }
                              bothTeamsClickable
                              compact
                            />
                          </div>
                        )}
                      </For>
                    </div>
                  </div>
                </Show>
              </div>
            )}
          </For>
        </div>
      </Show>

      <Show
        when={activeStage() === "cross-pool" && !crossPoolQuery.data?.message}
      >
        <div class="rounded-lg p-4">
          <Show
            when={
              Object.keys(crossPoolQuery.data?.initial_seeding || {}).length > 0
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
            <Show when={matchesQuery.isSuccess}>
              <div class="mt-6">
                <h3 class="mb-2 text-center text-sm font-semibold text-gray-700 dark:text-gray-200">
                  Cross Pool matches
                </h3>
                <div class="space-y-3">
                  <For
                    each={matchesQuery.data?.filter(
                      m => m.cross_pool?.id === crossPoolQuery.data?.id
                    )}
                  >
                    {match => (
                      <div
                        id={match.id}
                        class={`mb-3 block w-full rounded-lg border bg-white px-1 py-2 shadow dark:bg-gray-800 ${
                          matchCardColorToBorderColorMap[
                            getMatchCardColor(match)
                          ]
                        }`}
                      >
                        <MatchCard
                          match={match}
                          tournamentSlug={params.slug}
                          tournamentType={tournamentQuery.data?.event?.type}
                          useUCRegistrations={
                            tournamentQuery.data?.use_uc_registrations
                          }
                          bothTeamsClickable
                          compact
                        />
                      </div>
                    )}
                  </For>
                </div>
              </div>
            </Show>
          </Show>
        </div>
      </Show>

      <Show
        when={activeStage() === "brackets" && bracketQuery.data?.length > 0}
      >
        <div class="rounded-lg p-4">
          <Show
            when={bracketAndPoolTabs().length > 1}
            fallback={
              <>
                <Show when={activeBracketData()}>
                  <BracketContent
                    bracket={activeBracketData()}
                    teamsMap={teamsMap}
                    params={params}
                    getTeamImage={getTeamImage}
                    matchesQuery={matchesQuery}
                    tournamentType={tournamentQuery.data?.event?.type}
                    useUCRegistrations={
                      tournamentQuery.data?.use_uc_registrations
                    }
                  />
                </Show>
                <Show when={activePoolName()}>
                  <PositionPoolContent
                    poolName={activePoolName()}
                    results={positionPoolsMap()[activePoolName()]}
                    teamsMap={teamsMap}
                    params={params}
                    matchesQuery={matchesQuery}
                    tournamentType={tournamentQuery.data?.event?.type}
                    useUCRegistrations={
                      tournamentQuery.data?.use_uc_registrations
                    }
                  />
                </Show>
              </>
            }
          >
            <VerticalTabs
              tabs={bracketAndPoolTabs()}
              activeTab={activeBracketTab}
              onTabChange={setActiveBracketTab}
            >
              <Show when={activeBracketData()}>
                <BracketContent
                  bracket={activeBracketData()}
                  teamsMap={teamsMap}
                  params={params}
                  getTeamImage={getTeamImage}
                  matchesQuery={matchesQuery}
                  tournamentType={tournamentQuery.data?.event?.type}
                  useUCRegistrations={
                    tournamentQuery.data?.use_uc_registrations
                  }
                />
              </Show>
              <Show when={activePoolName()}>
                <PositionPoolContent
                  poolName={activePoolName()}
                  results={positionPoolsMap()[activePoolName()]}
                  teamsMap={teamsMap}
                  params={params}
                  matchesQuery={matchesQuery}
                  tournamentType={tournamentQuery.data?.event?.type}
                  useUCRegistrations={
                    tournamentQuery.data?.use_uc_registrations
                  }
                />
              </Show>
            </VerticalTabs>
          </Show>
        </div>
      </Show>
    </Show>
  );
};

const SwissGroupContent = props => {
  const allRoundsComplete = () =>
    props.swissRound.current_round > props.swissRound.num_rounds;

  const [selectedRound, setSelectedRound] = createSignal(null);

  // Default to "final" when all rounds are complete
  createEffect(() => {
    if (allRoundsComplete() && selectedRound() === null) {
      setSelectedRound("final");
    }
  });

  const displayResults = () => {
    const round = selectedRound();
    if (round === "final") {
      return props.swissRound.results;
    }
    if (
      round !== null &&
      props.swissRound.round_results &&
      props.swissRound.round_results[String(round)]
    ) {
      return props.swissRound.round_results[String(round)];
    }
    return props.swissRound.results;
  };

  const completedRounds = () => {
    if (!props.swissRound.round_results) return [];
    return Object.keys(props.swissRound.round_results)
      .map(Number)
      .sort((a, b) => a - b);
  };

  return (
    <div class="mb-6">
      <h2 class="mb-3 text-center text-lg font-bold text-blue-600 dark:text-blue-500">
        Swiss {props.swissRound.name}
      </h2>
      <p class="mb-2 text-center text-sm">
        Round {props.swissRound.current_round}/{props.swissRound.num_rounds}
      </p>
      <Show when={completedRounds().length > 0}>
        <div class="mb-3 flex flex-wrap justify-center gap-1">
          <For each={completedRounds()}>
            {round => (
              <button
                class={`rounded-full px-3 py-1 text-xs font-medium ${
                  selectedRound() === round
                    ? "bg-blue-600 text-white"
                    : "bg-gray-200 text-gray-700 dark:bg-gray-600 dark:text-gray-300"
                }`}
                onClick={() => setSelectedRound(round)}
              >
                R{round}
              </button>
            )}
          </For>
          <Show when={!allRoundsComplete()}>
            <button
              class={`rounded-full px-3 py-1 text-xs font-medium ${
                selectedRound() === null
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-700 dark:bg-gray-600 dark:text-gray-300"
              }`}
              onClick={() => setSelectedRound(null)}
            >
              R{props.swissRound.current_round} (Current)
            </button>
          </Show>
          <Show when={allRoundsComplete()}>
            <button
              class={`rounded-full px-3 py-1 text-xs font-medium ${
                selectedRound() === "final"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-700 dark:bg-gray-600 dark:text-gray-300"
              }`}
              onClick={() => setSelectedRound("final")}
            >
              Final
            </button>
          </Show>
        </div>
      </Show>
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
                Pts
              </th>
              <th scope="col" class="px-4 py-3">
                W
              </th>
              <th scope="col" class="px-4 py-3">
                L
              </th>
              <th scope="col" class="px-4 py-3">
                D
              </th>
              <th scope="col" class="px-4 py-3">
                OS
              </th>
              <th scope="col" class="px-4 py-3">
                GD
              </th>
            </tr>
          </thead>
          <tbody>
            <For
              each={Object.entries(displayResults() || {})
                .map(([team_id, stats]) => ({
                  ...stats,
                  team_id
                }))
                .sort((a, b) => parseInt(a.rank) - parseInt(b.rank))}
            >
              {result => (
                <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                  <td class="px-4 py-4">{result.rank}</td>
                  <td class="px-4 py-4">
                    <A
                      href={`/tournament/${props.params.slug}/team/${
                        props.teamsMap()[result.team_id]?.slug
                      }`}
                    >
                      {props.teamsMap()[result.team_id]?.name}
                    </A>
                  </td>
                  <td class="px-4 py-4">
                    {result.wins * 2 + (result.draws || 0)}
                  </td>
                  <td class="px-4 py-4">{result.wins}</td>
                  <td class="px-4 py-4">{result.losses}</td>
                  <td class="px-4 py-4">{result.draws || 0}</td>
                  <td class="px-4 py-4">{result.opp_strength || 0}</td>
                  <td class="px-4 py-4">
                    {parseInt(result["GF"]) - parseInt(result["GA"])}
                  </td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>
      <Show when={props.matchesQuery?.isSuccess && selectedRound() !== "final"}>
        <div class="mt-6">
          <h3 class="mb-2 text-center text-sm font-semibold text-gray-700 dark:text-gray-200">
            Swiss {props.swissRound.name} — Round{" "}
            {selectedRound() ?? props.swissRound.current_round} Matches
          </h3>
          <div class="mt-3 space-y-3">
            <Show
              when={
                props.swissRound.byes &&
                props.swissRound.byes[
                  String(selectedRound() ?? props.swissRound.current_round)
                ]
              }
            >
              {() => {
                const round = () =>
                  selectedRound() ?? props.swissRound.current_round;
                const teamId = () => props.swissRound.byes[String(round())];
                const groupColors = () => {
                  const swissGroups = matchCardColors["swiss_round"];
                  return swissGroups[
                    (props.swissRound.sequence_number - 1) % swissGroups.length
                  ];
                };
                const byeColor = () =>
                  groupColors()[(round() - 1) % groupColors().length];
                return (
                  <div
                    class={`mb-3 block w-full rounded-lg border bg-white px-4 py-3 shadow dark:bg-gray-800 ${
                      matchCardColorToBorderColorMap[byeColor()]
                    }`}
                  >
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-3">
                        <span class="text-xs font-medium uppercase text-gray-400 dark:text-gray-500">
                          Bye
                        </span>
                        <A
                          href={`/tournament/${props.params.slug}/team/${
                            props.teamsMap()[teamId()]?.slug
                          }`}
                          class="font-semibold text-gray-800 dark:text-gray-200"
                        >
                          {props.teamsMap()[teamId()]?.name ||
                            `Team ${teamId()}`}
                        </A>
                      </div>
                      <span class="font-bold text-green-600 dark:text-green-400">
                        15 - 0
                      </span>
                    </div>
                  </div>
                );
              }}
            </Show>
            <For
              each={props.matchesQuery.data?.filter(
                m =>
                  m.swiss_round?.id === props.swissRound.id &&
                  m.sequence_number ===
                    (selectedRound() ?? props.swissRound.current_round)
              )}
            >
              {match => (
                <div
                  id={match.id}
                  class={`mb-3 block w-full rounded-lg border bg-white px-1 py-2 shadow dark:bg-gray-800 ${
                    matchCardColorToBorderColorMap[getMatchCardColor(match)]
                  }`}
                >
                  <MatchCard
                    match={match}
                    tournamentSlug={props.params.slug}
                    tournamentType={props.tournamentType}
                    useUCRegistrations={props.useUCRegistrations}
                    bothTeamsClickable
                    compact
                  />
                </div>
              )}
            </For>
          </div>
        </div>
      </Show>
    </div>
  );
};

const BracketContent = props => {
  return (
    <div>
      <h2 class="mt-4 text-center text-lg font-bold text-blue-600 dark:text-blue-500">
        Bracket {props.bracket.name}
      </h2>
      <Show
        when={
          Object.keys(props.bracket.initial_seeding || {}).length > 0 &&
          props.bracket.initial_seeding[
            Object.keys(props.bracket.initial_seeding)[0]
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
              <For each={Object.entries(props.bracket.initial_seeding || {})}>
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
                          src={props.getTeamImage(props.teamsMap()[team_id])}
                          alt="Bordered avatar"
                        />
                        <A
                          href={`/tournament/${props.params.slug}/team/${
                            props.teamsMap()[team_id]?.slug
                          }`}
                        >
                          {props.teamsMap()[team_id]?.name}
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
              <For each={Object.entries(props.bracket.current_seeding || {})}>
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
                          src={props.getTeamImage(props.teamsMap()[team_id])}
                          alt="Bordered avatar"
                        />
                        <A
                          href={`/tournament/${props.params.slug}/team/${
                            props.teamsMap()[team_id]?.slug
                          }`}
                        >
                          {props.teamsMap()[team_id]?.name}
                        </A>
                      </td>
                    </Show>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </div>
        <Show when={props.matchesQuery?.isSuccess}>
          <div class="mt-6">
            <h3 class="mb-2 text-center text-sm font-semibold text-gray-700 dark:text-gray-200">
              Bracket {props.bracket.name} matches
            </h3>
            <div class="space-y-3">
              <For
                each={props.matchesQuery.data?.filter(
                  m => m.bracket?.id === props.bracket.id
                )}
              >
                {match => (
                  <div
                    id={match.id}
                    class={`mb-3 block w-full rounded-lg border bg-white px-1 py-2 shadow dark:bg-gray-800 ${
                      matchCardColorToBorderColorMap[getMatchCardColor(match)]
                    }`}
                  >
                    <MatchCard
                      match={match}
                      tournamentSlug={props.params.slug}
                      tournamentType={props.tournamentType}
                      useUCRegistrations={props.useUCRegistrations}
                      bothTeamsClickable
                      compact
                    />
                  </div>
                )}
              </For>
            </div>
          </div>
        </Show>
      </Show>
    </div>
  );
};

const PositionPoolContent = props => {
  return (
    <div>
      <h2 class="mb-2 text-center text-lg font-semibold">
        Position Pool {props.poolName}
      </h2>
      <div class="relative my-3 overflow-x-auto rounded-lg shadow-lg">
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
            <For each={props.results}>
              {result => (
                <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                  <td class="px-4 py-4">{result.seed}</td>
                  <td class="px-4 py-4">
                    <A
                      href={`/tournament/${props.params.slug}/team/${
                        props.teamsMap()[result.team_id]?.slug
                      }`}
                    >
                      {props.teamsMap()[result.team_id]?.name}
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
      <Show when={props.matchesQuery?.isSuccess}>
        <div class="mt-4">
          <h3 class="mb-2 text-center text-sm font-semibold text-gray-700 dark:text-gray-200">
            Position Pool {props.poolName} matches
          </h3>
          <div class="space-y-3">
            <For
              each={props.matchesQuery.data?.filter(
                m => m.position_pool && m.position_pool.name === props.poolName
              )}
            >
              {match => (
                <div
                  id={match.id}
                  class={`mb-3 block w-full rounded-lg border bg-white px-1 py-2 shadow dark:bg-gray-800 ${
                    matchCardColorToBorderColorMap[getMatchCardColor(match)]
                  }`}
                >
                  <MatchCard
                    match={match}
                    tournamentSlug={props.params.slug}
                    tournamentType={props.tournamentType}
                    useUCRegistrations={props.useUCRegistrations}
                    bothTeamsClickable
                    compact
                  />
                </div>
              )}
            </For>
          </div>
        </div>
      </Show>
    </div>
  );
};

export default TournamentStandings;
