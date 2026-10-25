import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { chevronRight, mapPin, shieldCheck } from "solid-heroicons/solid";
import { Show } from "solid-js";

import Initials from "./Initials";

const chip =
  "inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-gray-700 dark:bg-gray-700 dark:text-gray-300";

const TeamCard = props => (
  <A
    href={`/team/${props.team.slug}`}
    data-season-card
    class="mx-auto mt-4 flex min-h-[44px] w-full max-w-[260px] touch-manipulation items-center gap-3 rounded-xl bg-white px-3 py-2 text-left shadow-sm ring-1 ring-gray-200 transition duration-200 hover:ring-blue-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 active:bg-gray-50 dark:bg-gray-700 dark:ring-gray-600 md:mx-0 md:mt-0 md:w-auto md:max-w-sm md:px-4 md:py-3"
  >
    <Show
      when={props.team.image || props.team.image_url}
      fallback={
        <Initials
          name={props.team.name}
          class="h-9 w-9 rounded-full text-xs md:h-10 md:w-10"
        />
      }
    >
      <img
        src={props.team.image || props.team.image_url}
        alt=""
        width="40"
        height="40"
        class="h-9 w-9 rounded-full object-cover md:h-10 md:w-10"
      />
    </Show>
    <span class="min-w-0 flex-1">
      <span class="block text-xs text-gray-500 dark:text-gray-400">
        {props.season} team
      </span>
      <span class="block break-words font-semibold text-gray-900 dark:text-white">
        {props.team.name}
      </span>
    </span>
    <Icon class="h-5 w-5 text-gray-400" path={chevronRight} />
  </A>
);

const Ribbon = props => (
  <A
    href={`/tournament/${props.represented.tournament_slug}/team/${props.represented.team.slug}`}
    data-ribbon
    class="relative mt-2 inline-flex touch-manipulation items-start gap-1.5 rounded-3xl bg-blue-50 px-3 py-2 text-left text-sm font-semibold leading-5 text-blue-800 ring-1 ring-blue-300 transition duration-200 before:absolute before:-inset-y-1 before:inset-x-0 before:content-[''] hover:bg-blue-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 active:bg-blue-200 dark:bg-blue-900 dark:text-blue-200 dark:ring-blue-700"
  >
    <Icon class="mt-0.5 h-4 w-4 shrink-0 text-blue-600" path={shieldCheck} />
    <span>
      Represented {props.represented.state}{" "}
      <span class="whitespace-nowrap">· {props.represented.year}</span>
      <span class="sr-only"> team roster</span>
    </span>
    <Icon
      class="-mr-1 mt-0.5 h-4 w-4 shrink-0 text-blue-500"
      path={chevronRight}
      aria-hidden="true"
    />
  </A>
);

const Hero = props => {
  const teams = () => new Set(props.profile.tournaments.map(t => t.team.id));
  const count = (n, word) => `${n === 1 ? word : word + "s"}`;
  return (
    <div class="rounded-2xl border border-gray-200 bg-gradient-to-br from-blue-50 via-white to-green-50 p-5 text-center shadow-sm dark:border-gray-700 dark:from-gray-800 dark:via-gray-800 dark:to-gray-800 md:flex md:items-center md:gap-8 md:p-6 md:text-left">
      <Show
        when={props.profile.profile_pic_url}
        fallback={
          <div class="mx-auto flex h-24 w-24 flex-none items-center justify-center rounded-full bg-gradient-to-br from-blue-200 to-green-200 p-1 text-3xl font-bold text-blue-800 ring-2 ring-gray-300 dark:from-gray-700 dark:to-gray-700 dark:text-gray-300 dark:ring-blue-500 md:mx-0 md:h-32 md:w-32 md:text-4xl">
            {props.profile.full_name?.charAt(0)?.toUpperCase() || "?"}
          </div>
        }
      >
        <img
          src={props.profile.profile_pic_url}
          alt=""
          width="128"
          height="128"
          class="mx-auto h-24 w-24 flex-none rounded-full object-cover ring-2 ring-gray-300 dark:ring-blue-500 md:mx-0 md:h-32 md:w-32"
        />
      </Show>
      <div class="md:flex-1">
        <h1 class="mt-3 bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-3xl font-extrabold text-transparent md:mt-0 md:text-4xl">
          {props.profile.full_name}
        </h1>
        <Show when={props.profile.represented}>
          <Ribbon represented={props.profile.represented} />
        </Show>
        <div class="mt-2 flex flex-wrap justify-center gap-2 text-xs md:justify-start">
          <span
            class={
              props.profile.match_up === "F"
                ? "rounded-full bg-white px-2.5 py-0.5 text-purple-800 ring-1 ring-inset ring-purple-300 dark:bg-gray-800 dark:text-purple-300 dark:ring-purple-700"
                : "rounded-full bg-white px-2.5 py-0.5 text-teal-800 ring-1 ring-inset ring-teal-300 dark:bg-gray-800 dark:text-teal-200 dark:ring-teal-700"
            }
          >
            {props.profile.match_up === "F"
              ? "Female matching"
              : "Male matching"}
          </span>
          <Show
            when={
              props.profile.state &&
              props.profile.state !== props.profile.represented?.state
            }
          >
            <span class={chip} data-state-chip>
              <Icon class="h-3 w-3" path={mapPin} />
              {props.profile.state}
            </span>
          </Show>
          <Show when={props.profile.jersey_number != null}>
            <span class={chip}>#{props.profile.jersey_number}</span>
          </Show>
        </div>
        <Show when={props.profile.tournaments.length}>
          <p class="mt-4 text-sm text-gray-600 dark:text-gray-300 md:mt-3">
            <b class="text-gray-900 dark:text-white">
              {props.profile.tournaments.length}
            </b>{" "}
            {count(props.profile.tournaments.length, "tournament")} ·{" "}
            <b class="text-gray-900 dark:text-white">{teams().size}</b>{" "}
            {count(teams().size, "team")}
          </p>
        </Show>
      </div>
      <Show when={props.profile.season_team}>
        <TeamCard
          team={props.profile.season_team.team}
          season={props.profile.season_team.season}
        />
      </Show>
    </div>
  );
};

export default Hero;
