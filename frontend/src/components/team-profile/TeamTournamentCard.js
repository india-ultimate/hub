import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { calendar, chevronRight } from "solid-heroicons/solid";
import { Show } from "solid-js";

import { formatDates } from "../../dates";
import { parseLocalDate, todayIST } from "../../utils";
import Placement from "../player-profile/Placement";

const chip =
  "rounded-md bg-gray-100 px-2 py-1 text-gray-700 dark:bg-gray-700 dark:text-gray-300";

const TeamTournamentCard = props => {
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
  const upcoming = () =>
    t().status === "SCH" && parseLocalDate(t().start_date) > todayIST();
  const record = () =>
    `${t().record.wins}–${t().record.losses}${t().record.draws ? `–${t().record.draws}` : ""}`;
  return (
    <article
      data-first-new={props.firstNew ? "" : undefined}
      class="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800"
    >
      <div class="flex items-start gap-3">
        <Show when={t().logo_light || t().logo_dark}>
          {logo(t().logo_light ?? t().logo_dark, "light", "dark:hidden")}
          {logo(t().logo_dark ?? t().logo_light, "dark", "hidden dark:block")}
        </Show>
        <div class="min-w-0 flex-1">
          <h4 class="contents">
            <A
              href={`/tournament/${t().slug}`}
              class="inline-flex min-h-[44px] items-center font-semibold text-gray-900 hover:text-blue-600 focus-visible:rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-white dark:hover:text-blue-400"
            >
              {t().title}
            </A>
          </h4>
          <div class="mt-0.5 flex items-start gap-1 text-xs text-gray-600 dark:text-gray-300">
            <Icon
              class="mt-0.5 h-3.5 w-3.5 flex-none"
              path={calendar}
              aria-hidden="true"
            />
            <span class="min-w-0 break-words">
              {formatDates(t().start_date, t().end_date)}
              {t().location ? ` · ${t().location}` : ""}
            </span>
          </div>
        </div>
        <Placement t={t()} />
      </div>
      <div class="mt-2 flex flex-wrap gap-1.5 text-xs">
        <span class={chip}>{t().division}</span>
        <Show when={t().record}>
          <span class="rounded-md bg-gray-50 px-2 py-1 text-gray-700 ring-1 ring-inset ring-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:ring-gray-600">
            <span class="text-gray-500 dark:text-gray-400">W–L </span>
            <b class="text-gray-900 dark:text-white">{record()}</b>
          </span>
        </Show>
        <Show when={upcoming()}>
          <span class="rounded-md px-2 py-1 text-gray-700 ring-1 ring-inset ring-gray-300 dark:text-gray-300 dark:ring-gray-600">
            Upcoming
          </span>
        </Show>
        <Show when={t().spirit_rank}>
          <span class="rounded-md bg-green-50 px-2 py-1 text-green-800 dark:bg-green-900 dark:text-green-300">
            Spirit #{t().spirit_rank}
          </span>
        </Show>
      </div>
      <A
        href={`/tournament/${t().slug}/team/${props.team.slug}`}
        class="mt-2 flex min-h-[44px] items-center gap-2 rounded-lg px-1 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 active:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-700"
      >
        Matches &amp; roster
        <Icon
          class="ml-auto h-4 w-4 text-gray-500 dark:text-gray-400"
          path={chevronRight}
          aria-hidden="true"
        />
      </A>
    </article>
  );
};

export default TeamTournamentCard;
