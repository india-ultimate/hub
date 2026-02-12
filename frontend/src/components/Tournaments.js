import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { createSignal, For, Match, Show, Switch } from "solid-js";

import { fetchTournaments } from "../queries";

const Tournaments = () => {
  const tournamentsQuery = createQuery(() => ["tournaments"], fetchTournaments);

  const [showMixed, setShowMixed] = createSignal(true);
  const [showOpens, setShowOpens] = createSignal(true);
  const [showWomens, setShowWomens] = createSignal(true);

  return (
    <div>
      <h1 class="mb-5 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-3xl font-extrabold text-transparent ">
          Tournaments
        </span>
      </h1>

      <ul class="flex w-full items-center rounded-lg border border-blue-500 bg-white text-sm font-medium text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white">
        <li class="w-full border-b-0 border-r border-blue-500 dark:border-gray-600">
          <div class="flex items-center ps-3">
            <input
              id="mixed-checkbox"
              type="checkbox"
              value="mixed"
              checked={showMixed()}
              onChange={e => setShowMixed(e.target.checked)}
              class="h-4 w-4 rounded border-gray-300 bg-gray-100 text-blue-600 focus:ring-2 focus:ring-blue-500 dark:border-gray-500 dark:bg-gray-600 dark:ring-offset-gray-700 dark:focus:ring-blue-600 dark:focus:ring-offset-gray-700"
            />
            <label
              for="mixed-checkbox"
              class="ms-2 w-full py-3 text-sm font-medium text-blue-600 dark:text-gray-300"
            >
              Mixed
            </label>
          </div>
        </li>
        <li class="w-full border-b-0 border-r border-blue-500 dark:border-gray-600">
          <div class="flex items-center ps-3">
            <input
              id="opens-checkbox"
              type="checkbox"
              value="mens"
              checked={showOpens()}
              onChange={e => setShowOpens(e.target.checked)}
              class="h-4 w-4 rounded border-gray-300 bg-gray-100 text-blue-600 focus:ring-2 focus:ring-blue-500 dark:border-gray-500 dark:bg-gray-600 dark:ring-offset-gray-700 dark:focus:ring-blue-600 dark:focus:ring-offset-gray-700"
            />
            <label
              for="opens-checkbox"
              class="ms-2 w-full py-3 text-sm font-medium text-blue-600 dark:text-gray-300"
            >
              Opens
            </label>
          </div>
        </li>
        <li class="w-full border-b-0 border-blue-500 dark:border-gray-600">
          <div class="flex items-center ps-3">
            <input
              id="womens-checkbox"
              type="checkbox"
              value="womens"
              checked={showWomens()}
              onChange={e => setShowWomens(e.target.checked)}
              class="h-4 w-4 rounded border-gray-300 bg-gray-100 text-blue-600 focus:ring-2 focus:ring-blue-500 dark:border-gray-500 dark:bg-gray-600 dark:ring-offset-gray-700 dark:focus:ring-blue-600 dark:focus:ring-offset-gray-700"
            />
            <label
              for="womens-checkbox"
              class="ms-2 w-full py-3 text-sm font-medium text-blue-600 dark:text-gray-300"
            >
              Womens
            </label>
          </div>
        </li>
      </ul>

      <div
        class={
          "mt-5 grid grid-cols-1 justify-items-center gap-5 md:grid-cols-2 lg:grid-cols-3 "
        }
      >
        <For
          each={tournamentsQuery.data?.filter(t => {
            if (t.event?.type === "OPN" && showOpens()) return true;
            if (t.event?.type === "MXD" && showMixed()) return true;
            if (t.event?.type === "WMN" && showWomens()) return true;
            return false;
          })}
        >
          {tournament => (
            <Show when={tournament.status !== "DFT"}>
              <A
                href={
                  tournament.status === "SCH"
                    ? `/tournament/${tournament.event?.slug}/register`
                    : `/tournament/${tournament.event?.slug}`
                }
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
                    <span
                      class={clsx(
                        "h-fit rounded px-2.5 py-0.5 text-sm font-medium",
                        new Date() >=
                          new Date(
                            tournament.event?.team_registration_start_date
                          ) &&
                          new Date() <=
                            new Date(
                              tournament.event?.team_registration_end_date
                            )
                          ? "bg-green-200 text-green-800 dark:bg-green-900 dark:text-green-300"
                          : new Date() >
                              new Date(
                                tournament.event?.team_registration_end_date
                              ) &&
                            new Date() <=
                              new Date(
                                tournament.event?.team_late_penalty_end_date
                              )
                          ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
                          : "bg-red-200 text-red-800 dark:bg-red-900 dark:text-red-300"
                      )}
                    >
                      Team Reg
                    </span>
                    <span
                      class={clsx(
                        "h-fit rounded px-2.5 py-0.5 text-sm font-medium",
                        new Date() >=
                          new Date(
                            tournament.event?.player_registration_start_date
                          ) &&
                          new Date() <=
                            new Date(
                              tournament.event?.player_registration_end_date
                            )
                          ? "bg-green-200 text-green-800 dark:bg-green-900 dark:text-green-300"
                          : new Date() >
                              new Date(
                                tournament.event?.player_registration_end_date
                              ) &&
                            new Date() <=
                              new Date(
                                tournament.event?.player_late_penalty_end_date
                              )
                          ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
                          : "bg-red-200 text-red-800 dark:bg-red-900 dark:text-red-300"
                      )}
                    >
                      Player Reg
                    </span>
                  </Match>
                  <Match when={tournament.status === "LIV"}>
                    <span
                      class={clsx(
                        "h-fit rounded px-2.5 py-0.5 text-sm font-medium",
                        new Date(Date.now()) < Date.parse(tournament.start_date)
                          ? "bg-blue-200 text-blue-800 dark:bg-blue-900 dark:text-blue-300"
                          : "bg-red-200 text-red-800 dark:bg-red-900 dark:text-red-300"
                      )}
                    >
                      {new Date(Date.now()) < Date.parse(tournament.start_date)
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
