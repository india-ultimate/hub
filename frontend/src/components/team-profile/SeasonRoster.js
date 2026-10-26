import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { chevronRight } from "solid-heroicons/solid";
import { For, Show } from "solid-js";

import { PlayerLink } from "../../playerLinks";
import RoleBadge from "../roster/role-badges/RoleBadge";
import Avatar from "./Avatar";

const NON_PLAYING = new Set(["COACH", "ACOACH", "MNGR"]);

const SeasonRoster = props => {
  const roster = () => props.roster;
  const players = () => roster().players.filter(p => !NON_PLAYING.has(p.role));
  const staff = () => roster().players.filter(p => NON_PLAYING.has(p.role));
  const from = () => ({ label: props.team.name });
  const Person = person => (
    <li>
      <PlayerLink
        slug={person.slug}
        from={from()}
        class="flex min-h-[44px] items-center gap-2 rounded-lg px-1 py-1 text-sm hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 active:bg-gray-100 dark:hover:bg-gray-700"
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
      <p class="text-xs text-gray-600 dark:text-gray-300">
        {roster().season} roster · at {roster().tournament_title}
      </p>
      <div class="mt-3 rounded-xl border border-gray-200 bg-white p-3 shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <ul
          role="list"
          class="grid gap-x-3 sm:grid-cols-2 md:grid-cols-1 lg:grid-cols-2"
        >
          <For each={players()}>{Person}</For>
        </ul>
        <Show when={staff().length}>
          <h3 class="mt-3 px-1 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300">
            Staff
          </h3>
          <ul
            role="list"
            class="mt-1 grid gap-x-3 sm:grid-cols-2 md:grid-cols-1 lg:grid-cols-2"
          >
            <For each={staff()}>{Person}</For>
          </ul>
        </Show>
        <A
          href={`/tournament/${roster().tournament_slug}/team/${props.team.slug}`}
          class="mt-2 flex min-h-[44px] items-center gap-1 rounded-lg px-1 text-sm font-medium text-blue-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 active:bg-gray-100 dark:text-blue-400"
        >
          Full roster and matches
          <Icon class="h-4 w-4" path={chevronRight} />
        </A>
      </div>
    </section>
  );
};

export default SeasonRoster;
