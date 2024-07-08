import { A, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import clsx from "clsx";
import { trophy } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";

import {
  addTeamRegistration,
  fetchTournamentBySlug,
  fetchUser,
  removeTeamRegistration
} from "../queries";
import Info from "./alerts/Info";
import Warning from "./alerts/Warning";
import Breadcrumbs from "./Breadcrumbs";

const TeamRegistration = () => {
  const queryClient = useQueryClient();

  const params = useParams();

  const tournamentQuery = createQuery(
    () => ["tournaments", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
  const userQuery = createQuery(() => ["me"], fetchUser);

  const registerTeamMutation = createMutation({
    mutationFn: addTeamRegistration,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournaments"] })
  });

  const deRegisterTeamMutation = createMutation({
    mutationFn: removeTeamRegistration,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournaments"] })
  });

  const [registeredTeamIds, setRegisteredTeamIds] = createSignal([]);

  createEffect(() => {
    if (tournamentQuery.status === "success" && !tournamentQuery.data.message) {
      let teamIds = tournamentQuery.data?.teams.map(team => team.id);
      setRegisteredTeamIds(teamIds);
    }
  });

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
        pageList={[{ url: "/tournaments", name: "All Tournaments" }]}
      />

      <h1 class="mb-5 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-2xl font-extrabold text-transparent">
          {tournamentQuery.data?.event?.title}
        </span>
      </h1>

      <div>
        <Show when={tournamentQuery.data?.logo_dark}>
          <div class="flex justify-center">
            <img
              src={tournamentQuery.data?.logo_dark}
              alt="Tournament logo"
              class="lg:1/4 hidden w-3/4 dark:block sm:w-1/2 md:w-2/5"
            />
            <img
              src={tournamentQuery.data?.logo_light}
              alt="Tournament logo"
              class="lg:1/4 block w-3/4 dark:hidden sm:w-1/2 md:w-2/5"
            />
          </div>
        </Show>
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
      </div>

      <div class="mx-auto mb-4 mt-6 w-fit">
        <Warning>
          Registrations open from{" "}
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
        <div class="mt-4">
          <h4 class="mb-4 text-lg font-bold text-blue-500">
            Registered Teams {`(${tournamentQuery.data?.teams.length})`}
          </h4>
          <Show
            when={tournamentQuery.data?.teams.length > 0}
            fallback={<Info text="No team has registered yet!" />}
          >
            <div class="my-6">
              <For each={tournamentQuery.data?.teams}>
                {team => (
                  <div class="mb-4 flex items-center justify-between gap-x-4 border-b pb-4">
                    <div class="flex items-center gap-x-4">
                      <img
                        src={team.image ?? team.image_url}
                        class="h-8 w-8 rounded-full"
                      />
                      <span class="font-medium">
                        {team.name}
                        {" ("}
                        {tournamentQuery.data?.reg_count.filter(
                          reg => reg.team_id === team.id
                        )[0].count || "-"}
                        {")"}
                      </span>
                    </div>
                    <div class="justify-self-end">
                      <A
                        href={`/tournament/${params.slug}/team/${team.slug}/roster`}
                        class={clsx(
                          "inline-flex items-center rounded-lg px-4 py-2 text-sm font-medium  focus:outline-none focus:ring-4",
                          userQuery.data?.admin_teams
                            .map(team => team.id)
                            .includes(team.id) &&
                            tournamentQuery.data?.status === "REG"
                            ? "bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                            : "border  border-blue-700 bg-transparent text-blue-600 hover:bg-blue-600 focus:ring-blue-300 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                        )}
                      >
                        <span class="self-center">
                          {userQuery.data?.admin_teams
                            .map(team => team.id)
                            .includes(team.id) &&
                          tournamentQuery.data?.status === "REG"
                            ? "Edit Roster"
                            : "View Roster"}
                        </span>
                      </A>
                    </div>
                  </div>
                )}
              </For>
            </div>
          </Show>
        </div>

        <div class="mt-4">
          <h4 class="mb-4 text-lg font-bold text-blue-500">
            Register your team(s)
          </h4>
          <Show
            when={tournamentQuery.data?.status == "REG"}
            fallback={<Info text="Registrations has closed !" />}
          >
            <Switch>
              <Match when={!userQuery.isSuccess}>
                <Info text="You must be logged in to register teams !" />
              </Match>
              <Match
                when={
                  userQuery.isSuccess &&
                  (!userQuery.data.admin_teams ||
                    userQuery.data.admin_teams?.length == 0)
                }
              >
                <Info text="You must be an admin of a team to register !" />
              </Match>
              <Match
                when={
                  userQuery.isSuccess && userQuery.data.admin_teams?.length > 0
                }
              >
                <div class="my-6">
                  <For each={userQuery.data.admin_teams}>
                    {team => (
                      <div class="mb-4 flex items-center justify-between gap-x-4 border-b border-gray-400/50 pb-4">
                        <div class="flex items-center gap-x-4">
                          <img
                            src={team.image ?? team.image_url}
                            class="h-8 w-8 rounded-full"
                          />
                          <span class="font-medium">{team.name}</span>
                        </div>
                        <Show when={registeredTeamIds().includes(team.id)}>
                          <button
                            type="button"
                            class={clsx(
                              "justify-self-end rounded-lg px-4 py-2 text-sm font-medium text-white focus:outline-none focus:ring-4",
                              "bg-red-500 hover:bg-red-600 focus:ring-red-300 dark:bg-red-600 dark:hover:bg-red-700 dark:focus:ring-red-800"
                            )}
                            onClick={() =>
                              deRegisterTeamMutation.mutate({
                                tournament_id: tournamentQuery.data?.id,
                                body: {
                                  team_id: team.id
                                }
                              })
                            }
                          >
                            De-register
                          </button>
                        </Show>
                        <Show when={!registeredTeamIds().includes(team.id)}>
                          <button
                            type="button"
                            class={clsx(
                              "justify-self-end rounded-lg px-4 py-2 text-sm font-medium text-white focus:outline-none focus:ring-4",
                              "bg-blue-600  hover:bg-blue-700 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                            )}
                            onClick={() =>
                              registerTeamMutation.mutate({
                                tournament_id: tournamentQuery.data?.id,
                                body: {
                                  team_id: team.id
                                }
                              })
                            }
                          >
                            Register
                          </button>
                        </Show>
                      </div>
                    )}
                  </For>
                </div>
              </Match>
            </Switch>
          </Show>
        </div>
      </div>
    </Show>
  );
};

export default TeamRegistration;
