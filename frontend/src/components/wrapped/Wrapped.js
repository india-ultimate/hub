import { createQuery } from "@tanstack/solid-query";
import { domToPng } from "modern-screenshot";
import { Icon } from "solid-heroicons";
import { arrowDownTray, sparkles, trophy } from "solid-heroicons/solid";
import { createEffect, createMemo, createSignal, For, Show } from "solid-js";

import { fetchUser, fetchWrappedData } from "../../queries";
import { assetURL } from "../../utils";

const StatCard = props => {
  return (
    <div class={props.double ? "col-span-2 rounded-lg" : "rounded-lg"}>
      <p class="text-left text-sm font-semibold text-black">{props.label}</p>
      <p class="text-left text-lg font-semibold text-blue-600 dark:text-blue-400">
        {props.value ?? "NA"}
      </p>
    </div>
  );
};

const TournamentBestCard = props => {
  return (
    <Show when={props.data && Object.keys(props.data).length > 0}>
      <div>
        <h3 class="text-md text-left font-semibold text-black">
          {props.title}
        </h3>
        <div class="space-y-1">
          <p class="text-md text-left font-semibold text-blue-600 dark:text-blue-400">
            <span class=" text-blue-600 dark:text-blue-400">
              {props.data.tournament_name}
            </span>
            {" | "}
            <span class="text-sm font-medium text-blue-600 dark:text-blue-400">
              {props.data.count}
              {props.title.includes("Offensive")
                ? " scores"
                : props.title.includes("Playmaking")
                ? " assists"
                : " blocks"}
            </span>
          </p>
        </div>
      </div>
    </Show>
  );
};

