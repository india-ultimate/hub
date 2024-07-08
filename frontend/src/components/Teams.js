import { A, useSearchParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import {
  createSolidTable,
  flexRender,
  getCoreRowModel
} from "@tanstack/solid-table";
import { createEffect, createSignal, For, Show } from "solid-js";

import { ChevronLeft, ChevronRight } from "../icons";
import { fetchUser, searchTeams } from "../queries";
import Error from "./alerts/Error";
import Info from "./alerts/Info";

const defaultColumns = [
  {
    accessorKey: "name",
    id: "name",
    header: () => <span>Team Name</span>,
    cell: props => (
      <div class="flex items-center gap-4">
        <img
          class="h-8 w-8 rounded-full"
          src={props.row.original.image ?? props.row.original.image_url}
          alt="logo"
        />
        <div class="font-medium dark:text-white">
          <div>{props.getValue()}</div>
        </div>
      </div>
    )
  },
  {
    accessorKey: "slug",
    id: "actions",
    header: () => <span>Actions</span>,
    cell: props => (
      <A
        href={`/team/${props.getValue()}`}
        class="mb-2 me-2 rounded-lg border border-blue-700 px-5 py-1.5 text-center text-sm font-medium text-blue-700 hover:bg-blue-800 hover:text-white focus:outline-none focus:ring-4 focus:ring-blue-300 dark:border-blue-500 dark:text-blue-500 dark:hover:bg-blue-500 dark:hover:text-white dark:focus:ring-blue-800"
      >
        View
      </A>
    )
  }
];

const Teams = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [pagination, setPagination] = createSignal({
    pageIndex: searchParams.page ? Number(searchParams.page) : 0,
    pageSize: 10
  });
  const [search, setSearch] = createSignal(searchParams.text ?? "");

  // update query params whenever we search or change page
  createEffect(() => {
    setSearchParams({
      text: search(),
      page: pagination().pageIndex
    });
  });

  // search and pageIndex should also track query params changes
  createEffect(() => {
    setSearch(searchParams.text ?? "");
  });

  createEffect(() => {
    setPagination({
      pageIndex: searchParams.page ? Number(searchParams.page) : 0,
      pageSize: 10
    });
  });

  const dataQuery = createQuery(
    () => ["teams", "search", search(), pagination()],
    () => searchTeams(search(), pagination())
  );
  const userQuery = createQuery(() => ["me"], fetchUser);

  const table = createSolidTable({
    get data() {
      return dataQuery.data?.items ?? [];
    },
    columns: defaultColumns,
    get rowCount() {
      return dataQuery.data?.count;
    },
    // pageCount: dataQuery.data?.count ?? -1, //you can now pass in `rowCount` instead of pageCount and `pageCount` will be calculated internally (new in v8.13.0)
    // rowCount: dataQuery.data?.count, // new in v8.13.0 - alternatively, just pass in `pageCount` directly
    get state() {
      return {
        get pagination() {
          return pagination();
        }
      };
    },
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true, //we're doing manual "server-side" pagination
    // getPaginationRowModel: getPaginationRowModel(), // If only doing manual pagination, you don't need this
    debugTable: true
  });

  return (
    <div>
      <h1 class="text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-3xl font-extrabold text-transparent ">
          Teams
        </span>
      </h1>

      <div class="relative flex flex-wrap justify-center overflow-x-auto">
        <h2 class="w-full text-left text-lg font-bold text-blue-600">
          My Teams
        </h2>
        <h3 class="mb-2 w-full text-left text-sm italic">
          Teams in which you are an admin
        </h3>
        <Show
          when={userQuery.isSuccess}
          fallback={<Error text="Please login to view your teams" />}
        >
          <Show
            when={
              userQuery.data.admin_teams &&
              userQuery.data.admin_teams.length > 0
            }
            fallback={<Info text="No teams to show" />}
          >
            <For each={userQuery.data.admin_teams}>
              {team => (
                <div class="mt-1 flex w-full justify-between gap-4">
                  <div class="flex items-center gap-2">
                    <img
                      class="h-8 w-8 rounded-full"
                      src={team.image ?? team.image_url}
                      alt="logo"
                    />
                    <div class="font-medium dark:text-white">
                      <div>{team.name}</div>
                    </div>
                  </div>
                  <A
                    href={`/team/${team.slug}`}
                    class="mb-2 me-2 rounded-lg border border-blue-700 px-5 py-1.5 text-center text-sm font-medium text-blue-700 hover:bg-blue-800 hover:text-white focus:outline-none focus:ring-4 focus:ring-blue-300 dark:border-blue-500 dark:text-blue-500 dark:hover:bg-blue-500 dark:hover:text-white dark:focus:ring-blue-800"
                  >
                    Edit
                  </A>
                </div>
              )}
            </For>
          </Show>
          <A
            href={"/teams/new"}
            class="me-2 mt-4 w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          >
            Create New Team
          </A>
        </Show>

        <hr class="my-4 h-px w-full border-0 bg-gray-200 dark:bg-gray-700" />

        <h2 class="w-full text-left text-lg font-bold text-blue-600">
          All Teams
        </h2>
        <h3 class="w-full text-left text-sm italic">All teams in Hub</h3>
        <div class="relative m-2 mx-1 w-full">
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
            id="default-search"
            class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-4 ps-10 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
            placeholder="Search Team Names"
            required
            value={search()}
            onChange={e => {
              setSearch(e.target.value);
              table.setPageIndex(0);
            }}
          />
          <button
            type="submit"
            class="absolute bottom-2.5 end-2.5 rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          >
            Search
          </button>
        </div>
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
        <div class="mt-4 flex items-center gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            class="flex h-8 w-28 items-center justify-center rounded-lg border border-gray-300 bg-white px-3 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:text-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-white"
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
            class="flex h-8 w-28 items-center justify-center rounded-lg border border-gray-300 bg-white px-3 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:text-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-white"
          >
            Next
            <ChevronRight width={20} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Teams;
