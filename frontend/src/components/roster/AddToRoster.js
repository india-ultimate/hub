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
import { Icon } from "solid-heroicons";
import { handRaised } from "solid-heroicons/outline";
import { plus, xMark } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import { ChevronLeft, ChevronRight, Spinner } from "../../icons";
import {
  addToRoster,
  fetchUser,
  searchSeriesRosterPlayers
} from "../../queries";
import Info from "../alerts/Info";
import Modal from "../Modal";
import ErrorPopover from "../popover/ErrorPopover";
import SuccessPopover from "../popover/SuccessPopover";

const AddToRoster = props => {
  let modalRef;
  let successPopoverRef, errorPopoverRef;
  const [status, setStatus] = createSignal("");

  const queryClient = useQueryClient();
  const userQuery = createQuery(() => ["me"], fetchUser);
  const addToRosterMutation = createMutation({
    mutationFn: addToRoster,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournament-roster"] })
  });

  createEffect(function onMutationComplete() {
    if (addToRosterMutation.isSuccess) {
      setStatus("Successfully added player to the roster");
      successPopoverRef.showPopover();
    }
    if (addToRosterMutation.isError) {
      setStatus("Adding to the roster failed");
      errorPopoverRef.showPopover();
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
            addToRosterMutation.mutate({
              event_id: props.eventId,
              team_id: props.teamId,
              body: {
                player_id: userQuery.data?.player?.id
              }
            });
          }}
          type="button"
          class="mb-2 me-2 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-blue-700 px-2 py-2.5 text-center text-sm font-medium text-blue-700 hover:bg-blue-800 hover:text-white focus:outline-none dark:border-blue-500  dark:text-blue-500 dark:hover:bg-blue-500 dark:hover:text-white dark:focus:ring-blue-800 md:px-5"
        >
          <Icon path={handRaised} style={{ width: "24px" }} />
          <span class="w-3/4">Add myself to the roster</span>
        </button>
      </Show>
      <button
        onClick={() => modalRef.showModal()}
        type="button"
        class="mb-2 me-2 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-2 py-2.5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 md:px-5"
      >
        <Icon path={plus} style={{ width: "24px" }} />
        <span class="w-3/4">Add a player to the roster</span>
      </button>
      <Modal
        ref={modalRef}
        title={<span class="font-bold">Adding a new player to the roster</span>}
        close={() => modalRef.close()}
      >
        <AddPlayerRegistrationForm
          roster={props.roster}
          eventId={props.eventId}
          teamId={props.teamId}
          tournamentSlug={props.tournamentSlug}
          teamSlug={props.teamSlug}
          isPartOfSeries={props.isPartOfSeries}
        />
      </Modal>
      <SuccessPopover ref={successPopoverRef}>
        <span class="font-medium">{status()}</span>
      </SuccessPopover>

      <ErrorPopover ref={errorPopoverRef}>
        <span class="font-medium">{status()}</span>
      </ErrorPopover>
    </div>
  );
};

const AddPlayerRegistrationForm = componentProps => {
  const [search, setSearch] = createSignal("");
  const [pagination, setPagination] = createSignal({
    pageIndex: 0,
    pageSize: 5
  });
  const [status, setStatus] = createSignal();

  const queryClient = useQueryClient();
  const addToRosterMutation = createMutation({
    mutationFn: addToRoster,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournament-roster"] })
  });

  createEffect(function onMutationComplete() {
    if (addToRosterMutation.isSuccess) {
      setStatus("Successfully added player to the roster");
    }
    if (addToRosterMutation.isError) {
      setStatus("Adding to the roster failed");
    }
  });

  createEffect(() => {
    console.log(componentProps.isPartOfSeries);
  });

  const dataQuery = createQuery(
    () => [
      componentProps.tournamentSlug,
      componentProps.teamSlug,
      "players",
      "search",
      search(),
      pagination()
    ],
    () =>
      search().trim().length > (componentProps.isPartOfSeries ? -1 : 2)
        ? searchSeriesRosterPlayers(
            componentProps.tournamentSlug,
            componentProps.teamSlug,
            search(),
            pagination()
          )
        : []
  );

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
        <Show
          when={
            !(componentProps.roster || [])
              .map(reg => reg.player.id)
              .includes(props.getValue())
          }
          fallback={<span>Added</span>}
        >
          <button
            onClick={() =>
              addToRosterMutation.mutate({
                event_id: componentProps.eventId,
                team_id: componentProps.teamId,
                body: {
                  player_id: props.getValue()
                }
              })
            }
            class="mb-2 me-2 rounded-lg border border-blue-700 px-5 py-1.5 text-center text-sm font-medium text-blue-700 hover:bg-blue-800 hover:text-white focus:outline-none focus:ring-4 focus:ring-blue-300 dark:border-blue-500 dark:text-blue-500 dark:hover:bg-blue-500 dark:hover:text-white dark:focus:ring-blue-800"
          >
            Add
          </button>
        </Show>
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

  return (
    <div class="h-screen w-full rounded-lg p-2">
      <h2 class="w-full text-left text-lg font-bold text-blue-600">
        Add Players to Roster
      </h2>
      <h3 class="w-full text-left text-sm italic">
        Search players by name or email{" "}
        <Show when={!componentProps.isPartOfSeries}>(min. 3 letters)</Show>
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
                    search().trim().length >
                    (componentProps.isPartOfSeries ? -1 : 2)
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
      <p class="my-2">{status()}</p>
    </div>
  );
};

export default AddToRoster;
