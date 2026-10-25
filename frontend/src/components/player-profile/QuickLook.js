import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { chevronRight, star } from "solid-heroicons/solid";
import { For, Show } from "solid-js";

import { careerTotals, PlayerLink, profileQueryKey } from "../../playerLinks";
import { fetchPlayerProfile } from "../../queries";
import Modal from "../Modal";

const ROLES = {
  CAP: "Captain",
  SCAP: "Spirit Captain",
  COACH: "Coach",
  ACOACH: "Assistant Coach",
  MNGR: "Manager"
};

const AWARD_STYLES = {
  MVP: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  MSP: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
};

const plural = (n, word) => (n === 1 ? word.slice(0, -1) : word);

const QuickLook = props => {
  const query = createQuery(
    () => profileQueryKey(props.player?.slug),
    () => fetchPlayerProfile(props.player.slug),
    {
      staleTime: 60_000,
      get enabled() {
        return !!props.player?.slug;
      }
    }
  );
  const profile = () => query.data;
  const tournament = () =>
    profile()?.tournaments.find(t => t.slug === props.from?.tournamentSlug);
  const subtitle = () =>
    [
      tournament()?.team.name ?? profile()?.season_team?.team.name,
      profile()?.jersey_number != null && `#${profile().jersey_number}`,
      ROLES[tournament()?.role]
    ]
      .filter(Boolean)
      .join(" · ");
  const career = () => {
    const c = careerTotals(profile().tournaments);
    return [
      ...(c.tracked
        ? ["goals", "assists", "blocks"].map(k => [c[k], plural(c[k], k)])
        : []),
      [c.mvp, "MVP"],
      [c.msp, "MSP"]
    ].filter(([n]) => n > 0);
  };
  const photo = () =>
    props.player?.profile_pic_url ?? profile()?.profile_pic_url;

  return (
    <Modal
      ref={props.ref}
      title={
        <h3 class="text-lg font-bold text-gray-900 dark:text-white">
          {props.player?.full_name}
        </h3>
      }
    >
      <div class="flex items-center gap-4">
        <Show
          when={photo()}
          fallback={
            <span class="flex h-16 w-16 flex-none items-center justify-center rounded-full bg-gradient-to-br from-blue-200 to-green-200 text-xl font-bold text-blue-800 ring-2 ring-gray-300 dark:from-gray-700 dark:to-gray-700 dark:text-gray-300 dark:ring-blue-500">
              {props.player?.full_name?.charAt(0)?.toUpperCase() || "?"}
            </span>
          }
        >
          <img
            src={photo()}
            alt=""
            width="64"
            height="64"
            class="h-16 w-16 flex-none rounded-full object-cover ring-2 ring-gray-300 dark:ring-blue-500"
          />
        </Show>
        <div class="min-h-5 text-sm text-gray-500 dark:text-gray-400">
          {subtitle()}
        </div>
      </div>

      <Show when={props.match}>
        <div class="mt-4 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          This match
        </div>
        <div class="mt-1 grid grid-cols-3 gap-2 text-center">
          <For
            each={[
              ["Goals", props.match.goals],
              ["Assists", props.match.assists],
              ["Blocks", props.match.blocks]
            ]}
          >
            {([label, value]) => (
              <div
                data-stat={label.toLowerCase()}
                class="rounded-lg bg-blue-50 py-2 dark:bg-gray-700"
              >
                <div class="text-xl font-bold text-blue-700 dark:text-blue-300">
                  {value}
                </div>
                <div class="text-xs uppercase text-gray-500 dark:text-gray-400">
                  {label}
                </div>
              </div>
            )}
          </For>
        </div>
      </Show>
      <Show when={props.award}>
        <div
          class={`mt-4 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${AWARD_STYLES[props.award]}`}
        >
          <Icon path={star} class="h-3.5 w-3.5" />
          {props.award} in this match
        </div>
      </Show>

      <Show when={props.player?.slug}>
        <div class="mt-3 flex min-h-5 items-center text-sm text-gray-600 dark:text-gray-300">
          <Show
            when={profile()}
            fallback={
              <Show when={query.isLoading}>
                <div class="h-4 w-48 animate-pulse rounded bg-gray-200 motion-reduce:animate-none dark:bg-gray-700" />
              </Show>
            }
          >
            <Show when={career().length}>
              <p>
                Career:{" "}
                <For each={career()}>
                  {([n, label], i) => (
                    <>
                      {i() > 0 && " · "}
                      <b>{n}</b> {label}
                    </>
                  )}
                </For>
              </p>
            </Show>
          </Show>
        </div>
      </Show>

      <Show when={props.player?.slug}>
        <PlayerLink
          slug={props.player.slug}
          from={props.from}
          class="mt-4 flex min-h-[48px] touch-manipulation items-center justify-center gap-2 rounded-lg bg-blue-600 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 active:bg-blue-800"
        >
          View full profile <Icon path={chevronRight} class="h-4 w-4" />
        </PlayerLink>
      </Show>
    </Modal>
  );
};

export default QuickLook;
