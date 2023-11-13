import { createQuery } from "@tanstack/solid-query";
import { fetchTournaments } from "../queries";
import { For, Match, Show, Switch } from "solid-js";
import { A } from "@solidjs/router";

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
                href={`/tournament/${tournament.event?.ultimate_central_slug}`}
                class="block w-full rounded-lg border border-blue-600 bg-white p-4 shadow dark:border-blue-400 dark:bg-gray-800"
              >
                <h5 class="mb-2 text-xl font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
                  {tournament.event.title}
                </h5>
                <div class="flex justify-between">
                  <span class="flex-grow text-sm capitalize">
                    {tournament.event.location}
                  </span>
                  <Switch>
                    <Match when={tournament.status === "COM"}>
                      <span class="mr-2 h-fit rounded bg-blue-100 px-2.5 py-0.5 text-sm font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                        Completed
                      </span>
                    </Match>
                    <Match when={tournament.status === "LIV"}>
                      <span class="mr-2 h-fit rounded bg-green-100 px-2.5 py-0.5 text-sm font-medium text-green-800 dark:bg-green-900 dark:text-green-300">
                        Live
                      </span>
                    </Match>
                  </Switch>
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
