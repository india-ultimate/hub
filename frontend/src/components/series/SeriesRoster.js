import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { trophy } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";

import {
  fetchSeriesBySlug,
  fetchSeriesTeamBySlug,
  fetchTeamSeriesInvitationsSent,
  fetchTeamSeriesRoster,
  fetchUser
} from "../../queries";
import { useStore } from "../../store";
import Info from "../alerts/Info";
import Warning from "../alerts/Warning";
import Breadcrumbs from "../Breadcrumbs";
import AddToRoster from "./AddToRoster";

function groupInvitationsByPlayerId(invitations) {
  let groupedInvitations = {};

  for (let invitation of invitations) {
    const playerId = invitation.to_player?.id;
    if (!Object.keys(groupedInvitations).includes(playerId)) {
      groupedInvitations[playerId] = [];
    }
    groupedInvitations[playerId].push(invitation);
  }
  // Object.groupBy not widely available yet
  // return Object.groupBy(invitations, invitation => playerId);
  return groupedInvitations;
}

const SeriesRoster = props => {
  const params = useParams();
  const [store] = useStore();
  const [latestInvitationsPerPlayer, setLatestInvitationsPerPlayer] =
    createSignal([]);
  const [numPendingInvitations, setNumPendingInvitations] =
    createSignal(undefined);

  const seriesQuery = createQuery(
    () => ["series", params.series_slug],
    () => fetchSeriesBySlug(params.series_slug)
  );
  const teamQuery = createQuery(
    () => ["team", params.team_slug],
    () => fetchSeriesTeamBySlug(params.series_slug, params.team_slug)
  );

  const rosterQuery = createQuery(
    () => ["series-roster", params.series_slug, params.team_slug],
    () => fetchTeamSeriesRoster(params.series_slug, params.team_slug)
  );

  const userQuery = createQuery(() => ["me"], fetchUser);

  const rosterInvitationsQuery = createQuery(
    () => ["series-invitations-sent", params.series_slug, params.team_slug],
    () => fetchTeamSeriesInvitationsSent(params.series_slug, params.team_slug)
  );

  createEffect(() => {
    if (rosterInvitationsQuery.isSuccess) {
      const grouped = groupInvitationsByPlayerId(rosterInvitationsQuery.data);
      let latestInvitations = [];
      let pendingInvitations = 0;

      for (let [_, invitations] of Object.entries(grouped)) {
        let latestTimeStamp = new Date(Date.parse(invitations[0].created_at));
        let latestInvitationIdx = 0;

        for (const [idx, invitation] of invitations.entries()) {
          const timestamp = new Date(Date.parse(invitation.created_at));
          if (timestamp > latestTimeStamp) {
            latestTimeStamp = timestamp;
            latestInvitationIdx = idx;
          }
        }

        latestInvitations.push(invitations[latestInvitationIdx]);
        if (invitations[latestInvitationIdx].status === "Pending") {
          pendingInvitations++;
        }
      }

      setLatestInvitationsPerPlayer(latestInvitations);
      setNumPendingInvitations(pendingInvitations);
    }
  });

  const currentUserIsTeamAdmin = () =>
    teamQuery.data?.admins.map(user => user.id).includes(userQuery.data?.id);

  return (
    <Switch>
      <Match when={seriesQuery.isLoading}>Fetching series...</Match>
      <Match when={seriesQuery.isError}>
        <div>
          <div>Series could not be fetched.</div>
          Error -{" "}
          <span class="text-red-500">
            {seriesQuery.error?.message || teamQuery.error?.message}
          </span>
          <A href={"/series"} class="text-blue-600 dark:text-blue-500">
            <br />
            Back to Series page
          </A>
        </div>
      </Match>
      <Match when={seriesQuery.isSuccess}>
        <Breadcrumbs
          icon={trophy}
          pageList={[
            { url: "/series", name: "All Series" },
            {
              url: `/series/${params.series_slug}`,
              name: seriesQuery.data?.slug || ""
            }
          ]}
        />
        {/* <h1 class="mb-5 text-center">
            <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-2xl font-extrabold text-transparent">
              {seriesQuery.data?.name}
            </span>
          </h1> */}
        {/* <div class="flex justify-center">
            <img
              class="mr-3 inline-block h-24 w-24 rounded-full p-1 ring-2 ring-gray-300 dark:ring-blue-500"
              src={teamQuery.data?.image ?? teamQuery.data?.image_url}
              alt="Bordered avatar"
            />
          </div>
          <div class="mt-4 text-center text-lg font-bold">
            {teamQuery.data?.name}
          </div>
          <div class="text-center text-sm">
            {(teamQuery.data?.city || "") +
              ", " +
              (teamQuery.data?.state_ut || "")}
          </div> */}

        <div class="my-2 flex flex-row items-center justify-start gap-x-6 rounded-xl border border-gray-200 bg-gray-100 p-4">
          <div>
            <img
              class="h-24 w-24 rounded-full p-1 ring-2 ring-gray-300 dark:ring-blue-500"
              src={teamQuery.data?.image ?? teamQuery.data?.image_url}
              alt="Bordered avatar"
            />
          </div>
          <div class="flex flex-col items-start justify-center gap-y-1">
            <div class="text-lg font-bold text-gray-700">
              {teamQuery.data?.name}
            </div>
            <div class="text-md text-right">
              {(teamQuery.data?.city || "") +
                ", " +
                (teamQuery.data?.state_ut || "")}
            </div>
            <div class="mt-1 rounded-md border border-blue-300 bg-blue-100 px-2 py-0.5 text-sm font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-300">
              {teamQuery.data?.category}
            </div>
          </div>
        </div>

        <Warning>
          <ul>
            <li>
              Players can be added <span class="font-semibold">throughout</span>{" "}
              the season, and{" "}
              <span class="inline-block font-semibold">
                cannot be removed once added.
              </span>
            </li>
            <li>
              Series roster limit: {seriesQuery.data?.series_roster_max_players}
            </li>
          </ul>
        </Warning>

        <div class="mx-auto max-w-screen-md">
          <div class="mt-6">
            <h4 class="mb-2 text-xl font-bold text-blue-500">Add to Roster</h4>
            <Switch>
              <Match when={!store.loggedIn}>
                <Info text="You must be logged in to add/remove players from the roster!" />
              </Match>
              <Match
                when={
                  store.loggedIn &&
                  (!teamQuery.data?.admins || !currentUserIsTeamAdmin())
                }
              >
                <Info text="You must be a team admin to perform rostering!" />
              </Match>
              <Match when={store.loggedIn && currentUserIsTeamAdmin()}>
                <AddToRoster
                  roster={rosterQuery.data}
                  invitees={latestInvitationsPerPlayer()}
                  seriesSlug={params.series_slug}
                  teamSlug={params.team_slug}
                />
              </Match>
            </Switch>
          </div>

          {/* Current roster and invites sent */}
          <div class="mx-auto max-w-screen-md">
            <div class="mt-4">
              <h4 class="text-xl font-bold text-blue-500 underline underline-offset-2">
                Current Roster {`(${rosterQuery.data?.length || "-"})`}
              </h4>

              <Show
                when={rosterQuery.data?.length !== 0}
                fallback={<Info text="No Players in the roster yet" />}
              >
                <div class="mt-2 w-full divide-y">
                  <For each={rosterQuery.data}>
                    {registration => (
                      <div
                        class={clsx(
                          "mr-6 flex w-full items-center justify-between space-x-4 py-2 pr-2"
                        )}
                      >
                        <div class="flex items-center gap-x-4">
                          <div class="font-medium">
                            <div>
                              {registration.player?.full_name}
                              <Show
                                when={registration.player?.match_up}
                              >{` (${registration.player?.match_up})`}</Show>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </For>
                </div>
              </Show>
            </div>

            <Show when={store.loggedIn && currentUserIsTeamAdmin()}>
              <div class="mt-4">
                <h4 class="text-xl font-bold text-blue-500 underline underline-offset-2">
                  Invited players {`(${numPendingInvitations() || "-"})`}
                </h4>

                <Show
                  when={latestInvitationsPerPlayer()?.length !== 0}
                  fallback={<Info text="No invitations sent yet" />}
                >
                  <div class="mt-2 w-full divide-y">
                    <For
                      each={latestInvitationsPerPlayer().filter(
                        inv => inv.status !== "Accepted"
                      )}
                    >
                      {invitation => (
                        <div
                          class={clsx(
                            "mr-6 flex w-full items-center justify-between space-x-4 py-2 pr-2"
                          )}
                        >
                          <div class="flex w-full items-center justify-between gap-x-4">
                            <div class="font-medium">
                              {invitation.to_player?.full_name}
                              <Show
                                when={invitation.to_player?.match_up}
                              >{` (${invitation.to_player?.match_up})`}</Show>
                            </div>
                            <div>
                              <Switch>
                                <Match when={invitation.status === "Pending"}>
                                  <span class="me-2 h-fit rounded-full bg-yellow-100 px-2.5 py-0.5 text-center text-sm text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
                                    Pending
                                  </span>
                                </Match>
                                <Match when={invitation.status === "Declined"}>
                                  <span class="me-2 h-fit rounded-full bg-red-100 px-2.5 py-0.5 text-center text-sm text-red-800 dark:bg-red-900 dark:text-red-300">
                                    Declined
                                  </span>
                                </Match>
                                <Match when={invitation.status === "Expired"}>
                                  <span class="me-2 h-fit rounded-full bg-gray-200 px-2.5 py-0.5 text-center text-sm text-gray-800 dark:bg-gray-900 dark:text-gray-300">
                                    Expired
                                  </span>
                                </Match>
                              </Switch>
                            </div>
                          </div>
                        </div>
                      )}
                    </For>
                  </div>
                </Show>
              </div>
            </Show>
          </div>
        </div>
      </Match>
    </Switch>
  );
};

export default SeriesRoster;
