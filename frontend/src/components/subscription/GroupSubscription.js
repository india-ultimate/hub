import { createQuery, useQueryClient } from "@tanstack/solid-query";
import {
  createSolidTable,
  flexRender,
  getCoreRowModel
} from "@tanstack/solid-table";
import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/solid";
import {
  createEffect,
  createSignal,
  For,
  Match,
  onMount,
  Show,
  Switch
} from "solid-js";

import { majorAge, MAX_GROUP, minAge, minAgeWarning } from "../../constants";
import { ChevronLeft, ChevronRight } from "../../icons";
import { inr } from "../../money";
import {
  fetchPlayerById,
  fetchSeasonPlans,
  fetchSeasonQuotes,
  searchPlayers
} from "../../queries";
import { Loading, TableRowsSkeleton } from "../../skeletons/primitives";
import { displayDate, getAge } from "../../utils";
import Info from "../alerts/Info";
import RazorpayPayment from "../RazorpayPayment";
import SubscriptionPlayerList from "./SubscriptionPlayerList";

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
          <Show when={props.row.original.has_subscription}>
            <div class="text-xs text-gray-500 dark:text-gray-400">
              Has a subscription
            </div>
          </Show>
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
              class="mb-2 me-2 rounded-lg border border-blue-700 px-5 py-1.5 text-center text-sm font-medium text-blue-700 hover:bg-blue-800 hover:text-white"
            >
              Add
            </button>
          }
        >
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
          placeholder="Player name"
          required
          value={search()}
          onChange={e => {
            setSearch(e.target.value);
          }}
        />
        <button
          type="button"
          onClick={() => setSearch("")}
          class="absolute bottom-2.5 end-24 rounded-full px-2 py-2 text-sm font-medium text-gray-400 hover:text-gray-700 focus:outline-none"
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
              <Loading label="Loading players">
                <TableRowsSkeleton rows={3} cols={3} />
              </Loading>
            </Show>
          </div>
        }
      >
        <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400 rtl:text-right">
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

