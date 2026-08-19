import { createSignal, Show } from "solid-js";

import TournamentAgentTab from "./tournament-manager/agent/TournamentAgentTab";
import TournamentManagerClassic from "./tournament-manager/TournamentManagerClassic";

/**
 * Underline tabs — Flowbite MCP `flowbite://components/tabs` (Tabs with underline),
 * mapped to this project's classic Flowbite/Tailwind tokens.
 */
const TournamentManager = () => {
  const [tab, setTab] = createSignal("classic");
  const [selectedTournamentId, setSelectedTournamentId] = createSignal(null);

  const tabClass = active =>
    active
      ? "inline-block rounded-t-lg border-b-2 border-blue-600 p-4 text-blue-600 dark:border-blue-500 dark:text-blue-500"
      : "inline-block rounded-t-lg border-b-2 border-transparent p-4 hover:border-gray-300 hover:text-gray-600 dark:hover:text-gray-300";

  return (
    <div
      class={
        tab() === "agent"
          ? "flex h-[calc(100dvh-9.5rem)] flex-col overflow-hidden lg:h-[calc(100dvh-13.5rem)]"
          : undefined
      }
    >
      <div class="mb-4 shrink-0 border-b border-gray-200 text-center text-sm font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400">
        <ul class="-mb-px flex flex-wrap">
          <li class="me-2">
            <button
              type="button"
              class={tabClass(tab() === "classic")}
              aria-current={tab() === "classic" ? "page" : undefined}
              onClick={() => setTab("classic")}
            >
              Classic
            </button>
          </li>
          <li class="me-2">
            <button
              type="button"
              class={tabClass(tab() === "agent")}
              aria-current={tab() === "agent" ? "page" : undefined}
              onClick={() => setTab("agent")}
            >
              AI Agent
            </button>
          </li>
        </ul>
      </div>

      <Show when={tab() === "classic"}>
        <TournamentManagerClassic
          tournamentId={selectedTournamentId()}
          onTournamentSelected={id => setSelectedTournamentId(id)}
        />
      </Show>
      <Show when={tab() === "agent"}>
        <div class="min-h-0 flex-1 overflow-hidden">
          <TournamentAgentTab
            tournamentId={selectedTournamentId()}
            onSelectTournament={id => setSelectedTournamentId(id)}
          />
        </div>
      </Show>
    </div>
  );
};

export default TournamentManager;
