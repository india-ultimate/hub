import { useNavigate, A } from "@solidjs/router";
import { createSignal, createEffect, onMount, Show } from "solid-js";
import { fetchUserData } from "../utils";
import { useStore } from "../store";
import Player from "./Player";
import TransactionList from "./TransactionList";
import { AccordionDownIcon } from "../icons";
import { initFlowbite } from "flowbite";

const Actions = props => {
  return (
    <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
      <tbody>
        <Show when={!props.player}>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              <A
                href="/registration/me"
                class="font-medium text-blue-600 dark:text-blue-500 hover:underline"
              >
                Register yourself as a player
              </A>
            </th>
          </tr>
        </Show>
        <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
          <th
            scope="row"
            class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
          >
            <A
              href="/registration/others"
              class="font-medium text-blue-600 dark:text-blue-500 hover:underline"
            >
              Fill the membership form for another player
            </A>
          </th>
        </tr>
        <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
          <th
            scope="row"
            class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
          >
            <A
              href="/registration/ward"
              class="font-medium text-blue-600 dark:text-blue-500 hover:underline"
            >
              Fill the membership form for a ward
            </A>
          </th>
          <td class="px-6 py-4" />
        </tr>
        <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
          <th
            scope="row"
            class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
          >
            <A
              href="/membership/group"
              class="font-medium text-blue-600 dark:text-blue-500 hover:underline"
            >
              Pay the membership fee for a group
            </A>
          </th>
          <td class="px-6 py-4" />
        </tr>
      </tbody>
    </table>
  );
};

const Home = () => {
  const [store, { setLoggedIn, setData }] = useStore();
  const [playerAccordion, setPlayerAccordion] = createSignal(false);
  const [wardAccordion, setWardAccordion] = createSignal({});

  createEffect(() => {
    if (!store.loggedIn) {
      const navigate = useNavigate();
      navigate("/login", { replace: true });
    }
  });

  onMount(() => {
    if (!store?.data?.username) {
      fetchUserData(setLoggedIn, setData);
    }
  });

  createEffect(() => {
    if (store?.data?.player || store?.data?.wards) {
      initFlowbite();
    }
  });

  return (
    <div>
      <h1 class="text-4xl font-bold mb-4 text-red-500">
        Welcome {store?.data?.full_name || store?.data?.username}!
      </h1>
      <div
        id="accordion-flush"
        data-accordion="collapse"
        data-active-classes="bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
        data-inactive-classes="text-gray-500 dark:text-gray-400"
      >
        <h2 id="accordion-heading-actions">
          <button
            type="button"
            class="flex items-center justify-between w-full py-5 font-medium text-left text-gray-500 border-b border-gray-200 dark:border-gray-700 dark:text-gray-400"
            data-accordion-target="#accordion-body-actions"
            aria-expanded="true"
            aria-controls="accordion-body-actions"
          >
            <span>User Actions</span>
            <AccordionDownIcon />
          </button>
        </h2>
        <div
          id="accordion-body-actions"
          class="hidden"
          aria-labelledby="accordion-heading-actions"
        >
          <div class="py-5 border-b border-gray-200 dark:border-gray-700">
            <Actions player={store.data.player} />
          </div>
        </div>
        <Show when={store.data.player}>
          <h2 id="accordion-heading-player">
            <button
              type="button"
              class="flex items-center justify-between w-full py-5 font-medium text-left text-gray-500 border-b border-gray-200 dark:border-gray-700 dark:text-gray-400"
              data-accordion-target="#accordion-body-player"
              aria-expanded="false"
              aria-controls="accordion-body-player"
            >
              <span>Player Information</span>
              <AccordionDownIcon />
            </button>
          </h2>
          <div
            id="accordion-body-player"
            class="hidden"
            aria-labelledby="accordion-heading-player"
          >
            <div class="py-5 border-b border-gray-200 dark:border-gray-700">
              <Player player={store.data.player} />
            </div>
          </div>
        </Show>
        <h2 id="accordion-heading-transactions">
          <button
            type="button"
            class="flex items-center justify-between w-full py-5 font-medium text-left text-gray-500 border-b border-gray-200 dark:border-gray-700 dark:text-gray-400"
            data-accordion-target="#accordion-body-transactions"
            aria-expanded="false"
            aria-controls="accordion-body-transactions"
          >
            <span>Transactions</span>
            <AccordionDownIcon />
          </button>
        </h2>
        <div
          id="accordion-body-transactions"
          class="hidden"
          aria-labelledby="accordion-heading-transactions"
        >
          <div class="py-5 border-b border-gray-200 dark:border-gray-700">
            <TransactionList />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home;
