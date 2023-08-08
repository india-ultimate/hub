import { useNavigate, A } from "@solidjs/router";
import { createSignal, createEffect, onMount, Show, For } from "solid-js";
import { fetchUserData } from "../utils";
import { useStore } from "../store";
import Player from "./Player";
import TransactionList from "./TransactionList";
import { AccordionDownIcon } from "../icons";
import { initFlowbite } from "flowbite";

const Actions = props => {
  return (
    <div class="w-90 text-sm font-medium text-gray-900 bg-white border border-gray-200 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white">
      <Show when={!props.player}>
        <A
          href="/registration/me"
          class="block w-full px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
        >
          Register yourself as a player
        </A>
      </Show>
      <A
        href="/registration/ward"
        class="block w-full px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
      >
        Fill the membership form for a minor player as Guardian
      </A>
      <A
        href="/registration/others"
        class="block w-full px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
      >
        Fill the membership form for another player
      </A>
      <A
        href="/membership/group"
        class="block w-full px-4 py-2 rounded-b-lg cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
      >
        Pay the membership fee for a group
      </A>
    </div>
  );
};

const Home = () => {
  const [store, { setLoggedIn, setData }] = useStore();

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
              <span>Player Information: {store.data.player.full_name}</span>
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
        <Show when={store.data.wards}>
          <For each={store.data.wards}>
            {ward => (
              <>
                <h2 id={`accordion-heading-ward-${ward.id}`}>
                  <button
                    type="button"
                    class="flex items-center justify-between w-full py-5 font-medium text-left text-gray-500 border-b border-gray-200 dark:border-gray-700 dark:text-gray-400"
                    data-accordion-target={`#accordion-body-ward-${ward.id}`}
                    aria-expanded="false"
                    aria-controls={`accordion-body-ward-${ward.id}`}
                  >
                    <span>Player Information: {ward.full_name}</span>
                    <AccordionDownIcon />
                  </button>
                </h2>
                <div
                  id={`accordion-body-ward-${ward.id}`}
                  class="hidden"
                  aria-labelledby={`accordion-heading-ward-${ward.id}`}
                >
                  <div class="py-5 border-b border-gray-200 dark:border-gray-700">
                    <Player player={ward} />
                  </div>
                </div>
              </>
            )}
          </For>
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