const GroupSubscription = props => {
  const queryClient = useQueryClient();
  const [status, setStatus] = createSignal();

  const [payingPlayers, setPayingPlayers] = createSignal([]);
  const [paymentSuccess, setPaymentSuccess] = createSignal(false);
  // player id -> tier slug. The tier is per person, not per group.
  const [tiers, setTiers] = createSignal({});
  const [notice, setNotice] = createSignal();
  // Set when an add is refused for a full group; any change clears it.
  const [full, setFull] = createSignal(false);

  // A team registration page links here with ?players=12,34 and
  // &tiers=12:regular,34:regular. A tier no longer on offer to them falls
  // back to the default one (tierFor).
  onMount(async () => {
    const linked = [
      ...new Set(
        (props.preselect?.players || "").split(",").map(Number).filter(Boolean)
      )
    ];
    if (!linked.length) return;
    const ids = linked.slice(0, MAX_GROUP);
    const wanted = Object.fromEntries(
      (props.preselect?.tiers || "")
        .split(",")
        .map(pair => pair.split(":"))
        .filter(([id, slug]) => Number(id) && slug)
        .map(([id, slug]) => [Number(id), slug])
    );
    const loaded = await Promise.all(
      ids.map(id => fetchPlayerById(id).catch(() => null))
    );
    const found = loaded.filter(Boolean);
    const needing = found
      // The search results this list usually holds carry is_minor, as does
      // a player a team admin loads; anyone else's gets a date of birth.
      .map(p => ({
        ...p,
        is_minor: p.is_minor ?? getAge(p.date_of_birth) < majorAge
      }));
    setPayingPlayers([
      ...payingPlayers().filter(p => !ids.includes(p.id)),
      ...needing
    ]);
    setTiers({
      ...tiers(),
      ...Object.fromEntries(
        needing.filter(p => wanted[p.id]).map(p => [p.id, wanted[p.id]])
      )
    });
    const notes = [];
    if (found.length < ids.length) {
      const missing = ids.length - found.length;
      notes.push(
        `${missing} player${missing === 1 ? "" : "s"} couldn't be loaded and ${
          missing === 1 ? "was" : "were"
        } left out.`
      );
    }
    if (linked.length > ids.length) {
      notes.push(
        `Only the first ${MAX_GROUP} players were added. Pay for them, then come back for the rest.`
      );
    }
    if (notes.length) setNotice(notes.join(" "));
  });

  const plansQuery = createQuery(
    () => ["season-plans", props.season?.id],
    () => fetchSeasonPlans(props.season.id),
    {
      get enabled() {
        return Boolean(props.season?.id);
      }
    }
  );

  // What each person could be bought, and at what price: in full, or the
  // difference from the tier they hold. One request for the whole selection,
  // refetched as it changes.
  const quotesQuery = createQuery(
    () => [
      "season-quotes",
      props.season?.id,
      payingPlayers()
        .map(p => p.id)
        .join(",")
    ],
    () =>
      fetchSeasonQuotes(
        props.season.id,
        payingPlayers().map(p => p.id)
      ),
    {
      keepPreviousData: true,
      get enabled() {
        return Boolean(props.season?.id) && payingPlayers().length > 0;
      }
    }
  );

  const pricesLoading = () =>
    plansQuery.isInitialLoading || quotesQuery.isInitialLoading;
  const payLocked = () => pricesLoading() || quotesQuery.isFetching;
  const plans = () => plansQuery.data ?? [];
  const quoteFor = playerId =>
    (quotesQuery.data ?? []).find(quote => quote.player_id === playerId);
  const heldFor = playerId => quoteFor(playerId)?.held;
  const pendingFor = playerId =>
    !quoteFor(playerId) && !quotesQuery.isError && quotesQuery.isFetching;
  const totalPending = () =>
    pricesLoading() || payingPlayers().some(player => pendingFor(player.id));

  // What this person may pick, at what they'd pay: the server's offers for
  // them, named from the season's plans.
  const plansFor = playerId => {
    const offers = quoteFor(playerId)?.offers ?? [];
    return plans().flatMap(plan => {
      const offer = offers.find(o => o.slug === plan.slug);
      return offer ? [{ ...plan, amount: offer.amount, kind: offer.kind }] : [];
    });
  };

  const defaultTier = playerId => {
    const available = plansFor(playerId);
    const granted = available.find(plan => plan.requires_grant);
    if (granted) {
      return granted.slug;
    }
    return (available.find(plan => plan.slug === "regular") ?? available[0])
      ?.slug;
  };

  // A picked tier they can't buy (a link asked for one that's no longer on
  // offer to them, say) gives way to the default one.
  const tierFor = playerId => {
    const picked = tiers()[playerId];
    return plansFor(playerId).some(plan => plan.slug === picked)
      ? picked
      : defaultTier(playerId);
  };

  const planFor = playerId =>
    plansFor(playerId).find(plan => plan.slug === tierFor(playerId));

  const setTierFor = (playerId, slug) =>
    setTiers({ ...tiers(), [playerId]: slug });

  const items = () =>
    payingPlayers()
      .filter(player => tierFor(player.id))
      .map(player => ({ player_id: player.id, plan_type: tierFor(player.id) }));

  const paymentSuccessCallback = () => {
    // What they held has changed, so no price quoted before paying holds.
    queryClient.removeQueries({ queryKey: ["season-quotes"] });
    setFull(false);
    setPaymentSuccess(true);
    props.successCallback();
  };

  const handlePlayerPayingStatus = (player, isPaying) => {
    if (isPaying) {
      setFull(payingPlayers().length >= MAX_GROUP);
      if (full()) return;
      setPayingPlayers([
        ...payingPlayers().filter(p => p.id !== player.id),
        player
      ]);
    } else {
      setFull(false);
      setPayingPlayers(payingPlayers().filter(p => p.id !== player.id));
    }
  };

  const [payDisabled, setPayDisabled] = createSignal(false);
  createEffect(() => {
    setPayDisabled(payingPlayers().length === 0);
  });

  // Every rupee here is a price the server sent back for the tier that was
  // picked; nothing is worked out in the browser.
  // In paise.
  const getAmount = () =>
    payingPlayers().reduce(
      (acc, player) => acc + (planFor(player.id)?.amount ?? 0),
      0
    );

  return (
    <div>
      <Show when={!paymentSuccess()}>
        <PlayerSearchDropdown
          payingPlayers={payingPlayers()}
          onPlayerPayingStatusChange={handlePlayerPayingStatus}
        />
      </Show>
      <Show when={notice()}>
        <div class="mt-4">
          <Info text={notice()} />
        </div>
      </Show>
      <Show when={full()}>
        <div class="mt-4">
          <Info
            text={`A payment covers up to ${MAX_GROUP} players. Pay for these, then start another.`}
          />
        </div>
      </Show>
      <SubscriptionPlayerList
        players={payingPlayers()}
        fee={getAmount()}
        startDate={displayDate(props.season?.start_date)}
        endDate={displayDate(props.season?.end_date)}
        onPlayerPayingStatusChange={handlePlayerPayingStatus}
        plansFor={plansFor}
        planFor={planFor}
        tierFor={tierFor}
        onTierChange={setTierFor}
        heldFor={heldFor}
        pendingFor={pendingFor}
        count={items().length}
        pricesPending={pricesLoading()}
        totalPending={totalPending()}
        pricesFailed={quotesQuery.isError}
      />
      <Show when={quotesQuery.isError}>
        <div class="mb-4 flex flex-wrap items-center gap-3" role="alert">
          <p class="text-sm text-red-700 dark:text-red-400">
            Prices couldn't be loaded.
          </p>
          <button
            type="button"
            class="min-h-11 rounded-lg border border-blue-700 px-4 text-sm font-medium text-blue-700 hover:bg-blue-700 hover:text-white dark:border-blue-500 dark:text-blue-400"
            onClick={() => quotesQuery.refetch()}
          >
            Try again
          </button>
        </div>
      </Show>
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
              disabled={payDisabled() || items().length === 0 || payLocked()}
              season={props.season}
              items={items()}
              buttonText={
                totalPending() || quotesQuery.isError
                  ? "Pay"
                  : `Pay ${inr(getAmount())}`
              }
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
                setNotice();
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

export default GroupSubscription;
