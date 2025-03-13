import { A } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import {
  createSolidTable,
  flexRender,
  getCoreRowModel
} from "@tanstack/solid-table";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { handRaised } from "solid-heroicons/outline";
import {
  arrowRight,
  checkCircle,
  plus,
  xCircle,
  xMark
} from "solid-heroicons/solid";
import {
  createEffect,
  createSignal,
  For,
  Match,
  onCleanup,
  Show,
  Switch
} from "solid-js";

import { ChevronLeft, ChevronRight, Spinner } from "../../icons";
import {
  fetchUser,
  getRecommendedPlayers,
  invitePlayerToSeries,
  registerYourselfToSeries,
  searchPlayers
} from "../../queries";
import Info from "../alerts/Info";
import Modal from "../Modal";
import ErrorPopover from "../popover/ErrorPopover";
import SuccessPopover from "../popover/SuccessPopover";

const AddToRoster = props => {
  let modalRef;
  let successPopoverRef, errorPopoverRef, errorModalRef;
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal({});

  const queryClient = useQueryClient();
  const userQuery = createQuery(() => ["me"], fetchUser);

  const registerYourselfMutation = createMutation({
    mutationFn: registerYourselfToSeries,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["series-roster"] })
  });

  createEffect(function onMutationComplete() {
    if (registerYourselfMutation.isSuccess) {
      setStatus("Added player to series roster");
      successPopoverRef.showPopover();
    }
    if (registerYourselfMutation.isError) {
      try {
        const mutationError = JSON.parse(
          registerYourselfMutation.error.message
        );
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

  return (
    <div class="mt-4 flex justify-center gap-2">
      <Show
        when={
          !props.roster
            ?.map(reg => reg.player.id)
            .includes(userQuery.data?.player?.id)
        }
      >
        <button
          onClick={() => {
            registerYourselfMutation.mutate({
              series_slug: props.seriesSlug,
              team_slug: props.teamSlug
            });
          }}
          type="button"
          class="mb-2 me-2 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-blue-700 px-2 py-2.5 text-center text-sm font-medium text-blue-700 hover:bg-blue-800 hover:text-white focus:outline-none dark:border-blue-500  dark:text-blue-500 dark:hover:bg-blue-500 dark:hover:text-white dark:focus:ring-blue-800 md:px-5"
        >
          <Icon path={handRaised} style={{ width: "24px" }} />
          <span class="w-3/4">Add myself</span>
        </button>
      </Show>

      <button
        onClick={() => modalRef.showModal()}
        type="button"
        class="mb-2 me-2 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-2 py-2.5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 md:px-5"
      >
        <Icon path={plus} style={{ width: "24px" }} />
        <span class="w-3/4">Invite a player</span>
      </button>
      <Modal
        ref={modalRef}
        title={<span class="font-bold">Adding a new player to the roster</span>}
        close={() => modalRef.close()}
      >
        <AddPlayerRegistrationForm
          roster={props.roster}
          invitees={props.invitees}
          seriesSlug={props.seriesSlug}
          teamSlug={props.teamSlug}
        />
      </Modal>
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
    </div>
  );
};

const AddPlayerRegistrationForm = componentProps => {
  const [search, setSearch] = createSignal("");
  const [pagination, setPagination] = createSignal({
    pageIndex: 0,
    pageSize: 5
  });
  const [recommendedPagination, setRecommendedPagination] = createSignal({
    pageIndex: 0,
    pageSize: 5
  });
  const [status, setStatus] = createSignal("");

  const queryClient = useQueryClient();

  // Shared helper functions for checking roster status
  const isPlayerInRoster = playerId => {
    return componentProps.roster?.map(reg => reg.player.id).includes(playerId);
  };

  const isPlayerInvited = playerId => {
    return componentProps.invitees
      .filter(invite => invite.to_player.id === playerId)
      .map(invite => invite.status)
      .includes("Pending");
  };

  const invitePlayerMutation = createMutation({
    mutationFn: invitePlayerToSeries,
    onSuccess: () => {
      queryClient.invalidateQueries(["series-invitations-sent"]);
      queryClient.invalidateQueries(["recommended-players"]);
      queryClient.invalidateQueries(["players", "search"]);
    }
  });

  createEffect(function onMutationComplete() {
    if (invitePlayerMutation.isSuccess) {
      setStatus("✅ Invited player to the roster");
    }
    if (invitePlayerMutation.isError) {
      setStatus(
        `❌ Adding to the roster failed: ${invitePlayerMutation.error.message}`
      );
    }
  });

  onCleanup(() => setStatus(""));

  const dataQuery = createQuery(
    () => ["players", "search", search(), pagination()],
    () =>
      search().trim().length > 2 ? searchPlayers(search(), pagination()) : []
  );

  const recommendedPlayersQuery = createQuery(
    () => [
      "recommended-players",
      componentProps.teamSlug,
      recommendedPagination()
    ],
    () =>
      getRecommendedPlayers(componentProps.teamSlug, recommendedPagination())
  );

  createEffect(() => {
    if (search()) {
      setPagination({
        pageIndex: 0,
        pageSize: 5
      });
    }
  });

  const defaultColumns = [
    {
      accessorKey: "full_name",
      id: "full_name",
      header: () => <span>Player Name</span>,
      cell: props => (
        <div>
          <div class="font-medium">{props.getValue()}</div>
          <div class="flex flex-wrap">
            <For each={props.row.original.teams}>
              {team => (
                <span class="my-2 me-2 rounded bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                  {team.name}
                </span>
              )}
            </For>
          </div>
        </div>
      )
    },
    {
      accessorKey: "id",
      id: "actions",
      header: () => <span>Actions</span>,
      cell: props => (
        <Switch>
          <Match when={isPlayerInRoster(props.getValue())}>
            <span class="inline-flex items-center rounded-md bg-green-50 px-2 py-1 text-sm font-medium text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-900/30 dark:text-green-400">
              Added to roster
            </span>
          </Match>
          <Match when={isPlayerInvited(props.getValue())}>
            <span class="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-sm font-medium text-yellow-700 ring-1 ring-inset ring-yellow-600/20 dark:bg-yellow-900/30 dark:text-yellow-400">
              Invited
            </span>
          </Match>
          <Match
            when={
              !isPlayerInRoster(props.getValue()) &&
              !isPlayerInvited(props.getValue())
            }
          >
            <button
              onClick={() =>
                invitePlayerMutation.mutate({
                  series_slug: componentProps.seriesSlug,
                  team_slug: componentProps.teamSlug,
                  body: {
                    to_player_id: props.getValue()
                  }
                })
              }
              disabled={invitePlayerMutation.isLoading}
              class="mb-2 me-2 rounded-lg border border-blue-700 px-5 py-1.5 text-center text-sm font-medium text-blue-700 hover:bg-blue-800 hover:text-white disabled:text-blue-400"
            >
              <Show
                when={!invitePlayerMutation.isLoading}
                fallback={"Loading..."}
              >
                Invite
              </Show>
            </button>
          </Match>
        </Switch>
      )
    }
  ];

  const table = createSolidTable({
    get data() {
      return dataQuery.data?.items ?? [];
    },
    columns: defaultColumns,
    get rowCount() {
      return dataQuery.data?.count;
    },
    get state() {
      return {
        get pagination() {
          return pagination();
        }
      };
    },
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true
  });

  const recommendedPlayersTable = createSolidTable({
    get data() {
      return recommendedPlayersQuery.data?.items ?? [];
    },
    columns: defaultColumns,
    get rowCount() {
      return recommendedPlayersQuery.data?.count;
    },
    get state() {
      return {
        get pagination() {
          return recommendedPagination();
        }
      };
    },
    onPaginationChange: setRecommendedPagination,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true
  });

  return (
    <div class="h-screen w-full rounded-lg p-2">
      <h2 class="w-full text-left text-lg font-bold text-blue-600">
        Add Players to Roster
      </h2>
      <h3 class="w-full text-left text-sm italic">
        Search players by name or email (min. 3 letters)
      </h3>
      <div class="relative my-4 w-full">
        <div class="pointer-events-none absolute inset-y-0 start-0 flex items-center ps-3">
          <svg
            class="h-4 w-4 text-gray-500 dark:text-gray-400"
            aria-hidden="true"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 20 20"
          >
            <path
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="m19 19-4-4m0-7A7 7 0 1 1 1 8a7 7 0 0 1 14 0Z"
            />
          </svg>
        </div>
        <input
          type="search"
          id="player-search"
          class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-4 ps-10 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          placeholder="Player Name / Email"
          required
          value={search()}
          onChange={e => {
            setSearch(e.target.value);
          }}
        />
        <button
          type="button"
          onClick={() => setSearch("")}
          class="absolute bottom-2.5 end-24 rounded-full px-2 py-2 text-sm font-medium text-gray-400 hover:text-gray-700 focus:outline-none "
        >
          <Icon path={xMark} style={{ width: "20px" }} />
        </button>
        <button
          type="submit"
          class="absolute bottom-2.5 end-2.5 rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
        >
          Search
        </button>
      </div>

      <Show
        when={table.getRowModel().rows.length > 0}
        fallback={
          <div>
            <Show
              when={dataQuery.isLoading}
              fallback={
                <Info
                  text={
                    search().trim().length > 2
                      ? "No players found."
                      : "Please enter min. 3 letters to search"
                  }
                />
              }
            >
              <Spinner />
            </Show>
          </div>
        }
      >
        <table class="w-full text-left text-sm text-gray-500 rtl:text-right dark:text-gray-400">
          <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
            <For each={table.getHeaderGroups()}>
              {headerGroup => (
                <tr>
                  <For each={headerGroup.headers}>
                    {header => {
                      return (
                        <th colSpan={header.colSpan} class="px-6 py-3">
                          {header.isPlaceholder ? null : (
                            <div>
                              {flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                            </div>
                          )}
                        </th>
                      );
                    }}
                  </For>
                </tr>
              )}
            </For>
          </thead>
          <tbody>
            <For each={table.getRowModel().rows}>
              {row => {
                return (
                  <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                    <For each={row.getVisibleCells()}>
                      {cell => {
                        return (
                          <td class="px-6 py-4">
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext()
                            )}
                          </td>
                        );
                      }}
                    </For>
                  </tr>
                );
              }}
            </For>
          </tbody>
        </table>
        <div class="mt-4 flex items-center justify-center gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            class="flex h-8 w-24 items-center justify-center rounded-lg border border-gray-300 bg-white px-3 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:text-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-white"
          >
            <ChevronLeft width={20} />
            Previous
          </button>
          <span class="flex items-center gap-1">
            <div>Page</div>
            <strong>
              {table.getState().pagination.pageIndex + 1} of{" "}
              {table.getPageCount().toLocaleString()}
            </strong>
          </span>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            class="flex h-8 w-24 items-center justify-center rounded-lg border border-gray-300 bg-white px-3 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:text-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-white"
          >
            Next
            <ChevronRight width={20} />
          </button>
        </div>
      </Show>

      <div class="mt-8">
        <h2 class="w-full text-left text-lg font-bold text-blue-600">
          Recommended Players
        </h2>
        <h3 class="w-full text-left text-sm italic">
          Players who have previously played with this team
        </h3>

        <Show
          when={recommendedPlayersTable.getRowModel().rows.length > 0}
          fallback={
            <div>
              <Show
                when={recommendedPlayersQuery.isLoading}
                fallback={<Info text="No recommended players found." />}
              >
                <Spinner />
              </Show>
            </div>
          }
        >
          <div class="mt-4 overflow-x-auto">
            <table class="w-full text-left text-sm text-gray-500 rtl:text-right dark:text-gray-400">
              <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                <For each={recommendedPlayersTable.getHeaderGroups()}>
                  {headerGroup => (
                    <tr>
                      <For each={headerGroup.headers}>
                        {header => (
                          <th colSpan={header.colSpan} class="px-6 py-3">
                            {header.isPlaceholder ? null : (
                              <div>
                                {flexRender(
                                  header.column.columnDef.header,
                                  header.getContext()
                                )}
                              </div>
                            )}
                          </th>
                        )}
                      </For>
                    </tr>
                  )}
                </For>
              </thead>
              <tbody>
                <For each={recommendedPlayersTable.getRowModel().rows}>
                  {row => (
                    <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                      <For each={row.getVisibleCells()}>
                        {cell => (
                          <td class="px-6 py-4">
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext()
                            )}
                          </td>
                        )}
                      </For>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
            <div class="mt-4 flex items-center justify-center gap-2">
              <button
                onClick={() => recommendedPlayersTable.previousPage()}
                disabled={!recommendedPlayersTable.getCanPreviousPage()}
                class="flex h-8 w-24 items-center justify-center rounded-lg border border-gray-300 bg-white px-3 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:text-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-white"
              >
                <ChevronLeft width={20} />
                Previous
              </button>
              <span class="flex items-center gap-1">
                <div>Page</div>
                <strong>
                  {recommendedPlayersTable.getState().pagination.pageIndex + 1}{" "}
                  of {recommendedPlayersTable.getPageCount().toLocaleString()}
                </strong>
              </span>
              <button
                onClick={() => recommendedPlayersTable.nextPage()}
                disabled={!recommendedPlayersTable.getCanNextPage()}
                class="flex h-8 w-24 items-center justify-center rounded-lg border border-gray-300 bg-white px-3 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:text-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-white"
              >
                Next
                <ChevronRight width={20} />
              </button>
            </div>
          </div>
        </Show>
      </div>
      <p class="my-2">{status()}</p>
    </div>
  );
};

export default AddToRoster;
