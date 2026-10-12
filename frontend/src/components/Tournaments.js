import { A, useSearchParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { check } from "solid-heroicons/solid-mini";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";

import { fetchTournamentCards } from "../queries";
import { parseLocalDate, todayIST, tournamentLink } from "../utils";

const Tournaments = () => {
  // "" is this year and anything upcoming; otherwise one year's tournaments.
  // The year lives in the URL (?year=2025) so it survives back and sharing.
  const [searchParams, setSearchParams] = useSearchParams();
  // Anything but 1-4 digits above zero (?year=abc, 0, 10000) is the default view.
  const year = () => {
    const y = searchParams.year;
    return typeof y === "string" && /^\d{1,4}$/.test(y) && +y > 0
      ? String(+y)
      : "";
  };
  // A pill click replaces the entry: Back isn't a stack of years.
  const setYear = y =>
    setSearchParams({ year: y || undefined }, { replace: true, scroll: false });
  const tournamentsQuery = createQuery(
    () => ["tournament-cards", year()],
    () => fetchTournamentCards(year() ? `?year=${year()}` : ""),
    { keepPreviousData: true }
  );

  const [showMixed, setShowMixed] = createSignal(true);
  const [showOpens, setShowOpens] = createSignal(true);
  const [showWomens, setShowWomens] = createSignal(true);

  // Newest first, whatever order the API sends.
  const yearOptions = () => [
    { value: "", label: "This year & upcoming" },
    ...[...(tournamentsQuery.data?.years ?? [])]
      .sort((x, y) => y - x)
      .map(y => ({ value: String(y), label: String(y) }))
  ];

  // The checked pill is the one tab stop; with none checked (an unlisted
  // year) it is the first, so the group can still be focused.
  const isTabStop = (o, i) =>
    year() === o.value ||
    (i === 0 && !yearOptions().some(x => x.value === year()));

  let pillsRef;
  // A deep-linked old year can start off-screen in the scrolling row.
  createEffect(() => {
    if (!tournamentsQuery.data?.years) return;
    pillsRef
      ?.querySelector(`[data-year="${year()}"]`)
      ?.scrollIntoView({ inline: "center", block: "nearest" });
  });

  const shown = () =>
    (tournamentsQuery.data?.tournaments ?? []).filter(t => {
      if (t.status === "DFT") return false;
      if (t.event?.type === "OPN" && showOpens()) return true;
      if (t.event?.type === "MXD" && showMixed()) return true;
      if (t.event?.type === "WMN" && showWomens()) return true;
      return false;
    });

  const pill =
    "inline-flex min-h-[44px] shrink-0 snap-start items-center justify-center whitespace-nowrap rounded-full border px-4 text-sm font-medium transition-colors duration-200 motion-reduce:transition-none focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900";
  const on = "border-blue-600 bg-blue-600 text-white hover:bg-blue-700";
  const off =
    "border-gray-300 bg-white text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700";

  // Radiogroup: arrows move the selection, and only the selected pill is a tab stop.
  const onKeyDown = e => {
    const keys = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (!(e.key in keys)) return;
    e.preventDefault();
    const opts = yearOptions();
    const i = opts.findIndex(o => o.value === year());
    const next = opts[(i + keys[e.key] + opts.length) % opts.length];
    setYear(next.value);
    e.currentTarget
      .querySelector(`[data-year="${next.value}"]`)
      ?.focus({ preventScroll: false });
  };

  const categories = [
    { label: "Mixed", on: showMixed, set: setShowMixed },
    { label: "Opens", on: showOpens, set: setShowOpens },
    { label: "Womens", on: showWomens, set: setShowWomens }
  ];

  return (
    <div>
      <h1 class="mb-5 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-3xl font-extrabold text-transparent">
          Tournaments
        </span>
      </h1>

      <div class="space-y-3 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800/50">
        <div>
          <span
            id="year-label"
            class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400"
          >
            Year
          </span>
          <div
            ref={pillsRef}
            role="radiogroup"
            aria-labelledby="year-label"
            onKeyDown={onKeyDown}
            class="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 py-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            <For each={yearOptions()}>
              {(o, i) => (
                <button
                  type="button"
                  role="radio"
                  data-year={o.value}
                  aria-checked={year() === o.value}
                  tabindex={isTabStop(o, i()) ? 0 : -1}
                  onClick={() => setYear(o.value)}
                  class={clsx(pill, year() === o.value ? on : off)}
                >
                  {o.label}
                </button>
              )}
            </For>
          </div>
        </div>
        <div>
          <span
            id="category-label"
            class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400"
          >
            Category
          </span>
          <div
            class="flex flex-wrap gap-2"
            role="group"
            aria-labelledby="category-label"
          >
            <For each={categories}>
              {c => (
                <button
                  type="button"
                  aria-pressed={c.on()}
                  onClick={() => c.set(!c.on())}
                  class={clsx(
                    pill,
                    "gap-1.5",
                    c.on()
                      ? "border-blue-600 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:border-blue-400 dark:bg-blue-900/40 dark:text-blue-200"
                      : off
                  )}
                >
                  <Show when={c.on()}>
                    <Icon path={check} aria-hidden="true" class="h-4 w-4" />
                  </Show>
                  {c.label}
                </button>
              )}
            </For>
          </div>
        </div>
      </div>

      <Show when={tournamentsQuery.isError}>
        <p role="alert" class="mt-8 text-center text-red-600 dark:text-red-400">
          Couldn't load the tournaments. Check your connection and try again.
        </p>
      </Show>
      <Show when={tournamentsQuery.data && shown().length === 0}>
        <p class="mt-8 text-center text-gray-600 dark:text-gray-300">
          No tournaments match these filters
          {year() ? ` in ${year()}` : " yet"}. Try another year or category.
        </p>
      </Show>
      <div
        aria-busy={tournamentsQuery.isFetching}
        class={clsx(
          "mt-5 grid grid-cols-1 justify-items-center gap-5 transition-opacity duration-200 motion-reduce:transition-none md:grid-cols-2 lg:grid-cols-3",
          tournamentsQuery.isFetching && "opacity-50"
        )}
      >
        <For each={shown()}>
          {tournament => (
            <Show when={tournament.status !== "DFT"}>
              <A
                href={tournamentLink(tournament)}
                class="block w-full rounded-lg border border-blue-600 bg-white p-4 shadow dark:border-blue-400 dark:bg-gray-800"
              >
                <Show when={tournament.event?.type}>
                  <span class="mr-2 h-fit rounded bg-blue-200 px-2.5 py-0.5 text-sm font-medium text-blue-800 dark:bg-green-900 dark:text-green-300">
                    <Switch>
                      <Match when={tournament.event?.type === "MXD"}>
                        Mixed
                      </Match>
                      <Match when={tournament.event?.type === "OPN"}>
                        Opens
                      </Match>
                      <Match when={tournament.event?.type === "WMN"}>
                        Womens
                      </Match>
                    </Switch>
                  </span>
                </Show>

                <Switch>
                  <Match when={tournament.status === "SCH"}>
                    {(() => {
                      const now = todayIST();
                      const evt = tournament.event;
                      const teamIsOpen =
                        now >=
                          parseLocalDate(evt?.team_registration_start_date) &&
                        now <= parseLocalDate(evt?.team_registration_end_date);
                      const teamIsLate =
                        now > parseLocalDate(evt?.team_registration_end_date) &&
                        !!evt?.team_late_penalty_end_date &&
                        now <= parseLocalDate(evt?.team_late_penalty_end_date);
                      const playerIsOpen =
                        now >=
                          parseLocalDate(evt?.player_registration_start_date) &&
                        now <=
                          parseLocalDate(evt?.player_registration_end_date);
                      const playerIsLate =
                        now >
                          parseLocalDate(evt?.player_registration_end_date) &&
                        !!evt?.player_late_penalty_end_date &&
                        now <=
                          parseLocalDate(evt?.player_late_penalty_end_date);
                      return (
                        <>
                          <span
                            class={clsx(
                              "mr-2 h-fit rounded px-2.5 py-0.5 text-sm font-medium",
                              teamIsOpen
                                ? "bg-green-200 text-green-800 dark:bg-green-900 dark:text-green-300"
                                : teamIsLate
                                  ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
                                  : "bg-red-200 text-red-800 dark:bg-red-900 dark:text-red-300"
                            )}
                          >
                            Team Reg
                          </span>
                          <span
                            class={clsx(
                              "mr-2 h-fit rounded px-2.5 py-0.5 text-sm font-medium",
                              playerIsOpen
                                ? "bg-green-200 text-green-800 dark:bg-green-900 dark:text-green-300"
                                : playerIsLate
                                  ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
                                  : "bg-red-200 text-red-800 dark:bg-red-900 dark:text-red-300"
                            )}
                          >
                            Player Reg
                          </span>
                        </>
                      );
                    })()}
                  </Match>
                  <Match when={tournament.status === "LIV"}>
                    <span
                      class={clsx(
                        "h-fit rounded px-2.5 py-0.5 text-sm font-medium",
                        todayIST() <
                          parseLocalDate(tournament.event?.start_date)
                          ? "bg-blue-200 text-blue-800 dark:bg-blue-900 dark:text-blue-300"
                          : "bg-red-200 text-red-800 dark:bg-red-900 dark:text-red-300"
                      )}
                    >
                      {todayIST() < parseLocalDate(tournament.event?.start_date)
                        ? "Upcoming"
                        : "Live"}
                    </span>
                  </Match>
                  <Match when={tournament.status === "COM"}>
                    <span class="h-fit rounded bg-gray-300 px-2.5 py-0.5 text-sm font-medium text-gray-700 dark:bg-gray-900 dark:text-gray-300">
                      Completed
                    </span>
                  </Match>
                </Switch>
                <div class="mb-2 mt-2">
                  <h5 class="text-xl font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
                    {tournament.event.title}
                  </h5>
                  <Show when={tournament.event?.series}>
                    <p class="text-sm italic">
                      Part of{" "}
                      <span class="text-blue-600">
                        {tournament.event?.series?.name}
                      </span>
                    </p>
                  </Show>
                </div>

                <div class="flex justify-between">
                  <span class="flex-grow text-sm capitalize">
                    {tournament.event.location}
                  </span>
                </div>
                <p class="text-sm text-blue-600 dark:text-blue-400">
                  {new Date(
                    Date.parse(tournament.event.start_date)
                  ).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                    timeZone: "UTC"
                  })}
                  <Show
                    when={
                      tournament.event.start_date !== tournament.event.end_date
                    }
                  >
                    {" "}
                    to{" "}
                    {new Date(
                      Date.parse(tournament.event.end_date)
                    ).toLocaleDateString("en-US", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      timeZone: "UTC"
                    })}
                  </Show>
                </p>
              </A>
            </Show>
          )}
        </For>
      </div>
    </div>
  );
};

export default Tournaments;