const WrappedYearDisplay = props => {
  const wrapped = () => props.wrapped;
  const player = () => props.player;
  const [isDownloading, setIsDownloading] = createSignal(false);
  const [isRevealed, setIsRevealed] = createSignal(false);
  let cardRef;

  const handleDownload = async () => {
    if (!cardRef) return;

    setIsDownloading(true);
    try {
      const dataUrl = await domToPng(cardRef, {
        quality: 1.0,
        scale: 8,
        backgroundColor: "#ffffff"
      });

      const link = document.createElement("a");
      link.download = `wrapped-${wrapped()?.year || "year"}.png`;
      link.href = dataUrl;
      link.click();
    } catch (error) {
      console.error("Error generating image:", error);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleReveal = () => {
    setIsRevealed(true);
  };

  return (
    <div class="space-y-6">
      <Show
        when={isRevealed()}
        fallback={
          <div class="flex min-h-[60vh] flex-col items-center justify-center space-y-8">
            <h1 class="text-center text-4xl font-bold text-blue-700 dark:text-white md:text-6xl">
              <span class="bold mb-2 block text-8xl">{wrapped()?.year}</span>
              <span class="rounded-lg bg-blue-700 px-4 py-2 italic text-white">
                That's a Wrap!
              </span>
            </h1>
            <button
              onClick={handleReveal}
              class="rounded-lg bg-white px-8 py-4 text-xl font-bold text-blue-700 shadow-lg transition-all hover:scale-105 active:scale-95"
            >
              <span class="flex items-center gap-2">
                Reveal My Stats!
                <Icon path={sparkles} class="h-5 w-5" />
              </span>
            </button>
          </div>
        }
      >
        <div
          style={{
            animation: "fadeInUp 0.6s ease-out forwards"
          }}
        >
          <div>
            <div
              ref={cardRef}
              class="relative aspect-[4/7] w-full rounded-lg border border-gray-200 bg-white px-5 py-5"
            >
              <div class="flex items-center justify-between">
                <h2 class="font-serif text-blue-700">
                  <span class="block text-6xl font-bold">
                    {wrapped()?.year}
                  </span>{" "}
                  <span class="text-3xl italic">Ultimate Wrapped</span>
                </h2>
                <span>
                  <Show
                    when={player()?.profile_pic_url}
                    fallback={
                      <div class="flex h-20 w-20 items-center justify-center rounded-full bg-gray-200">
                        <span class="text-2xl text-gray-500">
                          {player()?.full_name?.charAt(0)?.toUpperCase() || "?"}
                        </span>
                      </div>
                    }
                  >
                    <img
                      src={props.player.profile_pic_url}
                      alt="Profile"
                      class="h-20 w-20 rounded-full object-cover"
                    />
                  </Show>
                </span>
              </div>

              <div class="mt-2 w-full rounded-lg bg-blue-50 p-2">
                <div class="grid grid-cols-4">
                  <StatCard label="Games" value={wrapped()?.total_games} />
                  <StatCard label="Scores" value={wrapped()?.total_scores} />
                  <StatCard label="Assists" value={wrapped()?.total_assists} />
                  <StatCard label="Blocks" value={wrapped()?.total_blocks} />
                  <StatCard label="MVPs" value={wrapped()?.match_mvps} />
                  <StatCard label="MSPs" value={wrapped()?.match_msps} />
                  <StatCard
                    label="Tournaments"
                    value={wrapped()?.tournaments_played}
                  />
                  {/* <StatCard
              label="Longest Streak of Scores or Assists in games"
              double={true} 
              value={wrapped()?.continuous_streak_scored_or_assisted}
            /> */}
                </div>
              </div>

              {/* Tournament Bests */}
              <div class="mt-2 grid grid-cols-1 rounded-lg bg-blue-50 p-2 md:grid-cols-3">
                <TournamentBestCard
                  title="⚡ Peak Offensive Performance"
                  data={wrapped()?.most_scores_in_tournament}
                />
                <TournamentBestCard
                  title="🎨 Playmaking Masterclass"
                  data={wrapped()?.most_assists_in_tournament}
                />
                <TournamentBestCard
                  title="🚫 Disc Denial Expert"
                  data={wrapped()?.most_blocks_in_tournament}
                />
              </div>

              {/* Top Teammates */}
              <div class="mt-2 grid grid-cols-2 rounded-lg bg-blue-50 p-2">
                <Show
                  when={
                    wrapped()?.top_teammates_i_assisted &&
                    wrapped()?.top_teammates_i_assisted.length > 0
                  }
                >
                  <div>
                    <h3 class="text-md text-left font-semibold text-black">
                      🎯 My Favourite Targets
                    </h3>
                    <div class="mt-1 text-base">
                      <For
                        each={wrapped()?.top_teammates_i_assisted.slice(0, 3)}
                      >
                        {teammate => (
                          <div class="flex items-center gap-1">
                            <span class="font-semibold text-blue-600 dark:text-blue-400">
                              {teammate.player_name}
                            </span>
                            <span class="text-sm font-medium text-blue-600 dark:text-blue-400">
                              ({teammate.count})
                            </span>
                          </div>
                        )}
                      </For>
                    </div>
                  </div>
                </Show>

                <Show
                  when={
                    wrapped()?.top_teammates_who_assisted_me &&
                    wrapped()?.top_teammates_who_assisted_me.length > 0
                  }
                >
                  <div>
                    <h3 class="text-md text-left font-semibold text-black">
                      🙌 My Favorite Throwers
                    </h3>
                    <div class="mt-1 text-base">
                      <For
                        each={wrapped()?.top_teammates_who_assisted_me.slice(
                          0,
                          3
                        )}
                      >
                        {teammate => (
                          <div class="flex items-center gap-1">
                            <span class="font-semibold text-blue-600 dark:text-blue-400">
                              {teammate.player_name}
                            </span>
                            <span class="text-sm font-medium text-blue-600 dark:text-blue-400">
                              ({teammate.count})
                            </span>
                          </div>
                        )}
                      </For>
                    </div>
                  </div>
                </Show>
              </div>

              {/* Teams Played For */}
              {/* <Show
          when={
            wrapped()?.teams_played_for &&
            wrapped()?.teams_played_for.length > 0
          }
        >
          <div class="mt-2 rounded-lg bg-blue-50 p-2">
            <h3 class="text-md text-left font-semibold text-black mb-2">
              Jerseys I Wore
            </h3>
            <div class="space-y-1">
              <span class="font-semibold text-blue-600 dark:text-blue-400">
                {wrapped()?.teams_played_for.map(team => team.team_name).join(", ")}
              </span>
            </div>
          </div>
        </Show> */}

              <div class="absolute bottom-0 left-0 right-0">
                <div class="flex items-center justify-between px-5 py-2">
                  <img
                    class="h-8"
                    src={assetURL("iu-horizontal.png")}
                    alt="India Ultimate Logo"
                  />
                  <span class="text-xs italic text-blue-700">
                    hub.indiaultimate.org/wrapped
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="mt-5 flex items-center justify-center">
            <button
              onClick={handleDownload}
              disabled={isDownloading()}
              class="mb-4 flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white transition-all hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Icon path={arrowDownTray} class="h-5 w-5" />
              <span>{isDownloading() ? "Downloading..." : "Download"}</span>
            </button>
          </div>
        </div>
      </Show>
    </div>
  );
};

const Wrapped = () => {
  const userQuery = createQuery(() => ["me"], fetchUser);
  const wrappedQuery = createQuery(() => ["wrapped"], fetchWrappedData);
  const [selectedYear, setSelectedYear] = createSignal(null);

  // Get available years from wrapped data
  const availableYears = createMemo(() => {
    if (!wrappedQuery.data || wrappedQuery.data.length === 0) return [];
    return wrappedQuery.data.map(w => w.year).sort((a, b) => b - a); // Sort descending (latest first)
  });

  // Set default to latest year when data loads
  createEffect(() => {
    if (availableYears().length > 0 && selectedYear() === null) {
      setSelectedYear(availableYears()[0]);
    }
  });

  // Get wrapped data for selected year
  const displayData = createMemo(() => {
    if (!wrappedQuery.data || !selectedYear()) return null;
    return wrappedQuery.data.find(w => w.year === selectedYear());
  });

  return (
    <div>
      <Show
        when={userQuery.isLoading}
        fallback={
          <Show
            when={!userQuery.data}
            fallback={
              <Show
                when={wrappedQuery.isLoading}
                fallback={
                  <Show
                    when={wrappedQuery.error}
                    fallback={
                      <Show
                        when={wrappedQuery.data && wrappedQuery.data.length > 0}
                        fallback={
                          <div class="rounded-lg border border-gray-200 bg-white p-8 text-center dark:border-gray-700 dark:bg-gray-800">
                            <Icon
                              path={trophy}
                              class="mx-auto h-16 w-16 text-gray-400 dark:text-gray-500"
                            />
                            <h3 class="mt-4 text-lg font-semibold text-gray-900 dark:text-white">
                              No Wrapped Data Available
                            </h3>
                            <p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
                              Wrapped data will be available after the year
                              ends. Check back soon!
                            </p>
                          </div>
                        }
                      >
                        <Show
                          when={displayData()}
                          fallback={
                            <div class="flex items-center justify-center p-8">
                              <div class="text-center">
                                <div class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent" />
                                <p class="mt-4 text-gray-600 dark:text-gray-400">
                                  {selectedYear()
                                    ? `Loading wrapped data for ${selectedYear()}...`
                                    : "Loading wrapped data..."}
                                </p>
                              </div>
                            </div>
                          }
                        >
                          <WrappedYearDisplay
                            player={userQuery.data?.player}
                            wrapped={displayData()}
                          />
                        </Show>
                        <Show when={availableYears().length > 0}>
                          <div class="mt-4 flex items-center gap-2">
                            <p class="text-lg font-bold text-blue-600 dark:text-gray-400">
                              Select Year
                            </p>
                            <select
                              id="year-select"
                              value={selectedYear()}
                              onChange={e =>
                                setSelectedYear(Number(e.target.value))
                              }
                              class="block rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500 "
                            >
                              <For each={availableYears()}>
                                {year => <option value={year}>{year}</option>}
                              </For>
                            </select>
                          </div>
                        </Show>
                      </Show>
                    }
                  >
                    <div class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800 dark:border-red-800 dark:bg-red-900 dark:text-red-200">
                      <p class="font-medium">Error loading wrapped data</p>
                      <p class="text-sm">
                        {wrappedQuery.error?.message || "Unknown error"}
                      </p>
                    </div>
                  </Show>
                }
              >
                <div class="flex items-center justify-center p-8">
                  <div class="text-center">
                    <div class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent" />
                    <p class="mt-4 text-gray-600 dark:text-gray-400">
                      Loading wrapped data...
                    </p>
                  </div>
                </div>
              </Show>
            }
          >
            <div class="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-yellow-800 dark:border-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
              <p class="font-medium">Authentication Required</p>
              <p class="text-sm">Please log in to view your wrapped data.</p>
            </div>
          </Show>
        }
      >
        <div class="flex items-center justify-center p-8">
          <div class="text-center">
            <div class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent" />
            <p class="mt-4 text-gray-600 dark:text-gray-400">
              Loading user data...
            </p>
          </div>
        </div>
      </Show>
    </div>
  );
};

export default Wrapped;
