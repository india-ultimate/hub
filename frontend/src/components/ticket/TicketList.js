import { A, useSearchParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import {
  chatBubbleOvalLeftEllipsis,
  magnifyingGlass,
  xMark
} from "solid-heroicons/outline";
import {
  createEffect,
  createSignal,
  For,
  Index,
  Match,
  on,
  onCleanup,
  Show,
  Switch
} from "solid-js";

import { fetchTickets } from "../../queries";
import { CATEGORIES } from "../../tickets";
import Pagination from "./Pagination";
import TicketRow from "./TicketRow";

const PAGE_SIZE = 20;
// The page's status choices, and the statuses each asks the API for
const VIEWS = { active: ["OPN", "PRG"], resolved: ["RES"], all: [] };
const VIEW_LABELS = [
  ["active", "Active"],
  ["resolved", "Resolved"],
  ["all", "All"]
];

const chip = selected =>
  clsx(
    "inline-flex min-h-[44px] items-center rounded-lg px-4 text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 motion-reduce:transition-none dark:focus-visible:ring-blue-800",
    selected
      ? "bg-blue-700 text-white dark:bg-blue-600"
      : "bg-gray-100 text-gray-800 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
  );
const select =
  "min-h-[44px] flex-1 rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white sm:flex-none";
const primary =
  "inline-flex min-h-[44px] items-center rounded-lg bg-blue-700 px-5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus-visible:ring-blue-800";
const secondary =
  "inline-flex min-h-[44px] items-center rounded-lg border border-gray-300 bg-white px-5 text-sm font-medium text-gray-900 hover:bg-gray-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-gray-200 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700";

const TicketList = props => {
  const [params, setParams] = useSearchParams();
  const [draft, setDraft] = createSignal(params.q ?? "");
  let timer;
  onCleanup(() => clearTimeout(timer));

  // Back and Forward change the URL under the box, so follow it. Not when the
  // URL only caught up with the box: it holds the trimmed text, and copying
  // it back would eat a space typed just before a pause.
  createEffect(
    on(
      () => params.q,
      q => (q ?? "") !== draft().trim() && setDraft(q ?? ""),
      { defer: true }
    )
  );

  const searching = () => Boolean(params.q);
  // With no choice made, a search covers every status: 88% of tickets are
  // resolved, and those are where the answers are.
  const view = () =>
    params.status in VIEWS ? params.status : searching() ? "all" : "active";
  const sort = () => params.sort || (searching() ? "relevance" : "newest");
  const page = () => Math.max(1, Number(params.page) || 1);
  const filtered = () =>
    searching() ||
    Boolean(params.status || params.category || params.mine || params.upvoted);

  const request = () => ({
    q: params.q ?? "",
    status: VIEWS[view()],
    category: params.category ?? "",
    mine: params.mine === "1",
    upvoted: params.upvoted === "1",
    sort: params.sort ?? "",
    page: page()
  });

  const ticketsQuery = createQuery(
    () => ["tickets", "list", request()],
    () => fetchTickets(request()),
    { keepPreviousData: true }
  );

  const count = () => ticketsQuery.data?.count ?? 0;
  const pages = () => Math.ceil(count() / PAGE_SIZE);

  // Any change except paging starts again from page 1
  const update = (changes, options) =>
    setParams({ page: null, ...changes }, options);

  const goToPage = p =>
    setParams({ page: p === 1 ? null : p }, { scroll: true });

  // An old link can point past the last page once tickets move on
  createEffect(() => {
    if (ticketsQuery.data && pages() > 0 && page() > pages()) {
      setParams({ page: pages() === 1 ? null : pages() }, { replace: true });
    }
  });

  const search = value => {
    setDraft(value);
    clearTimeout(timer);
    // The first search gets its own history entry, so Back returns to the
    // list; later keystrokes replace it, so Back doesn't step through them
    timer = setTimeout(
      () => update({ q: value.trim() || null }, { replace: searching() }),
      300
    );
  };

  const clearSearch = () => {
    clearTimeout(timer);
    setDraft("");
    update({ q: null });
  };

  const clearAll = () => {
    clearTimeout(timer);
    setDraft("");
    setParams({
      q: null,
      status: null,
      category: null,
      mine: null,
      upvoted: null,
      sort: null,
      page: null
    });
  };

  const toggle = key => update({ [key]: params[key] === "1" ? null : "1" });

  return (
    <div class="space-y-4">
      <div class="relative">
        <label for="ticket-search" class="sr-only">
          Search tickets
        </label>
        <Icon
          path={magnifyingGlass}
          class="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-500"
          aria-hidden="true"
        />
        <input
          id="ticket-search"
          type="search"
          value={draft()}
          onInput={e => search(e.currentTarget.value)}
          onKeyDown={e => e.key === "Escape" && clearSearch()}
          placeholder="Search tickets…"
          autocomplete="off"
          class="block min-h-[48px] w-full rounded-lg border border-gray-300 bg-white py-3 pl-10 pr-12 text-base text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder-gray-400 [&::-webkit-search-cancel-button]:appearance-none"
        />
        <Show when={draft()}>
          <button
            type="button"
            onClick={clearSearch}
            aria-label="Clear search"
            class="absolute right-1 top-1/2 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-lg text-gray-500 hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:hover:text-white"
          >
            <Icon path={xMark} class="h-5 w-5" aria-hidden="true" />
          </button>
        </Show>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Status" class="flex gap-2">
          <For each={VIEW_LABELS}>
            {([value, label]) => (
              <button
                type="button"
                id={`view-${value}`}
                aria-pressed={view() === value}
                class={chip(view() === value)}
                onClick={() => update({ status: value })}
              >
                {label}
              </button>
            )}
          </For>
        </div>
        <span
          class="mx-1 hidden h-6 w-px bg-gray-300 dark:bg-gray-600 sm:block"
          aria-hidden="true"
        />
        <button
          type="button"
          id="filter-mine"
          aria-pressed={params.mine === "1"}
          class={chip(params.mine === "1")}
          onClick={() => toggle("mine")}
        >
          Mine
        </button>
        <button
          type="button"
          id="filter-upvoted"
          aria-pressed={params.upvoted === "1"}
          class={chip(params.upvoted === "1")}
          onClick={() => toggle("upvoted")}
        >
          Upvoted by me
        </button>
        <div class="flex w-full gap-2 sm:ml-auto sm:w-auto">
          <label for="filter-category" class="sr-only">
            Category
          </label>
          <select
            id="filter-category"
            class={select}
            value={params.category ?? ""}
            onChange={e => update({ category: e.currentTarget.value || null })}
          >
            <option value="">All categories</option>
            <For each={CATEGORIES}>
              {category => <option value={category}>{category}</option>}
            </For>
          </select>
          <label for="sort" class="sr-only">
            Sort
          </label>
          <select
            id="sort"
            class={select}
            value={sort()}
            onChange={e => update({ sort: e.currentTarget.value })}
          >
            <Show when={searching()}>
              <option value="relevance">Best match</option>
            </Show>
            <option value="newest">Newest</option>
            <option value="upvotes">Most upvoted</option>
          </select>
        </div>
      </div>

      <div class="flex min-h-[1.5rem] items-center justify-between text-sm text-gray-600 dark:text-gray-400">
        <p id="ticket-count" aria-live="polite">
          <Show when={count() > 0}>
            Showing {(page() - 1) * PAGE_SIZE + 1}–
            {Math.min(page() * PAGE_SIZE, count())} of {count()}
          </Show>
        </p>
        <Show when={ticketsQuery.isFetching && ticketsQuery.data}>
          <span
            role="status"
            aria-label="Loading"
            class="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600 motion-reduce:animate-none"
          />
        </Show>
      </div>

      <div
        class="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800"
        aria-busy={ticketsQuery.isFetching}
      >
        <Switch>
          <Match when={ticketsQuery.isLoading}>
            <ul
              aria-hidden="true"
              class="divide-y divide-gray-200 dark:divide-gray-700"
            >
              <For each={[1, 2, 3, 4, 5]}>
                {() => (
                  <li class="flex gap-4 px-4 py-4 sm:px-6">
                    <div class="h-14 w-12 animate-pulse rounded-lg bg-gray-200 motion-reduce:animate-none dark:bg-gray-700" />
                    <div class="flex-1 space-y-3 py-1">
                      <div class="h-4 w-2/3 animate-pulse rounded bg-gray-200 motion-reduce:animate-none dark:bg-gray-700" />
                      <div class="h-3 w-1/2 animate-pulse rounded bg-gray-200 motion-reduce:animate-none dark:bg-gray-700" />
                    </div>
                  </li>
                )}
              </For>
            </ul>
          </Match>
          <Match when={ticketsQuery.isError}>
            <div class="px-6 py-12 text-center">
              <p class="font-semibold text-gray-900 dark:text-white">
                Couldn't load tickets
              </p>
              <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
                {ticketsQuery.error?.message}
              </p>
              <button
                type="button"
                class={clsx(secondary, "mt-4")}
                onClick={() => ticketsQuery.refetch()}
              >
                Try again
              </button>
            </div>
          </Match>
          <Match when={ticketsQuery.data?.items.length === 0}>
            <div id="tickets-empty" class="px-6 py-12 text-center">
              <Icon
                path={chatBubbleOvalLeftEllipsis}
                class="mx-auto h-10 w-10 text-gray-400"
                aria-hidden="true"
              />
              <Show
                when={filtered()}
                fallback={
                  <>
                    <h2 class="mt-3 text-lg font-semibold text-gray-900 dark:text-white">
                      Nothing open right now
                    </h2>
                    <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
                      Every ticket has been resolved. Browse them, or ask for
                      help in a new ticket.
                    </p>
                  </>
                }
              >
                <h2 class="mt-3 break-words text-lg font-semibold text-gray-900 dark:text-white">
                  {searching()
                    ? `No tickets match "${params.q}"`
                    : "No tickets match these filters"}
                </h2>
                <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
                  Try other words, or ask for help in a new ticket.
                </p>
              </Show>
              <div class="mt-6 flex flex-wrap justify-center gap-3">
                <Show
                  when={filtered()}
                  fallback={
                    <button
                      type="button"
                      class={secondary}
                      onClick={() => update({ status: "resolved" })}
                    >
                      Browse resolved tickets
                    </button>
                  }
                >
                  <button type="button" class={secondary} onClick={clearAll}>
                    Clear filters
                  </button>
                </Show>
                <A href="/tickets/new" class={primary}>
                  New ticket
                </A>
              </div>
            </div>
          </Match>
          <Match when={ticketsQuery.data}>
            <ul class="divide-y divide-gray-200 dark:divide-gray-700">
              {/* Index, not For: a vote puts a new ticket object in the cache, and
                  For would rebuild the row, losing keyboard focus and the error */}
              <Index each={ticketsQuery.data.items}>
                {ticket => (
                  <TicketRow
                    ticket={ticket()}
                    userId={props.user.id}
                    isStaff={props.user.is_staff}
                  />
                )}
              </Index>
            </ul>
          </Match>
        </Switch>
      </div>

      <Pagination page={page()} pages={pages()} onChange={goToPage} />
    </div>
  );
};

export default TicketList;
