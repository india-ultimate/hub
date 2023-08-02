import { getCookie, fetchUrl } from "../utils";
import { createSignal, onMount, Switch, Match, For } from "solid-js";
import { initFlowbite } from "flowbite";
import { AccordionDownIcon } from "../icons";

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

  onMount(async () => {
    initFlowbite();
  });

  onMount(() => {
    fetchUrl("/api/transactions", transactionsSuccessHandler, error =>
      console.log(error)
    );
  });

  return (
    <div id="accordion-collapse" data-accordion="collapse">
      <h3
        class="text-2xl font-bold text-gray-500"
        id="accordion-collapse-heading-1"
      >
        <button
          type="button"
          class="flex items-center justify-between w-full p-5 font-medium text-left text-gray-500 border border-b-0 border-gray-200 rounded-t-xl focus:ring-4 focus:ring-gray-200 dark:focus:ring-gray-800 dark:border-gray-700 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
          data-accordion-target="#accordion-collapse-body-1"
          aria-expanded="true"
          aria-controls="accordion-collapse-body-1"
        >
          Transactions
          <AccordionDownIcon />
        </button>
      </h3>
      <div
        id="accordion-collapse-body-1"
        class="hidden"
        aria-labelledby="accordion-collapse-heading-1"
      >
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

                    return (
                      <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
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
                          <Switch fallback={transaction.players[0].full_name}>
                            <Match when={nPlayers !== 1}>
                              <PlayersList players={transaction.players} />
                            </Match>
                          </Switch>
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
      </div>
    </div>
  );
};

export default TransactionList;
