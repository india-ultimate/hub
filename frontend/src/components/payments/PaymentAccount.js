import { useParams, useSearchParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { arrowDownTray, magnifyingGlass } from "solid-heroicons/outline";
import { createSignal, For, Match, onCleanup, Show, Switch } from "solid-js";

import {
  fetchPaymentAccountTransactions,
  paymentAccountCsvUrl
} from "../../queries";
import Pagination from "../ticket/Pagination";

const inr = paise =>
  `₹${(paise / 100).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

const day = iso =>
  new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  });

const STATUS_CHOICES = [
  ["paid", "Paid"],
  ["refunded", "Refunded"],
  ["all", "All"]
];

const chip = selected =>
  clsx(
    "inline-flex min-h-[44px] items-center rounded-lg px-4 text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 motion-reduce:transition-none dark:focus-visible:ring-blue-800",
    selected
      ? "bg-blue-700 text-white dark:bg-blue-600"
      : "bg-gray-100 text-gray-800 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
  );

const muted = "text-sm text-gray-500 dark:text-gray-400";

// Status in words as well as colour, never colour alone
const StatusBadge = props => (
  <Switch>
    <Match when={props.row.status === "refunded"}>
      <span class="inline-flex items-center rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900 dark:text-amber-200">
        ↺ Refunded
      </span>
    </Match>
    <Match when={props.row.refunded > 0}>
      <span class="inline-flex items-center rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900 dark:text-amber-200">
        ✓ Paid · ↺ {inr(props.row.refunded)} back
      </span>
    </Match>
    <Match when={true}>
      <span class="inline-flex items-center rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900 dark:text-green-200">
        ✓ Paid
      </span>
    </Match>
  </Switch>
);

const What = props => (
  <>
    <span>
      {props.row.for}
      <Show when={props.row.days_late > 0}>
        {" "}
        (+{props.row.days_late} {props.row.days_late === 1 ? "day" : "days"}{" "}
        late)
      </Show>
    </span>
    <Show when={props.row.penalty_amount > 0}>
      <span class="block text-xs text-gray-500 dark:text-gray-400">
        {inr(props.row.base_amount)} + {inr(props.row.penalty_amount)} late
      </span>
    </Show>
    <Show when={props.row.players.length}>
      <details class="mt-1">
        <summary class="cursor-pointer text-xs text-blue-700 dark:text-blue-400">
          {props.row.players.length}{" "}
          {props.row.players.length === 1 ? "person" : "people"}
        </summary>
        <p class="mt-1 text-xs">{props.row.players.join(", ")}</p>
      </details>
    </Show>
  </>
);

const Totals = props => (
  <div>
    <dl class="grid grid-cols-2 gap-3 sm:grid-cols-5">
      <For
        each={[
          ["Collected", inr(props.totals.collected)],
          ["Refunded", inr(props.totals.refunded)],
          ["Net", inr(props.totals.net)],
          ["Teams paid", props.totals.teams_paid],
          ["Players paid", props.totals.players_paid]
        ]}
      >
        {([label, value]) => (
          <div class="rounded-lg border border-gray-200 p-4 dark:border-gray-700 dark:bg-gray-800">
            <dt class="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
              {label}
            </dt>
            <dd class="mt-1 text-xl font-semibold tabular-nums text-gray-900 dark:text-white">
              {value}
            </dd>
          </div>
        )}
      </For>
    </dl>
    <p class={clsx(muted, "mt-2")}>
      Net is before Razorpay's fees. Your settlement report has the final
      amount.
    </p>
  </div>
);

const PaymentAccount = () => {
  const routeParams = useParams();
  const [params, setParams] = useSearchParams();
  const [draft, setDraft] = createSignal(params.q ?? "");
  let timer;
  onCleanup(() => clearTimeout(timer));

  const filters = () => ({
    slug: routeParams.slug,
    event: params.event ? Number(params.event) : null,
    status: params.status || "paid",
    q: params.q ?? "",
    page: Math.max(1, Number(params.page) || 1)
  });

  const query = createQuery(
    () => ["payment-account", filters()],
    () => fetchPaymentAccountTransactions(filters()),
    { keepPreviousData: true, retry: false }
  );

  const data = () => query.data;
  const pages = () => (data() ? Math.ceil(data().count / data().page_size) : 0);
  const update = (changes, options) =>
    setParams({ page: null, ...changes }, options);

  const search = value => {
    setDraft(value);
    clearTimeout(timer);
    timer = setTimeout(
      () => update({ q: value.trim() || null }, { replace: true }),
      300
    );
  };

  return (
    <div class="mx-auto max-w-6xl space-y-5 px-4 py-6">
      <Switch>
        <Match when={query.error?.message === "not-found"}>
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
            Not found
          </h1>
          <p class={muted}>
            There is no payments page here, or you have not been given access to
            it.
          </p>
        </Match>
        <Match when={query.isError}>
          <p class={muted}>
            The payments could not be loaded. Please try again in a moment.
          </p>
        </Match>
        <Match when={!data()}>
          <p class={muted}>Loading payments...</p>
        </Match>
        <Match when={data()}>
          <header>
            <div class="flex flex-wrap items-center gap-2">
              <h1 class="text-2xl font-bold text-gray-900 dark:text-white md:text-3xl">
                {data().account.name}
              </h1>
              <Show when={data().account.is_test_mode}>
                <span class="rounded bg-amber-100 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                  Test mode
                </span>
              </Show>
            </div>
            <p class={muted}>Payments collected into your Razorpay account</p>
          </header>

          <Show
            when={data().events.length}
            fallback={
              <p class={muted}>
                No payments yet. They appear here as teams and players pay.
              </p>
            }
          >
            <div class="flex flex-col gap-3 lg:flex-row lg:items-center">
              <label class="sr-only" for="payments-event">
                Tournament
              </label>
              <select
                id="payments-event"
                class="min-h-[44px] rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                value={data().event}
                onChange={e => update({ event: e.currentTarget.value })}
              >
                <For each={data().events}>
                  {event => <option value={event.id}>{event.title}</option>}
                </For>
              </select>
              <div class="flex gap-2" role="group" aria-label="Status">
                <For each={STATUS_CHOICES}>
                  {([value, label]) => (
                    <button
                      type="button"
                      class={chip(filters().status === value)}
                      aria-pressed={filters().status === value}
                      onClick={() =>
                        update({ status: value === "paid" ? null : value })
                      }
                    >
                      {label}
                    </button>
                  )}
                </For>
              </div>
              <div class="relative flex-1">
                <label for="payments-search" class="sr-only">
                  Search payments
                </label>
                <Icon
                  path={magnifyingGlass}
                  class="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-500"
                  aria-hidden="true"
                />
                <input
                  id="payments-search"
                  type="search"
                  value={draft()}
                  onInput={e => search(e.currentTarget.value)}
                  placeholder="Team, payer or payment ID"
                  autocomplete="off"
                  class="block min-h-[44px] w-full rounded-lg border border-gray-300 bg-white py-2 pl-10 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                />
              </div>
              <a
                href={paymentAccountCsvUrl({
                  ...filters(),
                  event: data().event
                })}
                class="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white px-4 text-sm font-medium text-gray-900 hover:bg-gray-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-gray-200 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700"
              >
                <Icon path={arrowDownTray} class="h-5 w-5" aria-hidden="true" />
                Export CSV
              </a>
            </div>

            <Totals totals={data().totals} />

            <Show
              when={data().results.length}
              fallback={<p class={muted}>No payments match these filters.</p>}
            >
              {/* Cards on a phone */}
              <ul class="space-y-3 md:hidden">
                <For each={data().results}>
                  {row => (
                    <li class="rounded-lg border border-gray-200 p-4 dark:border-gray-700 dark:bg-gray-800">
                      <div class="flex items-start justify-between gap-3">
                        <span class="font-semibold text-gray-900 dark:text-white">
                          {row.team}
                        </span>
                        <span class="font-semibold tabular-nums text-gray-900 dark:text-white">
                          {inr(row.amount)}
                        </span>
                      </div>
                      <p class="mt-1 text-sm text-gray-600 dark:text-gray-300">
                        {row.payer.name} · <What row={row} />
                      </p>
                      <div class="mt-2 flex items-center justify-between gap-3">
                        <StatusBadge row={row} />
                        <span class={clsx(muted, "text-xs")}>
                          {day(row.date)}
                        </span>
                      </div>
                      <p class="mt-1 break-all font-mono text-xs text-gray-500">
                        {row.payment_id}
                      </p>
                    </li>
                  )}
                </For>
              </ul>
              {/* A table on anything wider */}
              <div class="hidden overflow-x-auto md:block">
                <table class="w-full text-left text-sm tabular-nums text-gray-600 dark:text-gray-300">
                  <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                    <tr>
                      <th scope="col" class="px-4 py-3">
                        Date
                      </th>
                      <th scope="col" class="px-4 py-3">
                        Team
                      </th>
                      <th scope="col" class="px-4 py-3">
                        Paid by
                      </th>
                      <th scope="col" class="px-4 py-3">
                        For
                      </th>
                      <th scope="col" class="px-4 py-3 text-right">
                        Amount
                      </th>
                      <th scope="col" class="px-4 py-3">
                        Status
                      </th>
                      <th scope="col" class="px-4 py-3">
                        Payment ID
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <For each={data().results}>
                      {row => (
                        <tr class="border-b align-top dark:border-gray-700">
                          <td class="whitespace-nowrap px-4 py-3">
                            {day(row.date)}
                          </td>
                          <td class="px-4 py-3 font-medium text-gray-900 dark:text-white">
                            {row.team}
                          </td>
                          <td class="px-4 py-3">{row.payer.name}</td>
                          <td class="px-4 py-3">
                            <What row={row} />
                          </td>
                          <td class="whitespace-nowrap px-4 py-3 text-right font-medium text-gray-900 dark:text-white">
                            {inr(row.amount)}
                          </td>
                          <td class="px-4 py-3">
                            <StatusBadge row={row} />
                          </td>
                          <td class="px-4 py-3 font-mono text-xs">
                            {row.payment_id}
                          </td>
                        </tr>
                      )}
                    </For>
                  </tbody>
                </table>
              </div>
              <Pagination
                page={filters().page}
                pages={pages()}
                onChange={p =>
                  setParams({ page: p === 1 ? null : p }, { scroll: true })
                }
              />
            </Show>
          </Show>
        </Match>
      </Switch>
    </div>
  );
};

export default PaymentAccount;
