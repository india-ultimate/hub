import { A, useParams, useSearchParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { chevronRight, trophy } from "solid-heroicons/solid";
import { createMemo, For, Show } from "solid-js";

import { PlayerLink, useRestoreScroll } from "../../playerLinks";
import {
  fetchTournamentBySlug,
  fetchTournamentLeaderboard
} from "../../queries";
import { getTournamentBreadcrumbName } from "../../utils";
import Breadcrumbs from "../Breadcrumbs";
import PillTabs from "../tabs/PillTabs";

const TABS = [
  { id: "total", label: "Total", column: "Total", field: "num_total" },
  { id: "scores", label: "Scores", column: "Goals", field: "num_scores" },
  { id: "assists", label: "Assists", column: "Ast", field: "num_assists" },
  { id: "blocks", label: "Blocks", column: "Blk", field: "num_blocks" }
];

const TournamentStandings = () => {
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const setParam = (key, value, fallback) =>
    setSearchParams(
      { [key]: value === fallback ? undefined : value },
      { replace: true }
    );
  const activeTab = () =>
    TABS.some(t => t.id === searchParams.tab) ? searchParams.tab : "total";
  const activeTabConfig = () => TABS.find(t => t.id === activeTab());
  const selectedTeam = () => searchParams.team || "all";
  const selectedGender = () => searchParams.gender || "all";

  const tournamentQuery = createQuery(
    () => ["tournaments", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );

  const tournamentLeaderboardQuery = createQuery(
    () => ["tournaments", params.slug, "leaderboard"],
    () => fetchTournamentLeaderboard(params.slug)
  );

  useRestoreScroll(() => tournamentLeaderboardQuery.isSuccess);

  const rows = () =>
    (tournamentLeaderboardQuery.data?.[activeTab()] ?? [])
      .filter(p => selectedTeam() === "all" || p?.team_name === selectedTeam())
      .filter(
        p => selectedGender() === "all" || p?.gender === selectedGender()
      );
  const ranks = createMemo(() => {
    const field = activeTabConfig().field;
    const list = rows();
    return list.map(
      p => list.findIndex(q => (q?.[field] ?? 0) === (p?.[field] ?? 0)) + 1
    );
  });

  const from = () => ({
    label: `${tournamentQuery.data?.event?.title} · Leaderboard`,
    tournamentSlug: params.slug
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
            onChange={e => setParam("team", e.target.value, "all")}
            class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          >
            <option selected={selectedTeam() === "all"} value="all">
              All Teams
            </option>
            <For each={tournamentQuery.data?.teams}>
              {team => (
                <option
                  selected={selectedTeam() === team.name}
                  value={team.name}
                >
                  {team.name}
                </option>
              )}
            </For>
          </select>
        </div>
        <div class="col-span-4">
          <select
            id="gender"
            onChange={e => setParam("gender", e.target.value, "all")}
            class="col-span-2 block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          >
            <option selected={selectedGender() === "all"} value="all">
              M/F
            </option>
            <option selected={selectedGender() === "M"} value="M">
              M
            </option>
            <option selected={selectedGender() === "F"} value="F">
              F
            </option>
          </select>
        </div>
      </div>

      <PillTabs
        tabs={TABS.map(({ id, label }) => ({ id, label }))}
        activeTab={activeTab}
        onTabChange={id => setParam("tab", id, "total")}
      />

      <div class="overflow-hidden rounded-lg shadow-lg">
        <div
          aria-hidden="true"
          class="flex gap-3 bg-gray-50 px-3 py-2 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400"
        >
          <span class="w-4" />
          <span class="flex-1">Player</span>
          <span class="hidden w-48 md:block">Team</span>
          <span class="w-12 text-right">{activeTabConfig().column}</span>
          <span class="w-5" />
        </div>
        <div role="list">
          <For each={rows()}>
            {(player, index) => (
              <div role="listitem">
                <PlayerLink
                  slug={player?.slug}
                  from={from()}
                  class="flex min-h-[52px] touch-manipulation items-center gap-3 border-b bg-white px-3 text-sm transition-colors hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 active:bg-blue-100 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-gray-700 dark:active:bg-gray-600"
                >
                  <span class="w-4 text-xs text-gray-500">
                    {ranks()[index()]}
                  </span>
                  <span class="flex-1">
                    <span class="block font-semibold text-gray-900 dark:text-white">
                      {`${player?.first_name.trim()} ${player?.last_name.trim()} (${
                        player?.gender
                      })`}
                    </span>
                    <span class="text-xs text-gray-500 md:hidden">
                      {player?.team_name}
                    </span>
                  </span>
                  <span class="hidden w-48 md:block">{player?.team_name}</span>
                  <span class="w-12 text-right font-bold tabular-nums text-gray-900 dark:text-white">
                    <span class="sr-only">{activeTabConfig().label}: </span>
                    {player?.[activeTabConfig().field] ?? 0}
                  </span>
                  <Show when={player?.slug} fallback={<span class="w-5" />}>
                    <Icon
                      path={chevronRight}
                      class="h-5 w-5 text-gray-400"
                      aria-hidden="true"
                    />
                  </Show>
                </PlayerLink>
              </div>
            )}
          </For>
        </div>
        <Show when={rows().length === 0}>
          <div class="w-full bg-white py-2 text-center text-sm italic dark:bg-gray-800">
            No Players To Show
          </div>
        </Show>
      </div>
    </Show>
  );
};

export default TournamentStandings;
