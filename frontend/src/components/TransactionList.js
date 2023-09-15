import { fetchUrl } from "../utils";
import { createSignal, onMount, Show, For } from "solid-js";

const PlayersList = props => {
  return (
    <ul class="w-48 text-sm font-medium text-gray-900 bg-white border border-gray-200 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white">
      <For each={props.players}>
        {player_name => (
          <li class="w-full px-4 py-2 border-b border-gray-200 rounded-t-lg dark:border-gray-600">
            {player_name}
          </li>
        )}
      </For>
    </ul>
  );
};

const TransactionList = () => {
  const [transactions, setTransactions] = createSignal([]);

  const transactionsSuccessHandler = async response => {
    const data = await response.json();
    if (response.ok) {
      setTransactions(data);
    } else {
      console.log(data);
    }
  };

  onMount(() => {
    fetchUrl("/api/transactions", transactionsSuccessHandler, error =>
      console.log(error)
    );
  });

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
                Status
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
                Order ID
              </th>
              <th scope="col" class="px-6 py-3">
                Payment ID
              </th>
            </tr>
          </thead>
          <tbody>
            <For each={transactions()}>
              {transaction => {
                let date = new Date(
                  transaction.payment_date
                ).toLocaleDateString("en-IN", {
                  year: "numeric",
                  month: "long",
                  day: "numeric"
                });
                let nPlayers = transaction.players?.length;
                let bgColor;
                switch (transaction.status) {
                  case "completed":
                    bgColor = "bg-green-200 dark:bg-green-800";
                    break;
                  case "failed":
                    bgColor = "bg-red-300 dark:bg-red-700";
                    break;
                  case "created":
                    bgColor = "bg-orange-100 dark:bg-orange-900";
                    break;
                  default:
                    bgColor = "bg-white dark:bg-gray-900";
                    break;
                }

                return (
                  <tr
                    class={`${bgColor} border-b dark:bg-gray-800 dark:border-gray-700`}
                  >
                    <th
                      scope="row"
                      class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                    >
                      {date}
                    </th>
                    <td class="px-6 py-4">{transaction.status}</td>
                    <td class="px-6 py-4">₹ {transaction.amount / 100}</td>
                    <td class="px-6 py-4">{transaction.user}</td>
                    <td class="px-6 py-4">
                      <Show
                        when={nPlayers !== 1}
                        fallback={transaction.players[0]}
                      >
                        <PlayersList players={transaction.players} />
                      </Show>
                    </td>
                    <td class="px-6 py-4">
                      {transaction.event?.title || "Annual"}
                    </td>
                    <td class="px-6 py-4">{transaction.order_id}</td>
                    <td class="px-6 py-4">{transaction.payment_id}</td>
                  </tr>
                );
              }}
            </For>
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TransactionList;
