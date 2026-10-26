import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { trophy, userGroup } from "solid-heroicons/solid";
import {
  createEffect,
  createMemo,
  createSignal,
  For,
  on,
  Show
} from "solid-js";

import { PlayerLink } from "../../playerLinks";
import {
  fetchTeamProfile,
  fetchUser,
  teamProfileQueryKey
} from "../../queries";
import ErrorAlert from "../alerts/Error";
import Breadcrumbs from "../Breadcrumbs";
import Modal from "../Modal";
import ShareButton from "../player-profile/ShareButton";
import HeadToHead from "../team-profile/HeadToHead";
import Leaders from "../team-profile/Leaders";
import RecentForm from "../team-profile/RecentForm";
import SeasonRoster from "../team-profile/SeasonRoster";
import TeamHero from "../team-profile/TeamHero";
import TeamProfileSkeleton from "../team-profile/TeamProfileSkeleton";
import TeamStats from "../team-profile/TeamStats";
import TeamTournamentCard from "../team-profile/TeamTournamentCard";
import EditTeamNameForm from "./EditTeamNameForm";

const FIRST_SHOWN = 6;

const primary =
  "inline-flex min-h-[44px] items-center rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 active:bg-blue-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900";

const secondary =
  "inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm ring-1 ring-gray-200 transition duration-200 hover:bg-gray-100 active:bg-gray-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:bg-gray-700 dark:text-gray-200 dark:ring-gray-600 dark:hover:bg-gray-600";

const NotFound = () => (
  <div class="flex flex-col items-center px-6 py-16 text-center">
    <div
      aria-hidden="true"
      class="bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-5xl font-extrabold text-transparent"
    >
      404
    </div>
    <h1 class="mt-3 font-medium text-gray-800 dark:text-gray-100">
      We couldn&apos;t find that team
    </h1>
    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
      The link may be old or mistyped.
    </p>
    <A href="/teams" class={`mt-5 ${primary}`}>
      Browse teams
    </A>
  </div>
);

const EditNameModal = props => {
  let modalRef;
  return (
    <>
      <button
        type="button"
        onClick={() => modalRef.showModal()}
        class={secondary}
      >
        Edit name
      </button>
      <Modal
        ref={modalRef}
        title={<span class="text-md font-semibold">Edit name</span>}
        close={() => modalRef.close()}
      >
        {props.children}
      </Modal>
    </>
  );
};

