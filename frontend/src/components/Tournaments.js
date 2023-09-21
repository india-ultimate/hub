import { createQuery } from "@tanstack/solid-query";
import { fetchTournaments } from "../queries";
import { For, Match, Show, Switch } from "solid-js";
import { A } from "@solidjs/router";

const Tournaments = () => {
  const tournamentsQuery = createQuery(() => ["tournaments"], fetchTournaments);

  return (
    <div>
      <h1 class="text-center mb-5">
        <span class="font-extrabold text-transparent text-3xl bg-clip-text bg-gradient-to-r from-blue-500 to-green-500 w-fit ">
          Tournaments
        </span>
      </h1>
      <div
        className={
          "grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3 justify-items-center mt-5 "
        }
      >
        <For each={tournamentsQuery.data}>
          {tournament => (
            <Show when={tournament.status !== "DFT"}>
              <A
                href={`/tournament/${tournament.id}`}
                class="block p-4 bg-white border border-blue-600 rounded-lg shadow dark:bg-gray-800 dark:border-blue-400 w-full"
              >
                <h5 className="mb-2 text-xl font-bold tracking-tight text-blue-600 dark:text-blue-400 capitalize">
                  {tournament.event.title}
                </h5>
                <div class="flex justify-between">
                  <span class="flex-grow text-sm capitalize">
                    {tournament.event.location}
                  </span>
                  <Switch>
                    <Match when={tournament.status === "COM"}>
                      <span className="h-fit bg-blue-100 text-blue-800 text-sm font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-blue-900 dark:text-blue-300">
                        Completed
                      </span>
                    </Match>
                    <Match when={tournament.status === "LIV"}>
                      <span className="h-fit bg-green-100 text-green-800 text-sm font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-green-900 dark:text-green-300">
                        Live
                      </span>
                    </Match>
                  </Switch>
                </div>
                <p className="text-sm text-blue-600 dark:text-blue-400">
                  {new Date(
                    Date.parse(tournament.event.start_date)
                  ).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "short",
                    day: "numeric"
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
                      day: "numeric"
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
