import { A, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { envelope, queueList } from "solid-heroicons/outline";
import {
  arrowRight,
  bolt,
  calendarDays,
  link,
  minus,
  plus,
  trophy
} from "solid-heroicons/solid";
import {
  createEffect,
  createSignal,
  For,
  Match,
  Show,
  Suspense,
  Switch
} from "solid-js";

import {
  addTeamSeriesRegistration,
  fetchSeriesBySlug,
  fetchSeriesInvitations,
  fetchUser,
  removeTeamSeriesRegistration
} from "../../queries";
import { displayDateShort } from "../../utils";
import Info from "../alerts/Info";
import Breadcrumbs from "../Breadcrumbs";
import InvitationCard from "./Invitation";

const TeamRow = props => {
  const userIsTeamAdmin = () =>
    props.adminTeams?.map(team => team.id).includes(props.team.id);

  return (
    <div class="flex items-center justify-between gap-x-4 py-4">
      <div class="flex items-center gap-x-2">
        <img
          src={props.team.image ?? props.team.image_url}
          class="mr-2 h-8 w-8 rounded-full"
        />
        <span class="font-semibold">
          {props.team.name} {`(${props.regCount || "-"})`}
        </span>
        <Show when={userIsTeamAdmin()}>
          <Icon class="h-4 w-4 text-blue-600" path={bolt} />
        </Show>
      </div>
      <div class="justify-self-end">
        <A
          href={`/series/${props.seriesSlug}/team/${props.team.slug}`}
          class={clsx(
            "inline-flex items-center rounded-lg px-4 py-2 text-sm font-medium  focus:outline-none focus:ring-4",
            userIsTeamAdmin()
              ? "bg-blue-600 text-white hover:bg-blue-600 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
              : "border border-blue-700 bg-transparent text-blue-600  focus:ring-blue-300 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          )}
        >
          <span class="inline-flex items-center gap-2">
            <span>Roster</span>
            <Icon path={arrowRight} class="inline h-3 w-3" />
          </span>
        </A>
      </div>
    </div>
  );
};

const AdminTeamRow = props => {
  return (
    <div class="flex items-center justify-between gap-x-4 py-4">
      <div class="flex items-center gap-x-2">
        <img
          src={props.team.image ?? props.team.image_url}
          class="mr-2 h-8 w-8 rounded-full"
        />
        <span class="font-medium">{props.team.name}</span>
      </div>
      <div class="justify-self-end">
        <Show when={props.registeredTeamIds.includes(props.team.id)}>
          <button
            type="button"
            class={clsx(
              "justify-self-end rounded-lg px-4 py-2 text-sm font-medium text-white focus:outline-none focus:ring-4",
              "bg-red-500 hover:bg-red-600 focus:ring-red-300 dark:bg-red-600 dark:hover:bg-red-700 dark:focus:ring-red-800"
            )}
            onClick={() =>
              props.deRegisterTeamMutation.mutate({
                series_slug: props.seriesSlug,
                body: {
                  team_slug: props.team.slug
                }
              })
            }
          >
            <span class="inline-flex items-center gap-2">
              <Icon path={minus} class="inline h-3 w-3 text-white" />
              <span>Remove</span>
            </span>
          </button>
        </Show>
        <Show when={!props.registeredTeamIds.includes(props.team.id)}>
          <button
            type="button"
            class={clsx(
              "justify-self-end rounded-lg px-4 py-2 text-sm font-medium text-white focus:outline-none focus:ring-4",
              "bg-blue-600  hover:bg-blue-700 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
            )}
            onClick={() =>
              props.registerTeamMutation.mutate({
                series_slug: props.seriesSlug,
                body: {
                  team_slug: props.team.slug
                }
              })
            }
          >
            <span class="inline-flex items-center gap-2">
              <Icon path={plus} class="inline h-3 w-3 text-white" />
              <span>Register</span>
            </span>
          </button>
        </Show>
      </div>
    </div>
  );
};

const Series = () => {
  const params = useParams();
  const queryClient = useQueryClient();
  let registerYourTeamRef;

  const [registeredTeamIds, setRegisteredTeamIds] = createSignal([]);
  const [flash, setFlash] = createSignal(false);
  const [pendingInvitations, setPendingInvitations] = createSignal([]);

  const seriesQuery = createQuery(
    () => ["series", params.slug],
    () => fetchSeriesBySlug(params.slug)
  );

  const seriesInvitationsQuery = createQuery(
    () => ["my-series-invitations", params.slug],
    () => fetchSeriesInvitations(params.slug)
  );

  const userQuery = createQuery(() => ["me"], fetchUser);

  const registerTeamMutation = createMutation({
    mutationFn: addTeamSeriesRegistration,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["series"] })
  });

  const deRegisterTeamMutation = createMutation({
    mutationFn: removeTeamSeriesRegistration,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["series"] })
  });

  createEffect(() => {
    if (seriesQuery.isSuccess && !seriesQuery.data.message) {
      let teamIds = seriesQuery.data?.teams.map(team => team.id);
      setRegisteredTeamIds(teamIds);
    }
  });

  createEffect(() => {
    if (
      seriesInvitationsQuery.isSuccess &&
      !seriesInvitationsQuery.data.message
    ) {
      setPendingInvitations(
        seriesInvitationsQuery.data.filter(
          invitation => invitation.status === "Pending"
        )
      );
    }
  });

  const scrollToRegisterTeamSection = () => {
    registerYourTeamRef.scrollIntoView();
    setFlash(true);
    setTimeout(() => setFlash(false), 1500);
  };

  return (
    <Switch>
      {/* TODO: page skeleton here */}
      <Match when={seriesQuery.isLoading} />
      <Match when={seriesQuery.isError}>
        <div>
          <div>Series could not be fetched.</div>
          Error - <span class="text-red-500">{seriesQuery.error.message}</span>
          <A href={"/series"} class="text-blue-600 dark:text-blue-500">
            <br />
            Back to Series page
          </A>
        </div>
      </Match>
      <Match when={seriesQuery.isSuccess}>
        <Breadcrumbs
          icon={trophy}
          pageList={[{ url: "/series", name: "All Series" }]}
        />
        <div class="flex flex-col rounded-lg border border-blue-300 bg-blue-50 px-3 pb-3 pt-2">
          <h1 class="select-none sm:text-center">
            <span class="text-2xl font-extrabold text-gray-700">
              {seriesQuery.data?.name}
            </span>
          </h1>
          {/* Dates */}
          <div class="text-md mt-3 flex items-center sm:px-0">
            <Icon
              path={calendarDays}
              class="mr-2 inline h-6 w-6 text-gray-700"
            />
            <span class="mr-1 font-semibold">
              {displayDateShort(seriesQuery.data?.start_date)}
            </span>{" "}
            to{" "}
            <span class="ml-1 font-semibold">
              {displayDateShort(seriesQuery.data?.end_date)}
            </span>
          </div>
          <div class="mt-3 flex items-center">
            <Icon path={link} class="mr-3 h-5 w-5 text-gray-700" />
            <div class="">
              <a
                href="https://docs.google.com/document/d/1Ah_YUt78IKFoPsgCxawuRXAaBS8L5mbD2Lr6FkNux78/"
                class="flex w-fit items-start gap-1 text-blue-500"
              >
                <span class="text-md underline underline-offset-2">
                  Series Rules
                </span>
              </a>
            </div>
          </div>
          {/* Series badges */}
          <div class="mt-5 flex space-x-2">
            <span class="rounded-md border border-blue-300 bg-blue-100 px-2.5 py-0.5 text-sm font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-300">
              {seriesQuery.data?.category}
            </span>
            <Switch>
              <Match when={seriesQuery.data?.type === "Mixed"}>
                <span class="rounded-md border border-yellow-300 bg-yellow-100 px-2.5 py-0.5 text-sm font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
                  Mixed
                </span>
              </Match>
              <Match when={seriesQuery.data?.type === "Opens"}>
                <span class="rounded-md border border-green-300 bg-green-100 px-2.5 py-0.5 text-sm font-medium text-green-800 dark:bg-green-900 dark:text-green-300">
                  Opens
                </span>
              </Match>
              <Match when={seriesQuery.data?.type === "Womens"}>
                <span class="rounded-md border border-purple-300 bg-purple-100 px-2.5 py-0.5 text-sm font-medium text-purple-800 dark:bg-purple-900 dark:text-purple-300">
                  Womens
                </span>
              </Match>
            </Switch>
          </div>
        </div>

        {/* Invitations */}
        <details class="group mt-6 rounded-lg border border-gray-300">
          <summary class="px-3 py-2 group-open:border-b group-open:border-gray-300">
            <div class="flex items-center gap-2 text-gray-600">
              <Icon path={envelope} class="inline h-6 w-6 text-gray-500" />
              <span class="text-lg font-semibold text-gray-700">
                Your Invitations
              </span>

              <Show
                when={
                  seriesInvitationsQuery.isSuccess &&
                  pendingInvitations().length !== 0
                }
              >
                <span class="relative flex h-2.5 w-2.5">
                  <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                  <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-green-500" />
                </span>
              </Show>
            </div>
          </summary>
          <Switch>
            <Match when={seriesInvitationsQuery.isLoading}>
              {/* Invitations skeleton here */}
            </Match>
            <Match when={seriesInvitationsQuery.isError}>
              <div class="m-2">
                <Info text="You must be logged in to view invitations !" />
              </div>
            </Match>
            <Match
              when={
                seriesInvitationsQuery.isSuccess &&
                pendingInvitations().length == 0
              }
            >
              <Info text="You don't have pending invitations" />
            </Match>
            <Match
              when={
                seriesInvitationsQuery.isSuccess &&
                pendingInvitations().length !== 0
              }
            >
              <div class="space-y-2 px-3 py-2">
                <For each={pendingInvitations()}>
                  {invitation => (
                    <InvitationCard
                      invitation={invitation}
                      seriesSlug={params.slug}
                    />
                  )}
                </For>
              </div>
            </Match>
          </Switch>
        </details>

        {/* Teams registered */}
        <details class="group mt-6 rounded-lg border border-gray-300" open>
          <summary class="px-3 py-2 group-open:border-b group-open:border-gray-300">
            <div class="flex items-center gap-2 text-gray-600">
              <span>
                <Icon path={queueList} class="inline h-6 w-6 text-gray-500" />
              </span>
              <span class="inline-flex items-center space-x-1 font-semibold text-gray-700">
                <span class="text-lg">Registered teams</span>
                <span class="text-md font-semibold">
                  ({seriesQuery.data.teams.length})
                </span>
              </span>
            </div>
          </summary>
          <div>
            <button
              onClick={scrollToRegisterTeamSection}
              class={clsx(
                "text-md flex w-full items-center justify-start gap-2 px-4 py-4 font-medium",
                "border-b border-gray-300 bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300"
              )}
            >
              <Icon class="inline h-5 w-5" path={plus} />
              <span>Add your team</span>
            </button>
            <div class="divide-y divide-gray-300 px-3 py-2">
              <For each={seriesQuery.data.teams}>
                {team => (
                  <TeamRow
                    team={team}
                    adminTeams={userQuery.data?.admin_teams}
                    seriesSlug={params.slug}
                    regCount={
                      seriesQuery.data?.reg_count.filter(
                        reg => reg.team_id === team.id
                      )[0].count
                    }
                  />
                )}
              </For>
            </div>
          </div>
        </details>

        {/* Register your team */}
        <details
          open
          ref={registerYourTeamRef}
          class="group mt-6 scroll-mt-6 rounded-lg border border-gray-300"
        >
          <summary
            class={clsx(
              "rounded-lg px-3 py-2 group-open:rounded-b-none group-open:border-b group-open:border-gray-300",
              flash() ? "bg-green-100 text-black" : ""
            )}
          >
            <div class="flex items-center gap-2 text-gray-600">
              <Icon path={queueList} class="inline h-6 w-6 text-gray-500" />
              <span class="flex items-center font-semibold text-gray-700">
                <span class="text-lg">Register your team</span>
                <span class="text-md ml-0.5">(s)</span>
              </span>
            </div>
          </summary>
          <Switch>
            {/* skeleton here */}
            {/* <Match when={userQuery.isLoading && !userQuery.isRefetching}>
              <div class="m-2 h-6 rounded-md bg-gray-200 dark:bg-gray-700 animate-pulse" />
            </Match> */}
            <Match when={userQuery.isError}>
              <div class="m-2">
                <Info text="You must be logged in to register teams !" />
              </div>
            </Match>
            <Match
              when={
                userQuery.isSuccess &&
                (!userQuery.data.admin_teams ||
                  userQuery.data.admin_teams?.length == 0)
              }
            >
              <div class="m-2">
                <Info text="You must be an admin of a team to register !" />
              </div>
            </Match>
            <Match
              when={
                userQuery.isSuccess && userQuery.data.admin_teams?.length !== 0
              }
            >
              <A href="/teams">
                <div
                  class={clsx(
                    "text-md flex w-full items-center justify-start gap-2 px-4 py-4 font-medium underline",
                    "border-b border-gray-300 bg-gray-100 text-gray-800 "
                  )}
                >
                  Click to create, edit or view all teams
                  <Icon class="inline h-4 w-4" path={arrowRight} />
                </div>
              </A>
              <div class="divide-y divide-gray-300 px-3 py-2">
                <Suspense
                  fallback={
                    <div class="m-2 h-6 animate-pulse rounded-md bg-gray-200 dark:bg-gray-700" />
                  }
                >
                  <For each={userQuery.data.admin_teams}>
                    {team => (
                      <AdminTeamRow
                        team={team}
                        seriesSlug={params.slug}
                        registerTeamMutation={registerTeamMutation}
                        deRegisterTeamMutation={deRegisterTeamMutation}
                        registeredTeamIds={registeredTeamIds()}
                      />
                    )}
                  </For>
                </Suspense>
              </div>
            </Match>
          </Switch>
        </details>
      </Match>
    </Switch>
  );
};

export default Series;