const View = () => {
  const params = useParams();

  const query = createQuery(
    () => teamProfileQueryKey(params.slug),
    () => fetchTeamProfile(params.slug)
  );
  const userQuery = createQuery(() => ["me"], fetchUser);

  const [showAll, setShowAll] = createSignal(false);
  createEffect(
    on(
      () => params.slug,
      () => setShowAll(false),
      { defer: true }
    )
  );
  const tournaments = () => query.data?.tournaments ?? [];
  const visible = () =>
    showAll() ? tournaments() : tournaments().slice(0, FIRST_SHOWN);
  const hidden = () => tournaments().length - visible().length;
  const yearOf = t => Number(t.start_date.slice(0, 4));
  const years = createMemo(() => [...new Set(visible().map(yearOf))]);
  const showEarlier = () => {
    setShowAll(true);
    queueMicrotask(() => document.querySelector("[data-first-new] a")?.focus());
  };
  const isAdmin = () =>
    userQuery.isSuccess &&
    userQuery.data?.admin_teams?.some(team => team.id === query.data?.id);
  const hasLeaders = team =>
    Object.values(team.leaders).some(list => list.length);

  return (
    <Show
      when={!query.isError || query.error?.status !== 404}
      fallback={<NotFound />}
    >
      <Show
        when={query.data}
        fallback={
          <Show when={query.isError} fallback={<TeamProfileSkeleton />}>
            <div class="mx-auto max-w-xl py-10">
              <ErrorAlert text="We couldn't load this team. Check your connection and try again." />
              <button
                type="button"
                onClick={() => query.refetch()}
                class={primary}
              >
                Try again
              </button>
            </div>
          </Show>
        }
      >
        {team => (
          <div class="mx-auto max-w-5xl pb-10">
            <Breadcrumbs
              icon={userGroup}
              pageList={[
                { url: "/teams", name: "Teams" },
                { name: team().name }
              ]}
            />

            <TeamHero
              team={team()}
              isAdmin={isAdmin()}
              actions={
                <>
                  <EditNameModal>
                    <EditTeamNameForm
                      teamId={team().id}
                      teamName={team().name}
                    />
                  </EditNameModal>
                  <A href={`/team/${params.slug}/edit`} class={secondary}>
                    Edit details
                  </A>
                </>
              }
            />
            <TeamStats team={team()} />
            <RecentForm form={team().form} />

            <Show when={team().roster || hasLeaders(team())}>
              <div class="mt-7 grid gap-7 md:grid-cols-2 md:items-start md:gap-6">
                <Show when={team().roster}>
                  <SeasonRoster roster={team().roster} team={team()} />
                </Show>
                <Leaders leaders={team().leaders} team={team()} />
              </div>
            </Show>

            <Show
              when={tournaments().length}
              fallback={
                <div class="mt-6 rounded-xl border border-dashed border-gray-300 p-6 text-center dark:border-gray-600">
                  <Icon
                    class="mx-auto h-8 w-8 text-gray-300 dark:text-gray-600"
                    path={trophy}
                  />
                  <p class="mt-2 font-medium text-gray-700 dark:text-gray-200">
                    No tournaments yet
                  </p>
                  <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Tournaments {team().name} plays on the hub will show up
                    here.
                  </p>
                </div>
              }
            >
              <section aria-labelledby="history-heading">
                <h2
                  id="history-heading"
                  class="mt-7 text-lg font-bold text-gray-900 dark:text-white"
                >
                  Tournament history
                </h2>
                <For each={years()}>
                  {year => (
                    <>
                      <h3 class="mt-4 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300">
                        {year}
                      </h3>
                      <div class="mt-2 grid gap-3 md:grid-cols-2 md:gap-4">
                        <For each={visible().filter(t => yearOf(t) === year)}>
                          {t => (
                            <TeamTournamentCard
                              tournament={t}
                              team={team()}
                              firstNew={t === tournaments()[FIRST_SHOWN]}
                            />
                          )}
                        </For>
                      </div>
                    </>
                  )}
                </For>
                <Show when={hidden() > 0}>
                  <button
                    type="button"
                    onClick={showEarlier}
                    class="mt-5 flex min-h-[44px] w-full items-center justify-center gap-1 rounded-xl border border-dashed border-gray-300 py-3 text-sm font-medium text-blue-700 transition duration-200 hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 active:bg-gray-100 dark:border-gray-600 dark:text-blue-400 dark:hover:bg-gray-800"
                  >
                    Show {hidden()} earlier{" "}
                    {hidden() === 1 ? "tournament" : "tournaments"}
                  </button>
                </Show>
              </section>
            </Show>

            <HeadToHead rivals={team().rivals} />

            <Show when={team().admins.length}>
              <div class="mt-7 flex flex-wrap items-center gap-x-1 text-sm text-gray-600 dark:text-gray-300">
                <span>{team().admins.length === 1 ? "Admin" : "Admins"}:</span>
                <ul role="list" class="flex flex-wrap">
                  <For each={team().admins}>
                    {admin => (
                      <li class="after:mr-1 after:content-[','] last:after:content-none">
                        <PlayerLink
                          slug={admin.slug}
                          from={{ label: team().name }}
                          class="inline-flex min-h-[44px] items-center rounded font-medium text-gray-900 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:text-white"
                        >
                          {admin.full_name}
                        </PlayerLink>
                      </li>
                    )}
                  </For>
                </ul>
              </div>
            </Show>

            <ShareButton name={team().name} label="Share team" />
          </div>
        )}
      </Show>
    </Show>
  );
};

export default View;
