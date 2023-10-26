import { Show, For, Suspense, createSignal, createEffect } from "solid-js";
import { createQuery } from "@tanstack/solid-query";
import {
  fetchTransactions,
  fetchAllTransactions,
  fetchAllInvalidTransactions
} from "../queries";
import TransactionsSkeleton from "../skeletons/Transactions";
import TransactionPlayersList from "./TransactionPlayersList";

const TransactionList = props => {
  const [query, setQuery] = createSignal();

  createEffect(() => {
    const _ts = props.ts; // Added to trigger a refetch if required
    const q = createQuery(
      () => ["transactions"],
      props.admin
        ? props.onlyInvalid
          ? fetchAllInvalidTransactions
          : fetchAllTransactions
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
        class="hover:underline underline-offset-4 font-semibold after:content-['_↗']"
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
    <div class="p-5 border border-gray-200 dark:border-gray-700 dark:bg-gray-900">
      <div class="relative overflow-x-auto">
        <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
          <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
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
                      class={`${bgColor} border-b dark:bg-gray-800 dark:border-gray-700 text-gray-900 dark:text-white`}
                    >
                      <th
                        scope="row"
                        class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
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
                      <Show when={props.admin}>
                        <td class="px-6 py-4">
                          <button
                            data-modal-target="validationModal"
                            data-modal-toggle="validationModal"
                            class="text-sm text-white bg-gray-700 hover:bg-gray-800 focus:ring-4 focus:outline-none focus:ring-gray-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-gray-600 dark:hover:bg-gray-700 dark:focus:ring-gray-800"
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
