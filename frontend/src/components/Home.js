import { useNavigate, A } from "@solidjs/router";
import { createSignal, createEffect, onMount, Show } from "solid-js";
import { fetchUserData } from "../utils";
import { useStore } from "../store";
import Player from "./Player";
import TransactionList from "./TransactionList";

const Home = () => {
  const [store, { setLoggedIn, setData }] = useStore();
  const [ playerAccordion, setPlayerAccordion ] = createSignal(false);
  const [ wardAccordion, setWardAccordion ] = createSignal({});

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

  const togglePlayerAccordion = () => {
    setPlayerAccordion(!playerAccordion());
  };

  const getWardsWithIndices = () => {
    return store.data.wards.map((ward, index) => ({ ward, index }));
  };

  const wardsWithIndices = getWardsWithIndices();
  console.log(wardsWithIndices);

  return (
    <div>
      <h1 class="text-4xl font-bold mb-4 text-red-500">
        Welcome {store?.data?.full_name || store?.data?.username}!
      </h1>
      <div class="relative overflow-x-auto">
        <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
          <tbody>
            <Show when={!store.data.player}>
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
      </div>
      <Show when={store.data.player}>
        <div
          id="accordion-flush"
          data-accordion="open"
          data-active-classes="bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
          data-inactive-classes="text-gray-500 dark:text-gray-400">
          <h2 id="accordion-flush-heading-1">
            <button
              type="button"
              class="flex items-center justify-between w-full py-5 font-medium text-left text-gray-500 border-b border-gray-200 dark:border-gray-700 dark:text-gray-400"
              data-accordion-target="#accordion-flush-body-1"
              aria-expanded="true"
              aria-controls="accordion-flush-body-1"
              onClick={togglePlayerAccordion}
            >
              <span class="text-red-600 dark:text-red-500">Player information</span>
              <svg data-accordion-icon class={`w-3 h-3 shrink-0 ${ playerAccordion() ? "rotate-180" : "rotate-0" }`} aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 10 6">
                <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5 5 1 1 5"/>
              </svg>
            </button>
          </h2>
          <div
            id="accordion-flush-body-1"
            class={`${playerAccordion() ? "" : "hidden"}`}
            aria-labelledby="accordion-flush-heading-1">
            <div class="py-5 border-b border-gray-200 dark:border-gray-700">
              <Player player={store.data.player} />
            </div>
          </div>
        </div>
      </Show>
      <TransactionList />
      <div />
      <Show when={store.data.wards}>
        <div>
          {wardsWithIndices.map(({ ward, index }) => (
            <div key={index}>
              <Player player={ward} />
            </div>
          ))}
        </div>
      </Show>
    </div>
  );
};

export default Home;
