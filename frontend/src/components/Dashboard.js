import { A } from "@solidjs/router";
import { Show, For } from "solid-js";
import { useStore } from "../store";
import Player from "./Player";
import TransactionList from "./TransactionList";
import { AccordionDownIcon } from "../icons";
import { inboxStack } from "solid-heroicons/solid";
import { Icon } from "solid-heroicons";
import { showPlayerStatus } from "../utils";

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
        href="/help#import-players-from-a-spreadsheet"
        class="block w-full px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
      >
        Import players information from a Spreadsheet
      </A>
      <A
        href="/membership/group"
        class="block w-full px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
      >
        Pay the membership fee for a group
      </A>
      <A
        href="/validate-rosters"
        class="block w-full px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
      >
        Validate your Team Roster for an event
      </A>
    </div>
  );
};

const StaffActions = () => {
  return (
    <div class="w-90 text-sm font-medium text-gray-900 bg-white border border-gray-200 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white">
      <A
        href="/players"
        class="block w-full px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
      >
        View Registered players
      </A>
      <A
        href="/validate-rosters"
        class="block w-full px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
      >
        Validate Event Roster
      </A>
      <A
        href="/validate-transactions"
        class="block w-full px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
      >
        Validate Transactions
      </A>
      <A
        href="/tournament-manager"
        class="block w-full px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
      >
        Create / Manage Tournament
      </A>
    </div>
  );
};

const Dashboard = () => {
  const [store] = useStore();
  return (
    <div>
      <div class="w-full">
        <h2 class="flex items-center text-lg font-bold text-gray-900 text-center dark:text-white mb-5 mx-auto w-fit">
          <Icon class="w-6 h-6 mr-2.5" path={inboxStack} />
          Dashboard
        </h2>
      </div>

      <h1 class="text-2xl md:text-4xl font-bold mb-4 text-blue-500">
        Welcome <span>{store?.data?.full_name || store?.data?.username}</span>!
      </h1>
      <div
        id="accordion-flush"
        data-accordion="collapse"
        data-active-classes="bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
        data-inactive-classes="text-gray-500 dark:text-gray-400"
      >
        <Show when={store.data.player}>
          <h2 id="accordion-heading-player">
            <button
              type="button"
              class="flex items-center justify-between w-full py-5 font-medium text-left text-gray-500 border-b border-gray-200 dark:border-gray-700 dark:text-gray-400"
              data-accordion-target="#accordion-body-player"
              aria-expanded="true"
              aria-controls="accordion-body-player"
            >
              <span>Player Information: {store.data.player.full_name} </span>
              <span class="flex">
                {showPlayerStatus(store.data.player)}

                <AccordionDownIcon />
              </span>
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
                    aria-expanded={store?.data?.player ? "false" : "true"}
                    aria-controls={`accordion-body-ward-${ward.id}`}
                  >
                    <span>Player Information: {ward.full_name} </span>
                    <span class="flex">
                      {showPlayerStatus(store.data.player)}
                      <AccordionDownIcon />
                    </span>
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
        <h2 id="accordion-heading-actions">
          <button
            type="button"
            class="flex items-center justify-between w-full py-5 font-medium text-left text-gray-500 border-b border-gray-200 dark:border-gray-700 dark:text-gray-400"
            data-accordion-target="#accordion-body-actions"
            aria-expanded={
              store?.data?.player || store?.data?.wards?.length > 0
                ? "false"
                : "true"
            }
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
        <Show when={store.data.is_staff}>
          <h2 id="accordion-heading-staff">
            <button
              type="button"
              class="flex items-center justify-between w-full py-5 font-medium text-left text-gray-500 border-b border-gray-200 dark:border-gray-700 dark:text-gray-400"
              data-accordion-target="#accordion-body-staff"
              aria-expanded="false"
              aria-controls="accordion-body-staff"
            >
              <span>Staff Actions</span>
              <AccordionDownIcon />
            </button>
          </h2>
          <div
            id="accordion-body-staff"
            class="hidden"
            aria-labelledby="accordion-heading-staff"
          >
            <div class="py-5 border-b border-gray-200 dark:border-gray-700">
              <StaffActions player={store.data.player} />
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

export default Dashboard;
