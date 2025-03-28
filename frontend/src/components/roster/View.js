import { A, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { star, trophy } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";

import {
  fetchTeamBySlug,
  fetchTournamentBySlug,
  fetchTournamentTeamBySlugV2,
  fetchTournamentTeamPointsBySlugV2,
  removeFromRoster,
  updatePlayerRegistration
} from "../../queries";
import { useStore } from "../../store";
import { getTournamentBreadcrumbName } from "../../utils";
import { ifTodayInBetweenDates } from "../../utils";
import Info from "../alerts/Info";
import Warning from "../alerts/Warning";
import Breadcrumbs from "../Breadcrumbs";
import ErrorPopover from "../popover/ErrorPopover";
import SuccessPopover from "../popover/SuccessPopover";
import AddToRoster from "./AddToRoster";
import Registration from "./Registration";

const Roster = () => {
  let successPopoverRef, errorPopoverRef;
  const [editStatus, setEditStatus] = createSignal("");

  const queryClient = useQueryClient();

  const params = useParams();
  const [store] = useStore();

  const tournamentQuery = createQuery(
    () => ["tournaments", params.tournament_slug],
    () => fetchTournamentBySlug(params.tournament_slug)
  );

  const teamQuery = createQuery(
    () => ["teams", params.team_slug],
    () => fetchTeamBySlug(params.team_slug)
  );

  const rosterQuery = createQuery(
    () => ["tournament-roster", params.tournament_slug, params.team_slug],
    () => fetchTournamentTeamBySlugV2(params.tournament_slug, params.team_slug)
  );

  const rosterPointsQuery = createQuery(
    () => [
      "tournament-roster-points",
      params.tournament_slug,
      params.team_slug
    ],
    () =>
      fetchTournamentTeamPointsBySlugV2(
        params.tournament_slug,
        params.team_slug
      )
  );

  const removeFromRosterMutation = createMutation({
    mutationFn: removeFromRoster,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournament-roster"] })
  });

  const updateRegistrationMutation = createMutation({
    mutationFn: updatePlayerRegistration,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournament-roster"] })
  });

  createEffect(function onMutationComplete() {
    if (updateRegistrationMutation.isSuccess) {
      setEditStatus("Successfully edited registration");
      successPopoverRef.showPopover();
    }
    if (updateRegistrationMutation.isError) {
      setEditStatus("Editing registration failed");
      errorPopoverRef.showPopover();
    }
  });

  const currentUserIsTeamAdmin = () =>
    teamQuery.data?.admins.filter(user => user.id === store.data.id).length ==
    1;

  const isPlayer = registration => registration?.is_playing;

  const players = () => rosterQuery.data?.filter(reg => isPlayer(reg));
  const nonPlayers = () => rosterQuery.data?.filter(reg => !isPlayer(reg));

  const isPlayerRegInProgress = () => {
    return ifTodayInBetweenDates(
      Date.parse(tournamentQuery.data?.event?.player_registration_start_date),
      Date.parse(tournamentQuery.data?.event?.player_registration_end_date)
    );
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
        pageList={[
          { url: "/tournaments", name: "All Tournaments" },
          {
            url:
              tournamentQuery.data?.status === "REG" ||
              tournamentQuery.data?.status === "SCH"
                ? `/tournament/${params.tournament_slug}/register`
                : `/tournament/${params.tournament_slug}`,
            name: getTournamentBreadcrumbName(
              tournamentQuery.data?.event?.slug || ""
            )
          }
        ]}
      />

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
          <div class="mt-1 flex w-full gap-2">
            <span class="rounded-md border border-blue-300 bg-blue-100 px-2 py-0.5 text-sm font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-300">
              {teamQuery.data?.category}
            </span>
            <span class="inline-flex items-center rounded-md border border-blue-300 bg-blue-100 px-2 py-0.5 text-sm font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-300">
              <Icon path={star} class="mr-1 h-4" />
              {rosterPointsQuery.data?.points || 0}
            </span>
          </div>
        </div>
      </div>

      <div class="mx-auto mb-2 mt-2 w-full">
        <Show
          when={isPlayerRegInProgress()}
          fallback={<Warning>Player Rostering window is now closed!</Warning>}
        >
          <details class="w-full select-none bg-yellow-50 p-4 text-yellow-800 hover:cursor-pointer">
            <summary class="text-md font-semibold">
              Rostering Guidelines
            </summary>
            <div class="mt-2 space-y-2 text-sm">
              <ul class="list-inside list-disc space-y-1">
                <li>
                  <span>Rostering is open from </span>
                  <span class="inline-flex font-medium">
                    {new Date(
                      Date.parse(
                        tournamentQuery.data?.event
                          ?.player_registration_start_date
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
                        tournamentQuery.data?.event
                          ?.player_registration_end_date
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
                  <span class="font-semibold">Male matching</span> players:{" "}
                  <DisplayRosterLimit
                    min={
                      tournamentQuery.data?.event?.series
                        ?.event_min_players_male
                    }
                    max={
                      tournamentQuery.data?.event?.series
                        ?.event_max_players_male
                    }
                  />
                </li>
                <li>
                  <span class="font-semibold">Female matching</span> players:{" "}
                  <DisplayRosterLimit
                    min={
                      tournamentQuery.data?.event?.series
                        ?.event_min_players_female
                    }
                    max={
                      tournamentQuery.data?.event?.series
                        ?.event_max_players_female
                    }
                  />
                </li>
                <li>
                  <span class="font-semibold">Total</span> players:{" "}
                  <DisplayRosterLimit
                    min={
                      tournamentQuery.data?.event?.series
                        ?.event_min_players_total
                    }
                    max={
                      tournamentQuery.data?.event?.series
                        ?.event_max_players_total
                    }
                  />
                </li>
              </ul>
            </div>
          </details>
          <Show />
        </Show>
      </div>

      <div class="mx-auto max-w-screen-md">
        <div class="mt-6">
          <h4 class="mb-2 text-xl font-bold text-blue-500">Add to Roster</h4>
          <Show
            when={isPlayerRegInProgress()}
            fallback={<Info text="Player Registrations have closed!" />}
          >
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
                  eventId={tournamentQuery.data.event.id}
                  teamId={teamQuery.data.id}
                  tournamentSlug={params.tournament_slug}
                  teamSlug={params.team_slug}
                  isPartOfSeries={
                    tournamentQuery.data?.event?.series ? true : false
                  }
                  playerFee={tournamentQuery.data?.event?.player_fee || 0}
                />
              </Match>
            </Switch>
          </Show>
        </div>
        <div class="mt-4">
          <h4 class="text-xl font-bold text-blue-500">Current Roster</h4>
          <h2 class="my-4 text-lg font-bold underline underline-offset-2">
            Players {`(${players()?.length || "-"})`}
          </h2>
          <Show
            when={players()?.length !== 0}
            fallback={<Info text="No Players in the roster yet" />}
          >
            <div class="w-full divide-y">
              <For each={players()}>
                {registration => (
                  <Registration
                    registration={registration}
                    isTeamAdmin={currentUserIsTeamAdmin()}
                    canRemovePlayer={
                      store.loggedIn &&
                      currentUserIsTeamAdmin() &&
                      isPlayerRegInProgress()
                    }
                    canEditPlayer={store.loggedIn && currentUserIsTeamAdmin()}
                    removeMutation={removeFromRosterMutation}
                    updateMutation={updateRegistrationMutation}
                  />
                )}
              </For>
            </div>
          </Show>
          <h2 class="mb-4 mt-8 text-lg font-bold underline underline-offset-2">
            Non-players {`(${nonPlayers()?.length || "-"})`}
          </h2>
          <Show
            when={nonPlayers()?.length !== 0}
            fallback={<Info text="No Non-Players in the roster yet" />}
          >
            <div class="w-full divide-y">
              <For each={nonPlayers()}>
                {registration => (
                  <Registration
                    registration={registration}
                    isTeamAdmin={currentUserIsTeamAdmin()}
                    canRemovePlayer={
                      store.loggedIn &&
                      currentUserIsTeamAdmin() &&
                      isPlayerRegInProgress()
                    }
                    canEditPlayer={store.loggedIn && currentUserIsTeamAdmin()}
                    removeMutation={removeFromRosterMutation}
                    updateMutation={updateRegistrationMutation}
                  />
                )}
              </For>
            </div>
          </Show>
        </div>
      </div>
      <SuccessPopover ref={successPopoverRef}>
        <span class="font-medium">{editStatus()}</span>
      </SuccessPopover>

      <ErrorPopover ref={errorPopoverRef}>
        <span class="font-medium">{editStatus()}</span>
      </ErrorPopover>
    </Show>
  );
};

const DisplayRosterLimit = props => (
  <Show
    when={props.min === 0 && props.max === 0}
    fallback={
      <>
        <span>
          {props.min}
          (min)
        </span>
        <span> - </span>
        <span>
          {props.max}
          (max)
        </span>
      </>
    }
  >
    <span>0 (Not eligible)</span>
  </Show>
);

export default Roster;
