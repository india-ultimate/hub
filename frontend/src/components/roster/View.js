import { A, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import clsx from "clsx";
import { trophy } from "solid-heroicons/solid";
import { For, Match, Show, Switch } from "solid-js";

import {
  fetchTeamBySlug,
  fetchTournamentBySlug,
  fetchTournamentTeamBySlug,
  removeFromRoster
} from "../../queries";
import { useStore } from "../../store";
import Warning from "../alerts/Warning";
import Breadcrumbs from "../Breadcrumbs";
import EditRosteredPlayer from "./EditRosteredPlayer";
import RemoveFromRoster from "./RemoveFromRoster";

const Roster = () => {
  const queryClient = useQueryClient();
  const params = useParams();
  const [store] = useStore();

  const tournamentQuery = createQuery(
    () => ["tournament", params.tournament_slug],
    () => fetchTournamentBySlug(params.tournament_slug)
  );

  const teamQuery = createQuery(
    () => ["team", params.team_slug],
    () => fetchTeamBySlug(params.team_slug)
  );

  const rosterQuery = createQuery(
    () => ["tournament-roster", params.tournament_slug, params.team_slug],
    () => fetchTournamentTeamBySlug(params.tournament_slug, params.team_slug)
  );

  const removeFromRosterMutation = createMutation({
    mutationFn: removeFromRoster,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournament-roster"] })
  });

  const currentUserIsTeamAdmin = () =>
    teamQuery.data?.admins.filter(user => user.id === store.data.id).length ==
    1;

  const isPlayer = registration => registration?.roles?.includes("player");

  const isCaptain = registration =>
    registration?.roles?.includes("captain") ||
    registration?.roles?.includes("Captain");

  const isSpiritCaptain = registration =>
    registration?.roles?.includes("spirit captain") ||
    registration?.roles?.includes("Spirit Captain");

  const isCoach = registration =>
    registration?.roles?.includes("coach") ||
    registration?.roles?.includes("Coach") ||
    registration?.roles?.includes("assistant coach") ||
    registration?.roles?.includes("Assistant Coach");

  const isManager = registration => registration?.roles?.includes("Manager");

  const players = () => rosterQuery.data?.filter(reg => isPlayer(reg));
  const nonPlayers = () => rosterQuery.data?.filter(reg => !isPlayer(reg));

  return (
    <Show
      when={!tournamentQuery.data?.message}
      fallback={
        <div>
          Tournament could not be fetched. Error -{" "}
          {tournamentQuery.data.message}
          <A href={"/tournaments"} class="text-blue-600 dark:text-blue-500">
            <br />
            Back to Tournaments Page
          </A>
        </div>
      }
    >
      <Breadcrumbs
        icon={trophy}
        pageList={[
          { url: "/tournaments", name: "All Tournaments" },
          {
            url:
              tournamentQuery.data?.status === "REG"
                ? `/tournament/${params.tournament_slug}/register`
                : `/tournament/${params.tournament_slug}`,
            name: tournamentQuery.data?.event?.title || ""
          }
        ]}
      />

      <h1 class="mb-5 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-2xl font-extrabold text-transparent">
          {tournamentQuery.data?.event?.title}
        </span>
      </h1>
      {/* 
      <div>
        <p class="mt-2 text-center text-sm">
          {tournamentQuery.data?.event?.location}
        </p>
        <p class="mt-2 text-center text-sm">
          {new Date(
            Date.parse(tournamentQuery.data?.event.start_date)
          ).toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
            timeZone: "UTC"
          })}
          <Show
            when={
              tournamentQuery.data?.event.start_date !==
              tournamentQuery.data?.event.end_date
            }
          >
            {" "}
            to{" "}
            {new Date(
              Date.parse(tournamentQuery.data?.event.end_date)
            ).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
              timeZone: "UTC"
            })}
          </Show>
        </p>
      </div> */}

      <div class="text-center text-lg">{teamQuery.data?.name}</div>

      <div class="mx-auto mb-4 mt-6 w-fit">
        <Warning>
          Rostering open from{" "}
          <span class="inline-flex font-medium">
            {new Date(
              Date.parse(tournamentQuery.data?.event?.registration_start_date)
            ).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
              timeZone: "UTC"
            })}
          </span>{" "}
          to{" "}
          <span class="inline-flex font-medium">
            {new Date(
              Date.parse(tournamentQuery.data?.event?.registration_end_date)
            ).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
              timeZone: "UTC"
            })}
          </span>
        </Warning>
      </div>

      <div class="mx-auto max-w-screen-md">
        <div class="mt-10">
          <h4 class="text-xl font-bold text-blue-500">Add to Roster</h4>
          <Show
            when={tournamentQuery.data?.status == "REG"}
            fallback={
              <p class="mt-4 text-sm italic text-gray-500">
                Registrations have closed !
              </p>
            }
          >
            <Switch>
              <Match when={!store.loggedIn}>
                <p class="mt-4 text-sm italic text-gray-500">
                  You must be logged in to add/remove players from the roster !
                </p>
              </Match>
              <Match
                when={
                  store.loggedIn &&
                  (!teamQuery.data?.admins || !currentUserIsTeamAdmin())
                }
              >
                <p class="mt-4 text-sm italic text-gray-500">
                  You must be a team admin to perform rostering !
                </p>
                <p class="mt-4 text-sm italic text-gray-500">
                  Your team admins are:
                </p>
              </Match>
              <Match when={store.loggedIn && currentUserIsTeamAdmin()}>
                <p class="mt-4 text-sm italic text-gray-500">
                  Rostering here...
                </p>
              </Match>
            </Switch>
          </Show>
        </div>
        <div class="mt-12">
          <h4 class="text-xl font-bold text-blue-500">Current Roster</h4>
          <h2 class="mt-4 text-lg font-bold">Players</h2>
          <Show
            when={players()?.length !== 0}
            fallback={
              <p class="mt-4 text-sm italic text-gray-500">
                0 players in roster yet...
              </p>
            }
          >
            <div
              class={clsx("mt-4", currentUserIsTeamAdmin() ? "divide-y" : "")}
            >
              <For each={players()}>
                {registration => (
                  <div
                    class={clsx(
                      "mr-6 flex w-full items-center justify-between space-x-4 pr-2",
                      currentUserIsTeamAdmin() ? "py-4" : "py-2"
                    )}
                  >
                    <div class="flex items-center gap-x-4">
                      <img
                        class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                        src={registration.person.image_url}
                        alt="Bordered avatar"
                      />
                      <div class="font-medium">
                        <div>
                          {registration.person.first_name +
                            " " +
                            registration.person.last_name}
                          <Show
                            when={registration.person?.player?.gender}
                          >{` (${registration.person?.player?.gender})`}</Show>
                        </div>
                      </div>
                      <Show when={isCaptain(registration)}>
                        <span class="me-2 h-fit rounded-full bg-blue-100 px-2.5 py-0.5 text-xs text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                          Captain
                        </span>
                      </Show>
                      <Show when={isSpiritCaptain(registration)}>
                        <span class="me-2 h-fit rounded-full bg-green-100 px-2.5 py-0.5 text-xs text-green-800 dark:bg-green-900 dark:text-green-300">
                          Spirit Captain
                        </span>
                      </Show>
                      <Show when={isManager(registration)}>
                        <span class="me-2 h-fit rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
                          Manager
                        </span>
                      </Show>
                      <Show when={isCoach(registration)}>
                        <span class="me-2 h-fit rounded-full bg-pink-100 px-2.5 py-0.5 text-xs text-pink-800 dark:bg-pink-900 dark:text-pink-300">
                          Manager
                        </span>
                      </Show>
                    </div>
                    <div class="flex gap-x-3 justify-self-end">
                      <Show when={store.loggedIn && currentUserIsTeamAdmin()}>
                        <RemoveFromRoster
                          regId={registration.id}
                          eventId={tournamentQuery.data.event.id}
                          teamId={registration.team.id}
                          playerName={`${registration.person.first_name} ${registration.person.last_name}`.trim()}
                          removeMutation={removeFromRosterMutation}
                        />
                      </Show>
                      <Show when={store.loggedIn && currentUserIsTeamAdmin()}>
                        <EditRosteredPlayer />
                      </Show>
                    </div>
                  </div>
                )}
              </For>
            </div>
          </Show>
          <h2 class="mt-6 text-lg font-bold">Non-players</h2>
          <Show
            when={nonPlayers()?.length !== 0}
            fallback={
              <p class="mt-4 text-sm italic text-gray-500">
                0 non-players in roster yet...
              </p>
            }
          >
            <div class="mt-4 divide-y">
              <For each={nonPlayers()}>
                {registration => (
                  <div class="mr-6 flex w-full items-center justify-between space-x-4 py-4 pr-2">
                    <div class="flex items-center gap-x-4">
                      <img
                        class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                        src={registration.person.image_url}
                        alt="Bordered avatar"
                      />
                      <div class="font-medium">
                        <div>
                          {registration.person.first_name +
                            " " +
                            registration.person.last_name}
                          <Show
                            when={registration.person?.player?.gender}
                          >{` (${registration.person?.player?.gender})`}</Show>
                        </div>
                      </div>
                      <Show when={isCaptain(registration)}>
                        <span class="me-2 h-fit rounded-full bg-blue-100 px-2.5 py-0.5 text-xs text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                          Captain
                        </span>
                      </Show>
                      <Show when={isSpiritCaptain(registration)}>
                        <span class="me-2 h-fit rounded-full bg-green-100 px-2.5 py-0.5 text-xs text-green-800 dark:bg-green-900 dark:text-green-300">
                          Spirit Captain
                        </span>
                      </Show>
                      <Show when={isManager(registration)}>
                        <span class="me-2 h-fit rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
                          Manager
                        </span>
                      </Show>
                      <Show when={isCoach(registration)}>
                        <span class="me-2 h-fit rounded-full bg-pink-100 px-2.5 py-0.5 text-xs text-pink-800 dark:bg-pink-900 dark:text-pink-300">
                          Manager
                        </span>
                      </Show>
                    </div>
                    <div class="flex gap-x-3 justify-self-end">
                      <Show when={store.loggedIn && currentUserIsTeamAdmin()}>
                        <RemoveFromRoster />
                      </Show>
                      <Show when={store.loggedIn && currentUserIsTeamAdmin()}>
                        <EditRosteredPlayer />
                      </Show>
                    </div>
                  </div>
                )}
              </For>
            </div>
          </Show>
        </div>
      </div>
    </Show>
  );
};

export default Roster;
