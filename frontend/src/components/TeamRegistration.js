import { A, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { trophy } from "solid-heroicons/solid";
import {
  arrowRight,
  bolt,
  checkCircle,
  plus,
  xCircle
} from "solid-heroicons/solid";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";

import {
  addTeamRegistration,
  fetchTournamentBySlug,
  fetchUser,
  removeTeamRegistration
} from "../queries";
import { ifTodayInBetweenDates } from "../utils";
import Info from "./alerts/Info";
import Warning from "./alerts/Warning";
import Breadcrumbs from "./Breadcrumbs";
import Modal from "./Modal";
import ErrorPopover from "./popover/ErrorPopover";
import SuccessPopover from "./popover/SuccessPopover";
import RazorpayPayment from "./RazorpayPayment";

const TeamRegistration = () => {
  const queryClient = useQueryClient();

  const params = useParams();

  const [registeringTeamId, setRegisteringTeamId] = createSignal(undefined);
  const [deRegisteringTeamId, setDeRegisteringTeamId] = createSignal(undefined);
  const [registeredTeamIds, setRegisteredTeamIds] = createSignal([]);
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal({});

  let successPopoverRef, errorPopoverRef, errorModalRef, registerYourTeamRef;

  const tournamentQuery = createQuery(
    () => ["tournaments", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
  const userQuery = createQuery(() => ["me"], fetchUser);

  const registerTeamMutation = createMutation({
    mutationFn: addTeamRegistration,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournaments", params.slug] }),
    onSettled: () => setRegisteringTeamId(undefined)
  });

  const deRegisterTeamMutation = createMutation({
    mutationFn: removeTeamRegistration,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournaments", params.slug] }),
    onSettled: () => setDeRegisteringTeamId(undefined)
  });

  createEffect(() => {
    if (tournamentQuery.status === "success" && !tournamentQuery.data.message) {
      let teamIds = tournamentQuery.data?.teams.map(team => team.id);
      setRegisteredTeamIds(teamIds);
    }
  });

  createEffect(function onMutationComplete() {
    if (registerTeamMutation.isSuccess) {
      setStatus("Registered team");
      successPopoverRef.showPopover();
    }
    if (registerTeamMutation.isError) {
      try {
        const mutationError = JSON.parse(registerTeamMutation.error.message);
        setError(mutationError);
        setStatus(mutationError.message);
        // Show error modal for long errors with a description, possibly an action button also
        if (mutationError.description) {
          errorModalRef.showModal();
        } else {
          errorPopoverRef.showPopover();
        }
      } catch (err) {
        throw new Error(`Couldn't parse error object: ${err}`);
      }
    }
  });

  const scrollToMyTeams = () => registerYourTeamRef.scrollIntoView();

  const isAdminAndPlayerRegInProgress = teamId => {
    return (
      userQuery.data?.admin_teams
        .map(adminTeam => adminTeam.id)
        .includes(teamId) &&
      ifTodayInBetweenDates(
        Date.parse(tournamentQuery.data?.event?.player_registration_start_date),
        Date.parse(tournamentQuery.data?.event?.player_registration_end_date)
      )
    );
  };

  const isTeamFeeExists = () => {
    return tournamentQuery.data?.event?.team_fee > 0;
  };

  const getPlayerFee = event => {
    if (event?.player_fee > 0) {
      return "Rs. " + event?.player_fee / 100 + " per player";
    } else {
      return "Free";
    }
  };

  const getTeamFee = event => {
    if (event?.team_fee > 0) {
      return "Rs. " + event?.team_fee / 100 + " per team";
    } else {
      return "Free";
    }
  };

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
          <span class="mb-2 block font-bold">Registration Details!</span>
          <ul class="max-w-md list-inside list-disc space-y-1">
            <li>
              <strong>Team Registration Fee:</strong>{" "}
              {getTeamFee(tournamentQuery.data?.event)}
            </li>
            <li>
              <strong>Player Registration Fee:</strong>{" "}
              {getPlayerFee(tournamentQuery.data?.event)}
            </li>
            <li>
              Team Registrations window open from{" "}
              <span class="inline-flex font-medium">
                {new Date(
                  Date.parse(
                    tournamentQuery.data?.event?.team_registration_start_date
                  )
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
                  Date.parse(
                    tournamentQuery.data?.event?.team_registration_end_date
                  )
                ).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  timeZone: "UTC"
                })}
              </span>
            </li>
            <li>
              Player Registrations window open from{" "}
              <span class="inline-flex font-medium">
                {new Date(
                  Date.parse(
                    tournamentQuery.data?.event?.player_registration_start_date
                  )
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
                  Date.parse(
                    tournamentQuery.data?.event?.player_registration_end_date
                  )
                ).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  timeZone: "UTC"
                })}
              </span>
            </li>
          </ul>
          {/* <hr class="my-2 h-px border-0 bg-yellow-600 dark:bg-gray-700" /> */}
        </Warning>
      </div>

      <div class="mx-auto max-w-screen-md">
        <div class="mt-4">
          <div class="mb-2 flex items-center justify-between ">
            <h4 class="text-lg font-bold text-blue-500">
              Registered Teams {`(${tournamentQuery.data?.teams.length})`}
            </h4>
            <button
              onClick={scrollToMyTeams}
              class="inline-flex items-center gap-1 text-sm text-blue-600"
            >
              <Icon class="h-4 w-4 text-blue-700" path={plus} />
              Add your team
            </button>
          </div>
          <p class="mb-2 inline-flex items-center">
            <Icon class="h-4 w-4 text-blue-600" path={bolt} /> - Your team
          </p>

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
                      <Show
                        when={userQuery.data?.admin_teams
                          .map(team => team.id)
                          .includes(team.id)}
                      >
                        <Icon class="h-4 w-4 text-blue-600" path={bolt} />
                      </Show>
                    </div>
                    <div class="justify-self-end">
                      <A
                        href={`/tournament/${params.slug}/team/${team.slug}/roster`}
                        class={clsx(
                          "inline-flex items-center rounded-lg px-4 py-2 text-sm font-medium  focus:outline-none focus:ring-4",
                          isAdminAndPlayerRegInProgress(team.id)
                            ? "bg-blue-600 text-white hover:bg-blue-600 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                            : "border  border-blue-700 bg-transparent text-blue-600  focus:ring-blue-300 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                        )}
                      >
                        <span class="self-center">
                          {isAdminAndPlayerRegInProgress(team.id)
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

        <div class="mt-4" ref={registerYourTeamRef}>
          <h4 class="mb-1 text-lg font-bold text-blue-500">
            Register your team(s)
          </h4>
          <A href="/teams" class="mb-4 text-sm underline">
            Click to create, edit or view all teams
          </A>
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
                              "bg-red-500 hover:bg-red-600 focus:ring-red-300 disabled:bg-gray-400 dark:bg-red-600 dark:hover:bg-red-700 dark:focus:ring-red-800"
                            )}
                            disabled={deRegisteringTeamId() === team.id}
                            onClick={() => {
                              deRegisterTeamMutation.mutate({
                                tournament_id: tournamentQuery.data?.id,
                                body: {
                                  team_id: team.id
                                }
                              });
                              setDeRegisteringTeamId(team.id);
                            }}
                          >
                            <Show
                              when={deRegisteringTeamId() === team.id}
                              fallback="Remove"
                            >
                              Removing...
                            </Show>
                          </button>
                        </Show>
                        <Show when={!registeredTeamIds().includes(team.id)}>
                          <Show
                            when={isTeamFeeExists()}
                            fallback={
                              <button
                                type="button"
                                class={clsx(
                                  "justify-self-end rounded-lg px-4 py-2 text-sm font-medium text-white focus:outline-none focus:ring-4",
                                  "bg-blue-600 hover:bg-blue-700 focus:ring-blue-300 disabled:bg-gray-400 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                                )}
                                disabled={registeringTeamId() === team.id}
                                onClick={() => {
                                  registerTeamMutation.mutate({
                                    tournament_id: tournamentQuery.data?.id,
                                    body: {
                                      team_id: team.id
                                    }
                                  });
                                  setRegisteringTeamId(team.id);
                                }}
                              >
                                <Show
                                  when={registeringTeamId() === team.id}
                                  fallback="Register"
                                >
                                  Registering...
                                </Show>
                              </button>
                            }
                          >
                            <RazorpayPayment
                              disabled={!isTeamFeeExists()}
                              event={tournamentQuery.data?.event}
                              team={team}
                              amount={tournamentQuery.data?.event?.team_fee}
                              setStatus={setStatus}
                              successCallback={() =>
                                queryClient.invalidateQueries({
                                  queryKey: ["tournaments", params.slug]
                                })
                              }
                              successPopoverRef={successPopoverRef}
                              errorPopoverRef={errorPopoverRef}
                            />
                          </Show>
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
      <SuccessPopover ref={successPopoverRef}>
        <div class="flex flex-row items-center gap-2">
          <Icon path={checkCircle} class="h-6 w-6 text-green-700" />
          <div class="font-medium">{status()}</div>
        </div>
      </SuccessPopover>

      <ErrorPopover ref={errorPopoverRef}>
        <div class="flex flex-row items-center gap-2">
          <Icon path={xCircle} class="h-6 w-6 text-red-700" />
          <div class="font-medium">{status()}</div>
        </div>
      </ErrorPopover>

      <Modal
        ref={errorModalRef}
        close={() => errorModalRef.close()}
        fullWidth={true}
        title={
          <div class="flex flex-row gap-2">
            <div>
              <Icon path={xCircle} class="inline h-6 w-6 text-red-700" />
            </div>
            <div class="font-medium text-red-700">{status()}</div>
          </div>
        }
      >
        <div class="flex w-full flex-col justify-between gap-4 pb-2">
          <div class="text-gray-600">{error().description}</div>
          <div class="place-self-end">
            <A href={`${error().action_href}`}>
              <button
                type="button"
                class={clsx(
                  "inline-flex w-fit items-center rounded-lg border px-2.5 py-1.5 text-center text-sm font-medium sm:text-base",
                  "border-gray-500 bg-gray-200 text-gray-800 transition-colors hover:bg-gray-500 hover:text-white focus:outline-none focus:ring-4 focus:ring-gray-300"
                )}
              >
                <span class="mr-2">{error().action_name}</span>
                <Icon path={arrowRight} class="h-3 w-3" />
              </button>
            </A>
          </div>
        </div>
      </Modal>
    </Show>
  );
};

export default TeamRegistration;
