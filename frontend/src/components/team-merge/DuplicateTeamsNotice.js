import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { For, Show } from "solid-js";

import { fetchTeamSuggestions, teamSuggestionsQueryKey } from "../../queries";

export const mergeLink = suggestion =>
  `/team/${suggestion.team.slug}/merge?copies=${suggestion.copies
    .map(copy => copy.id)
    .join(",")}`;

const count = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// Teams the signed-in admin runs that have likely copies. Pass teamId to
// show one team's, as its edit page does.
const DuplicateTeamsNotice = props => {
  const query = createQuery(
    () => teamSuggestionsQueryKey(props.teamId),
    () => fetchTeamSuggestions(props.teamId)
  );
  const found = () => (query.data || []).filter(s => !s.pending);

  return (
    <Show when={found().length > 0}>
      <section
        id="duplicate-teams-notice"
        aria-labelledby="duplicate-teams-title"
        class="mb-4 rounded-lg border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-900 dark:border-yellow-700 dark:bg-yellow-900 dark:text-yellow-100"
      >
        <h2 id="duplicate-teams-title" class="font-semibold">
          <Show
            when={props.teamId}
            fallback={`${count(found().length, "team")} you run may have been added twice`}
          >
            This team may have been added twice
          </Show>
        </h2>
        <ul class="mt-2 space-y-2">
          <For each={found()}>
            {suggestion => (
              <li class="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
                <span>
                  <Show when={!props.teamId}>
                    <span class="font-medium">
                      {suggestion.team.name.trim()}
                    </span>
                    :{" "}
                  </Show>
                  {suggestion.copies.map(copy => copy.label).join(", ")}{" "}
                  {suggestion.copies.length === 1 ? "has" : "have"} a matching
                  name.
                </span>
                <A
                  href={mergeLink(suggestion)}
                  class="inline-flex min-h-[44px] items-center rounded-lg bg-yellow-800 px-4 text-sm font-medium text-white hover:bg-yellow-900 focus:outline-none focus:ring-4 focus:ring-yellow-300 dark:bg-yellow-300 dark:text-gray-900 dark:hover:bg-yellow-200"
                >
                  Review and merge
                  <span class="sr-only"> {suggestion.team.name.trim()}</span>
                </A>
              </li>
            )}
          </For>
        </ul>
      </section>
    </Show>
  );
};

export default DuplicateTeamsNotice;
