import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { calendar, chevronRight, star } from "solid-heroicons/solid";
import { Show } from "solid-js";

import { formatDates } from "../../dates";
import RoleBadge from "../roster/role-badges/RoleBadge";
import Initials from "./Initials";
import Placement from "./Placement";

const NON_PLAYING = new Set(["COACH", "ACOACH", "MNGR"]);

const StatChip = props => (
  <span class="rounded-md bg-gray-100 px-2 py-1 dark:bg-gray-700">
    <b class="text-gray-900 dark:text-white">{props.value}</b>{" "}
    {props.value === 1 ? props.label : `${props.label}s`}
  </span>
);

const AwardChip = props => (
  <span
    class={`inline-flex items-center gap-1 rounded-md px-2 py-1 ${props.class}`}
  >
    <Icon class="h-3 w-3" path={star} />
    {props.label} ×{props.count}
  </span>
);

const Note = props => (
  <p class="mt-1 text-xs italic text-gray-500 dark:text-gray-400">
    {props.children}
  </p>
);

const TournamentCard = props => {
  const t = () => props.tournament;
  const logo = (src, theme, hide) => (
    <img
      src={src}
      alt=""
      data-logo={theme}
      width="44"
      height="44"
      loading="lazy"
      class={`h-11 w-11 flex-none rounded-lg object-contain ${hide}`}
    />
  );
  const noPlayingStats = () =>
    t().role === "MNGR"
      ? "Managed, so no playing stats"
      : "Coached, so no playing stats";

  return (
    <article
      class={`rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800 ${props.pinned ? "ring-2 ring-blue-500" : ""}`}
    >
      <div class="flex items-start gap-3">
        <Show when={t().logo_light || t().logo_dark}>
          {logo(t().logo_light ?? t().logo_dark, "light", "dark:hidden")}
          {logo(t().logo_dark ?? t().logo_light, "dark", "hidden dark:block")}
        </Show>
        <div class="min-w-0 flex-1">
          <A
            href={`/tournament/${t().slug}`}
            class="inline-flex min-h-[44px] items-center font-semibold text-gray-900 hover:text-blue-600 hover:underline focus-visible:rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:text-white dark:hover:text-blue-400"
          >
            {t().title}
          </A>
          <div class="mt-0.5 flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
            <Icon class="h-3.5 w-3.5 flex-none" path={calendar} />
            <span class="truncate">
              {formatDates(t().start_date, t().end_date)}
              {t().location ? ` · ${t().location}` : ""}
            </span>
          </div>
        </div>
        <Placement t={t()} />
      </div>
      <A
        href={`/tournament/${t().slug}/team/${t().team.slug}`}
        class="mt-3 flex min-h-[44px] items-center gap-2 rounded-lg px-1 py-2 text-sm hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:hover:bg-gray-700"
      >
        <Show
          when={t().team.image || t().team.image_url}
          fallback={
            <Initials
              name={t().team.name}
              class="h-7 w-7 rounded-full text-xs"
            />
          }
        >
          <img
            src={t().team.image || t().team.image_url}
            alt=""
            width="28"
            height="28"
            loading="lazy"
            class="h-7 w-7 rounded-full object-cover"
          />
        </Show>
        <span class="font-medium text-gray-800 dark:text-gray-200">
          {t().team.name}
        </span>
        <RoleBadge role={t().role} />
        <Icon class="ml-auto h-4 w-4 text-gray-400" path={chevronRight} />
      </A>
      <Show
        when={t().is_playing && !NON_PLAYING.has(t().role)}
        fallback={<Note>{noPlayingStats()}</Note>}
      >
        <div class="mt-2 flex flex-wrap gap-1.5 text-xs text-gray-600 dark:text-gray-300">
          <Show
            when={t().stats}
            fallback={<Note>Stats not tracked at this tournament</Note>}
          >
            <StatChip value={t().stats.goals} label="goal" />
            <StatChip value={t().stats.assists} label="assist" />
            <StatChip value={t().stats.blocks} label="block" />
            <StatChip value={t().stats.games} label="game" />
          </Show>
          <Show when={t().mvp}>
            <AwardChip
              label="MVP"
              count={t().mvp}
              class="bg-yellow-50 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
            />
          </Show>
          <Show when={t().msp}>
            <AwardChip
              label="MSP"
              count={t().msp}
              class="bg-green-50 text-green-800 dark:bg-green-900 dark:text-green-300"
            />
          </Show>
        </div>
      </Show>
    </article>
  );
};

export default TournamentCard;
