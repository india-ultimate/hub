import { createQuery } from "@tanstack/solid-query";
import {
  createSolidTable,
  flexRender,
  getCoreRowModel
} from "@tanstack/solid-table";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";

import { minAge, minAgeWarning } from "../../constants";
import { ChevronLeft, ChevronRight, Spinner } from "../../icons";
import {
  fetchSeasonGrants,
  fetchSeasonPlans,
  searchPlayers
} from "../../queries";
import { displayDate } from "../../utils";
import Info from "../alerts/Info";
import RazorpayPayment from "../RazorpayPayment";
import MembershipPlayerList from "./MembershipPlayerList";

const PlayerSearchDropdown = componentProps => {
  const [search, setSearch] = createSignal("");
  const [pagination, setPagination] = createSignal({
    pageIndex: 0,
    pageSize: 5
  });
  const [status, _setStatus] = createSignal();
  const [payingPlayers, setPayingPlayers] = createSignal({});

  const dataQuery = createQuery(
    () => ["players", "search", search(), pagination()],
    () =>
      search().trim().length > 2 ? searchPlayers(search(), pagination()) : []
  );

  createEffect(() => {
    let newPayingPlayers = {};

    componentProps.payingPlayers.map(p => {
      newPayingPlayers[p.id] = true;
    });

    setPayingPlayers(newPayingPlayers);
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
        <Switch
          fallback={
            <button
              onClick={() =>
                componentProps.onPlayerPayingStatusChange(
                  props.row.original,
                  true
                )
              }
              class="mb-2 me-2 rounded-lg border border-blue-700 px-5 py-1.5 text-center text-sm font-medium text-blue-700 hover:bg-blue-800 hover:text-white "
            >
              Add
            </button>
          }
        >
          <Match when={props.row.original.has_membership}>
            Membership already exists
          </Match>
          <Match when={payingPlayers()[props.getValue()]}>Added</Match>
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

  return (
    <>
      <div class="relative mt-4 w-full">
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

      <h3 class="mb-4 mt-1 w-full text-left text-sm italic">
        Search players by name or email (min. 3 letters)
      </h3>

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
      <p class="my-2">{status()}</p>
    </>
  );
};

const GroupMembership = props => {
  const [status, setStatus] = createSignal();

  const [payingPlayers, setPayingPlayers] = createSignal([]);
  const [paymentSuccess, setPaymentSuccess] = createSignal(false);
  // player id -> tier slug. The tier is per person, not per group.
  const [tiers, setTiers] = createSignal({});

  const plansQuery = createQuery(
    () => ["season-plans", props.season?.id],
    () => fetchSeasonPlans(props.season.id),
    {
      get enabled() {
        return Boolean(props.season?.id);
      }
    }
  );

  // One request for the whole selection, refetched as it changes: the
  // legacy `sponsored` flag on a player says nothing about this season.
  const grantsQuery = createQuery(
    () => [
      "season-grants",
      props.season?.id,
      payingPlayers()
        .map(p => p.id)
        .join(",")
    ],
    () =>
      fetchSeasonGrants(
        props.season.id,
        payingPlayers().map(p => p.id)
      ),
    {
      get enabled() {
        return Boolean(props.season?.id) && payingPlayers().length > 0;
      }
    }
  );

  const plans = () => plansQuery.data ?? [];
  const hasGrant = playerId => (grantsQuery.data ?? []).includes(playerId);

  // What this person may pick: the open tiers, plus a grant-only tier when
  // they hold a grant for this season.
  const plansFor = playerId =>
    plans().filter(plan => !plan.requires_grant || hasGrant(playerId));

  const defaultTier = playerId => {
    const available = plansFor(playerId);
    const granted = available.find(plan => plan.requires_grant);
    if (granted) {
      return granted.slug;
    }
    return (available.find(plan => plan.slug === "regular") ?? available[0])
      ?.slug;
  };

  const tierFor = playerId => tiers()[playerId] ?? defaultTier(playerId);

  const planFor = playerId =>
    plans().find(plan => plan.slug === tierFor(playerId));

  const setTierFor = (playerId, slug) =>
    setTiers({ ...tiers(), [playerId]: slug });

  const items = () =>
    payingPlayers()
      .filter(player => tierFor(player.id))
      .map(player => ({ player_id: player.id, plan_type: tierFor(player.id) }));

  const paymentSuccessCallback = () => {
    setPaymentSuccess(true);
    props.successCallback();
  };

  const handlePlayerPayingStatus = (player, isPaying) => {
    // Don't perform any actions on a player who already has a membership
    if (player?.has_membership) {
      return;
    }
    if (isPaying) {
      // Add player to paying Players
      setPayingPlayers([
        ...payingPlayers().filter(p => p.id !== player.id),
        player
      ]);
    } else {
      // Remove player from paying Players
      setPayingPlayers(payingPlayers().filter(p => p.id !== player.id));
    }
  };

  const [payDisabled, setPayDisabled] = createSignal(false);
  createEffect(() => {
    setPayDisabled(payingPlayers().length === 0);
  });

  // Every rupee here is a price the server sent back for the tier that was
  // picked; nothing is worked out in the browser.
  const getAmount = () =>
    payingPlayers().reduce(
      (acc, player) => acc + (planFor(player.id)?.amount ?? 0),
      0
    ) / 100;

  return (
    <div>
      <Show when={!paymentSuccess()}>
        <PlayerSearchDropdown
          payingPlayers={payingPlayers()}
          onPlayerPayingStatusChange={handlePlayerPayingStatus}
        />
      </Show>
      <MembershipPlayerList
        players={payingPlayers()}
        fee={getAmount()}
        startDate={displayDate(props.season?.start_date)}
        endDate={displayDate(props.season?.end_date)}
        onPlayerPayingStatusChange={handlePlayerPayingStatus}
        plansFor={plansFor}
        planFor={planFor}
        tierFor={tierFor}
        onTierChange={setTierFor}
      />
      <Show when={payingPlayers()?.find(p => p.is_minor)}>
        <div
          class="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-gray-800 dark:text-red-400"
          role="alert"
        >
          * {minAgeWarning} Please ensure that all the players are atleast{" "}
          {minAge} years old before {displayDate(props.season?.end_date)}.
        </div>
      </Show>
      <div>
        <Switch>
          <Match when={!paymentSuccess()}>
            <RazorpayPayment
              disabled={payDisabled() || items().length === 0}
              season={props.season}
              items={items()}
              buttonText={`Pay ₹ ${getAmount().toLocaleString("en-IN")}`}
              setStatus={setStatus}
              successCallback={paymentSuccessCallback}
            />
          </Match>
          <Match when={paymentSuccess()}>
            <button
              class={`my-2 w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto ${
                payDisabled() ? "cursor-not-allowed" : ""
              } `}
              onClick={() => {
                setPaymentSuccess(false);
                setPayingPlayers([]);
                setStatus("");
                initFlowbite();
              }}
              disabled={!paymentSuccess()}
            >
              Make another Payment
            </button>
          </Match>
        </Switch>
      </div>
      <p>{status()}</p>
    </div>
  );
};

export default GroupMembership;
