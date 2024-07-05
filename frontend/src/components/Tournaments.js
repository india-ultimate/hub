import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { For, Match, Show, Switch } from "solid-js";

import { fetchTournaments } from "../queries";

const Tournaments = () => {
  const tournamentsQuery = createQuery(() => ["tournaments"], fetchTournaments);
  return (
    <div>
      <h1 class="mb-5 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-3xl font-extrabold text-transparent ">
          Tournaments
        </span>
      </h1>
      <div
        class={
          "mt-5 grid grid-cols-1 justify-items-center gap-5 md:grid-cols-2 lg:grid-cols-3 "
        }
      >
        <For each={tournamentsQuery.data}>
          {tournament => (
            <Show when={tournament.status !== "DFT"}>
              <A
                href={
                  tournament.status === "REG" || tournament.status === "SCH"
                    ? `/tournament/${tournament.event?.slug}/register`
                    : `/tournament/${tournament.event?.slug}`
                }
                class="block w-full rounded-lg border border-blue-600 bg-white p-4 shadow dark:border-blue-400 dark:bg-gray-800"
              >
                <Switch>
                  <Match when={tournament.status === "REG"}>
                    <span class="h-fit rounded bg-green-200 px-2.5 py-0.5 text-sm font-medium text-green-800 dark:bg-green-900 dark:text-green-300">
                      Registrations open
                    </span>
                  </Match>
                  <Match when={tournament.status === "SCH"}>
                    <span class="h-fit rounded bg-yellow-100 px-2.5 py-0.5 text-sm font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
                      Registrations closed
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
                <h5 class="mb-2 mt-2 text-xl font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
                  {tournament.event.title}
                </h5>
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
