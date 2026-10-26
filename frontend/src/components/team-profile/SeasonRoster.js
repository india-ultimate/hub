import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { chevronRight } from "solid-heroicons/solid";
import { createEffect, createSignal, For, on, Show } from "solid-js";

import { PlayerLink } from "../../playerLinks";
import { parseLocalDate } from "../../utils";
import RoleBadge from "../roster/role-badges/RoleBadge";
import Avatar from "./Avatar";

const monthYear = iso =>
  parseLocalDate(iso).toLocaleDateString("en-IN", {
    month: "short",
    year: "numeric"
  });

const SeasonRoster = props => {
  const [selected, setSelected] = createSignal(0);
  createEffect(
    on(
      () => props.team.slug,
      () => setSelected(0),
      { defer: true }
    )
  );
  const current = () => Math.min(selected(), props.rosters.length - 1);
  const roster = () => props.rosters[current()];
  const players = () => roster().players.filter(p => p.is_playing);
  const others = () => roster().players.filter(p => !p.is_playing);
  const from = () => ({ label: props.team.name });
  const count = r => r.players.filter(p => p.is_playing).length;
  const tabs = [];

  const onKeyDown = event => {
    const last = props.rosters.length - 1;
    const next = {
      ArrowRight: current() === last ? 0 : current() + 1,
      ArrowLeft: current() === 0 ? last : current() - 1,
      Home: 0,
      End: last
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    setSelected(next);
    tabs[next]?.focus();
  };

  const Person = person => (
    <li>
      <PlayerLink
        slug={person.slug}
        from={from()}
        class="flex min-h-[44px] items-center gap-2 rounded-lg px-1 py-1 text-sm transition-colors duration-200 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 active:bg-gray-100 motion-reduce:transition-none dark:hover:bg-gray-700"
      >
        <Avatar
          src={person.profile_pic_url}
          name={person.full_name}
          size="h-8 w-8"
        />
        <span class="min-w-0 break-words font-medium text-gray-800 dark:text-gray-200">
          {person.full_name}
        </span>
        <span class="ml-auto flex flex-none items-center">
          <RoleBadge role={person.role} />
        </span>
        <Show when={person.slug}>
          <Icon
            class="h-4 w-4 flex-none text-gray-500"
            path={chevronRight}
            aria-hidden="true"
          />
        </Show>
      </PlayerLink>
    </li>
  );

  return (
    <section
      aria-labelledby="roster-heading"
      class="min-w-0 md:only:col-span-2"
    >
      <h2
        id="roster-heading"
        class="text-lg font-bold text-gray-900 dark:text-white"
      >
        This season
      </h2>
      <Show when={props.rosters.length > 1}>
        <div
          role="tablist"
          aria-label="Roster by division"
          onKeyDown={onKeyDown}
          class="mt-2 flex w-full max-w-full overflow-x-auto rounded-xl bg-gray-100 p-1 dark:bg-gray-700 sm:inline-flex sm:w-auto"
        >
          <For each={props.rosters}>
            {(r, i) => (
              <button
                type="button"
                role="tab"
                id={`roster-tab-${i()}`}
                aria-selected={current() === i()}
                aria-controls="roster-panel"
                tabindex={current() === i() ? 0 : -1}
                ref={el => (tabs[i()] = el)}
                onClick={() => setSelected(i())}
                class={`min-h-[44px] flex-1 whitespace-nowrap rounded-lg px-4 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 motion-reduce:transition-none ${
                  current() === i()
                    ? "bg-white font-semibold text-blue-700 shadow-sm dark:bg-gray-800 dark:text-blue-400"
                    : "font-medium text-gray-700 hover:text-gray-900 active:bg-gray-200 dark:text-gray-300"
                }`}
              >
                {r.division}{" "}
                <span class="text-xs font-normal text-gray-600 dark:text-gray-300">
                  {count(r)}
                </span>
                <span class="sr-only"> players</span>
              </button>
            )}
          </For>
        </div>
      </Show>
      <div
        id="roster-panel"
        role={props.rosters.length > 1 ? "tabpanel" : undefined}
        aria-labelledby={
          props.rosters.length > 1 ? `roster-tab-${current()}` : undefined
        }
        tabindex={props.rosters.length > 1 ? 0 : undefined}
        class="rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
      >
        <p class="mt-3 text-sm text-gray-700 dark:text-gray-300">
          Roster at {roster().tournament_title} ·{" "}
          {monthYear(roster().start_date)}
        </p>
        <div class="mt-3 rounded-xl border border-gray-200 bg-white p-3 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <ul role="list" class="grid gap-x-3 sm:grid-cols-2 md:grid-cols-1">
            <For each={players()}>{Person}</For>
          </ul>
          <Show when={others().length}>
            <h3 class="mt-3 px-1 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300">
              Non-players
            </h3>
            <ul
              role="list"
              class="mt-1 grid gap-x-3 sm:grid-cols-2 md:grid-cols-1"
            >
              <For each={others()}>{Person}</For>
            </ul>
          </Show>
          <A
            href={`/tournament/${roster().tournament_slug}/team/${props.team.slug}`}
            class="mt-2 flex min-h-[44px] items-center gap-1 rounded-lg px-1 text-sm font-medium text-blue-700 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 active:bg-gray-100 dark:text-blue-400"
          >
            Full roster and matches
            <Icon class="h-4 w-4" path={chevronRight} aria-hidden="true" />
          </A>
        </div>
      </div>
    </section>
  );
};

export default SeasonRoster;
