import { createQuery } from "@tanstack/solid-query";
import { createSignal, For } from "solid-js";

import { fetchTournaments } from "../queries";
import TournamentCard from "./tournament/TournamentCard";

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
          {tournament => <TournamentCard tournament={tournament} />}
        </For>
      </div>
    </div>
  );
};

export default Tournaments;
