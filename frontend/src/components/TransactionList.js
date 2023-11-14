import { createQuery } from "@tanstack/solid-query";
import { createEffect, createSignal, For, Show, Suspense } from "solid-js";

import { transactionTypes } from "../constants";
import {
  fetchAllInvalidManualTransactions,
  fetchAllManualTransactions,
  fetchTransactions
} from "../queries";
import TransactionsSkeleton from "../skeletons/Transactions";
import { getLabel } from "../utils";
import TransactionPlayersList from "./TransactionPlayersList";

const TransactionList = props => {
  const [query, setQuery] = createSignal();

  createEffect(() => {
    const _ts = props.ts; // Added to trigger a refetch if required
    const q = createQuery(
      () => ["transactions"],
      props.admin
        ? props.onlyInvalid
          ? fetchAllInvalidManualTransactions
          : fetchAllManualTransactions
        : fetchTransactions,
      {
        refetchOnWindowFocus: false
      }
    );
    setQuery(q);
  });

  const renderWhatsappLink = phone => (
    <span>
      {phone.slice(0, 1)}
      <a
        class="font-semibold underline-offset-4 after:content-['_↗'] hover:underline"
        href={`https://api.whatsapp.com/send?phone=${phone.slice(1)}`}
      >
        {phone.slice(1)}
      </a>
    </span>
  );

  const getPaidBy = user => {
    return (
      <span>
        {user.first_name} {user.last_name} ({" "}
        {props.admin ? renderWhatsappLink(user.phone) : ""} )
      </span>
    );
  };

  return (
    <div class="border border-gray-200 p-5 dark:border-gray-700 dark:bg-gray-900">
      <div class="relative overflow-x-auto">
        <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
          <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
            <tr>
              <th scope="col" class="px-6 py-3">
                Date
              </th>
              <th scope="col" class="px-6 py-3">
                Amount
              </th>
              <th scope="col" class="px-6 py-3">
                Paid By
              </th>
              <th scope="col" class="px-6 py-3">
                Players
              </th>
              <th scope="col" class="px-6 py-3">
                Annual / Event
              </th>
              <th scope="col" class="px-6 py-3">
                Transaction ID
              </th>
              <th scope="col" class="px-6 py-3">
                Transaction Type
              </th>
              <Show when={props.admin}>
                <th scope="col" class="px-6 py-3">
                  Validate
                </th>
              </Show>
            </tr>
          </thead>
          <tbody>
            <Suspense fallback={<TransactionsSkeleton />}>
              <For each={query()?.data}>
                {transaction => {
                  let date = new Date(
                    transaction.payment_date
                  ).toLocaleDateString("en-IN", {
                    year: "numeric",
                    month: "long",
                    day: "numeric"
                  });
                  let nPlayers = transaction.players?.length;
                  const bgColor = transaction.validated
                    ? "bg-green-200 dark:bg-green-800"
                    : "bg-orange-100 dark:bg-orange-900";

                  return (
                    <tr
                      class={`${bgColor} border-b text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-white`}
                    >
                      <th
                        scope="row"
                        class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
                      >
                        {date}
                      </th>
                      <td class="px-6 py-4">₹ {transaction.amount / 100}</td>
                      <td class="px-6 py-4">{getPaidBy(transaction.user)}</td>
                      <td class="px-6 py-4">
                        <Show
                          when={nPlayers !== 1}
                          fallback={transaction.players[0]}
                        >
                          <TransactionPlayersList
                            players={transaction.players}
                          />
                        </Show>
                      </td>
                      <td class="px-6 py-4">
                        {transaction.event?.title || "Annual"}
                      </td>
                      <td class="px-6 py-4">{transaction.transaction_id}</td>
                      <td class="px-6 py-4">
                        {getLabel(transactionTypes, transaction.type)}
                      </td>
                      <Show when={props.admin}>
                        <td class="px-6 py-4">
                          <button
                            data-modal-target="validationModal"
                            data-modal-toggle="validationModal"
                            class="w-full rounded-lg bg-gray-700 px-5 py-2.5 text-center text-sm text-sm font-medium text-white hover:bg-gray-800 focus:outline-none focus:ring-4 focus:ring-gray-300 dark:bg-gray-600 dark:hover:bg-gray-700 dark:focus:ring-gray-800 sm:w-auto"
                            onClick={() => props.setTransaction(transaction)}
                          >
                            Validate
                          </button>
                        </td>
                      </Show>
                    </tr>
                  );
                }}
              </For>
            </Suspense>
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TransactionList;
