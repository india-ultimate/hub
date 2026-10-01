import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { For, Show, Suspense } from "solid-js";

import { inr } from "../../money";
import { fetchReceipts } from "../../queries";

const day = iso =>
  new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  });

const linkClass =
  "inline-flex min-h-[44px] items-center px-2 font-medium text-blue-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-blue-400";

const ReceiptList = () => {
  const query = createQuery(() => ["receipts"], fetchReceipts);
  return (
    <div class="border border-gray-200 p-5 dark:border-gray-700 dark:bg-gray-900">
      <p class="mb-3 text-sm text-gray-500 dark:text-gray-400">
        Receipts and refund notes for subscriptions you have paid for.
      </p>
      <Suspense
        fallback={
          <p class="text-sm text-gray-500 dark:text-gray-400">
            Loading your receipts...
          </p>
        }
      >
        <Show
          when={query.data?.length}
          fallback={
            <p class="text-sm text-gray-500 dark:text-gray-400">
              {/* Empty only once the list really arrived: a request still in
                  flight or one that failed must not read as "you have none". */}
              <Show
                when={query.isSuccess}
                fallback="Your receipts could not be loaded. Please try again in a moment."
              >
                No receipts yet. One appears here when you pay for a
                subscription.
              </Show>
            </p>
          }
        >
          <div class="relative overflow-x-auto">
            <table class="w-full text-left text-sm tabular-nums text-gray-600 dark:text-gray-300">
              <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                <tr>
                  <th scope="col" class="whitespace-nowrap px-4 py-3">
                    Number
                  </th>
                  <th scope="col" class="whitespace-nowrap px-4 py-3">
                    Date
                  </th>
                  <th scope="col" class="px-4 py-3">
                    For
                  </th>
                  <th
                    scope="col"
                    class="whitespace-nowrap px-4 py-3 text-right"
                  >
                    Amount INR
                  </th>
                  <th scope="col" class="px-4 py-3">
                    <span class="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <For each={query.data}>
                  {receipt => {
                    const note = receipt.kind === "refund";
                    return (
                      <tr
                        class={`border-b dark:border-gray-700 ${
                          note
                            ? "bg-amber-50/60 dark:bg-gray-800"
                            : "bg-white dark:bg-gray-900"
                        }`}
                      >
                        <td
                          class={`whitespace-nowrap py-3 font-mono font-medium text-gray-900 dark:text-white ${
                            note ? "pl-8 pr-4" : "px-4"
                          }`}
                        >
                          {receipt.number}
                        </td>
                        <td class="whitespace-nowrap px-4 py-3">
                          {day(receipt.date)}
                        </td>
                        <td class="px-4 py-3">{receipt.summary}</td>
                        <td
                          class={`whitespace-nowrap px-4 py-3 text-right font-mono ${
                            note ? "text-amber-700 dark:text-amber-400" : ""
                          }`}
                        >
                          {note ? "−" : ""}
                          {inr(receipt.total)}
                        </td>
                        <td class="whitespace-nowrap px-4 py-1">
                          <A href={`/receipts/${receipt.id}`} class={linkClass}>
                            View
                          </A>
                          <a
                            href={`/api/receipts/${receipt.id}/pdf`}
                            class={linkClass}
                          >
                            PDF
                          </a>
                        </td>
                      </tr>
                    );
                  }}
                </For>
              </tbody>
            </table>
          </div>
        </Show>
      </Suspense>
    </div>
  );
};

export default ReceiptList;
