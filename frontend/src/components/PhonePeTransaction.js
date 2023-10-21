import { getCookie, fetchUserData } from "../utils";
import { useStore } from "../store";
import {
  createSignal,
  Show,
  onMount,
  createEffect,
  Switch,
  Match
} from "solid-js";
import { useParams, useSearchParams, A } from "@solidjs/router";
import TransactionPlayersList from "./TransactionPlayersList";
import Breadcrumbs from "./Breadcrumbs";
import { inboxStack } from "solid-heroicons/solid";

const PhonePeTransaction = () => {
  const [status, setStatus] = createSignal("");
  const [transaction, setTransaction] = createSignal({});
  const [queryCounter, setQueryCounter] = createSignal(0);
  const [interval, setInterval] = createSignal(3000);
  const [searchParams, _] = useSearchParams();
  const params = useParams();

  const [_store, { userFetchSuccess, userFetchFailure }] = useStore();

  const fetchTransaction = transactionId => {
    setStatus(
      transaction()?.transaction_id
        ? "Refreshing transaction data..."
        : "Fetching transaction data..."
    );
    setQueryCounter(queryCounter() + 1);
    fetch(`/api/phonepe-transaction/${transactionId}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    })
      .then(async response => {
        if (response.ok) {
          const data = await response.json();
          setTransaction(data);
          fetchUserData(userFetchSuccess, userFetchFailure);
        } else {
          if (response.status === 422) {
            const error = await response.json();
            setStatus(`Error: ${error.message}`);
          } else {
            const body = await response.text();
            setStatus(
              `Error: ${response.statusText} (${response.status}) — ${body}`
            );
          }
        }
        setStatus("");
      })
      .catch(error => {
        setStatus(`Error: ${error}`);
      });
  };

  onMount(() => {
    fetchTransaction(params.transactionId);
  });

  createEffect(() => {
    // The Check Status API Reconciliation is implemented here...

    // NOTE: The recommendation in the docs is as follows, but we implement an
    // approximation of it. The backend has a cronjob that does the
    // reconciliation for every pending transaction, once an hour.

    // Every 3 seconds once for the next 30 seconds,
    // Every 6 seconds once for the next 60 seconds,
    // Every 10 seconds for the next 60 seconds,
    // Every 30 seconds for the next 60 seconds, and then
    // Every 1 min until timeout (20 mins).
    if (transaction()?.status === "pending" && interval() > 0) {
      setTimeout(fetchTransaction, interval(), params.transactionId);
    }
  });

  createEffect(() => {
    queryCounter() > 20
      ? setInterval(0)
      : queryCounter() > 10
      ? setInterval(6000)
      : setInterval(3000);
  });

  return (
    <>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "PhonePe Transaction" }
        ]}
      />
      <Show when={transaction()?.transaction_id}>
        <div class="relative overflow-x-auto">
          <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
            <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
              <tr>
                <th scope="col" class="px-6 py-3">
                  Transaction ID
                </th>
                <th scope="col" class="px-6 py-3">
                  {transaction().transaction_id}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                <th
                  scope="row"
                  class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                >
                  Transaction Amount
                </th>
                <td class="px-6 py-4">₹ {transaction().amount / 100}</td>
              </tr>
              <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                <th
                  scope="row"
                  class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                >
                  Transaction Status
                </th>
                <td class="px-6 py-4">{transaction().status}</td>
              </tr>
              <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                <th
                  scope="row"
                  class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                >
                  Transaction Player(s)
                </th>
                <td class="px-6 py-4">
                  <Switch>
                    <Match when={transaction().players?.length > 1}>
                      <TransactionPlayersList players={transaction().players} />
                    </Match>
                    <Match when={transaction().players?.length == 1}>
                      {transaction().players[0]}
                    </Match>
                    <Match when={!transaction().players?.length}>—</Match>
                  </Switch>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Show>
      <Show when={transaction().status === "pending" && queryCounter() >= 0}>
        <div
          class="p-4 mb-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400"
          role="alert"
        >
          The transaction information will be automatically refreshed in{" "}
          {interval() / 1000} seconds. If the transaction isn't marked as
          successful in 1 minutes, please check the status 1 hour later or get
          in touch with the India Ultimate Operations team.
        </div>
      </Show>
      <Show when={transaction().status === "pending" && queryCounter() < 0}>
        <div
          class="p-4 mb-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400"
          role="alert"
        >
          The transaction is pending. Please check the status 1 hour later or
          get in touch with the India Ultimate Operations team.
        </div>
      </Show>
      <Show when={transaction().status === "success"}>
        Payment successfully completed! 🎉
      </Show>
      <Show when={searchParams.next}>
        <p>
          <A class="text-blue-600 dark:text-blue-500" href={searchParams.next}>
            Go Back
          </A>
        </p>
      </Show>
      <Show when={status()}>
        <p>{status()}</p>
      </Show>
    </>
  );
};

export default PhonePeTransaction;
