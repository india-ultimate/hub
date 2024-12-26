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
import { arrowRight, checkCircle, xCircle, xMark } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import { ChevronLeft, ChevronRight, Spinner } from "../../icons";
import { addToRoster, searchSeriesRosterPlayers } from "../../queries";
import Info from "../alerts/Info";
import Modal from "../Modal";
import ErrorPopover from "../popover/ErrorPopover";
import SuccessPopover from "../popover/SuccessPopover";
import RazorpayPayment from "../RazorpayPayment";

const AddToRoster = componentProps => {
  let successPopoverRef, errorPopoverRef, errorModalRef;
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal({});
  const [search, setSearch] = createSignal("");
  const [pagination, setPagination] = createSignal({
    pageIndex: 0,
    pageSize: 5
  });
  const [selectedPlayers, setSelectedPlayers] = createSignal([]);

  const queryClient = useQueryClient();
  const addToRosterMutation = createMutation({
    mutationFn: addToRoster,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournament-roster"] })
  });

  createEffect(function onMutationComplete() {
    if (addToRosterMutation.isSuccess) {
      setStatus("Successfully added player to the roster");
      successPopoverRef?.showPopover();
    }
    if (addToRosterMutation.isError) {
      try {
        const mutationError = JSON.parse(addToRosterMutation.error.message);
        setError(mutationError);
        setStatus(mutationError.message);
        // Show error modal for long errors with a description, possibly an action button also
        if (mutationError.description) {
          errorModalRef?.showModal();
        } else {
          errorPopoverRef?.showPopover();
        }
      } catch (err) {
        throw new Error(`Couldn't parse error object: ${err}`);
      }
    }
  });

  const handleAddToRoster = player => {
    if (componentProps.playerFee > 0) {
      setSelectedPlayers([...selectedPlayers(), player]);
    } else {
      addToRosterMutation.mutate({
        event_id: componentProps.eventId,
        team_id: componentProps.teamId,
        body: {
          player_id: player.id
        }
      });
    }
  };

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
        <Show
          when={
            !(componentProps.roster || [])
              .map(reg => reg.player.id)
              .includes(props.getValue()) &&
            !selectedPlayers()
              .map(p => p.id)
              .includes(props.getValue())
          }
          fallback={<span>Added</span>}
        >
          <button
            onClick={() => handleAddToRoster(props.row.original)}
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
    <div class="w-full rounded-lg p-2">
      <Show when={componentProps.playerFee > 0}>
        <div class="mb-4 rounded-lg bg-blue-50 p-4 text-sm text-blue-800 dark:bg-gray-800 dark:text-blue-400">
          <h1 class="text-lg font-bold">Player Registrations</h1>
          <Show
            when={selectedPlayers().length > 0}
            fallback={
              <h2 class="italic">
                Please add players from the Add to roster section below
              </h2>
            }
          >
            <h2 class="">
              Paying{" "}
              <strong>
                Rs.{" "}
                {(componentProps.playerFee * selectedPlayers().length) / 100}
              </strong>{" "}
              for {selectedPlayers().length} players
            </h2>
            <ol class="mt-2 max-w-md list-inside list-decimal space-y-1">
              <For each={selectedPlayers()}>
                {player => (
                  <li>
                    <div class="inline-flex w-fit items-center gap-2">
                      <span>{player.full_name}</span>
                      <button
                        onClick={() =>
                          setSelectedPlayers([
                            ...selectedPlayers().filter(p => p.id !== player.id)
                          ])
                        }
                      >
                        <Icon class="h-4 w-4" path={xMark} />
                      </button>
                    </div>
                  </li>
                )}
              </For>
            </ol>
            <button
              onClick={() => setSelectedPlayers([])}
              class="mt-1 rounded-lg text-sm text-red-500 underline"
            >
              Reset
            </button>
          </Show>

          <RazorpayPayment
            disabled={selectedPlayers().length === 0}
            event={{ id: componentProps.eventId }}
            team={{ id: componentProps.teamId }}
            player_ids={selectedPlayers().map(p => p.id)}
            amount={componentProps.playerFee * selectedPlayers().length}
            setStatus={msg => {
              return msg;
            }}
            successCallback={() => {
              queryClient.invalidateQueries({
                queryKey: ["tournament-roster"]
              });
              setStatus("Paid successfully!");
              successPopoverRef?.showPopover();
              setSelectedPlayers([]);
            }}
            failureCallback={msg => {
              console.log(msg, componentProps.errorPopoverRef);

              setStatus(msg);
              errorPopoverRef?.showPopover();
            }}
          />
        </div>
      </Show>
      <h2 class="w-full text-left text-lg font-bold text-blue-600">Search</h2>
      <h3 class="w-full text-left text-sm italic">
        Search players by name or email{" "}
        <Show
          when={!componentProps.isPartOfSeries}
          fallback="(Players part of your series roster)"
        >
          (min. 3 letters)
        </Show>
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

export default AddToRoster;
