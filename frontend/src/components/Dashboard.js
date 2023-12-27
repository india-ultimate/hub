import { supported } from "@github/webauthn-json/browser-ponyfill";
import { A } from "@solidjs/router";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import { inboxStack } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import { AccordionDownIcon } from "../icons";
import { useStore } from "../store";
import { registerPasskey, showPlayerStatus } from "../utils";
import Player from "./Player";
import TransactionList from "./TransactionList";

const Actions = props => {
  const onCreatePasskeyClick = async () => {
    props.setSuccess(false);
    props.setError(false);

    const response = await registerPasskey();

    if (response.success) {
      props.setSuccess(response.success);
    }
    if (response.error) {
      props.setError(response.error);
    }

    initFlowbite();
  };

  return (
    <div class="w-90 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white">
      <Show when={!props.player}>
        <A
          href="/registration/me"
          class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
        >
          Register yourself as a player
        </A>
      </Show>
      <A
        href="/registration/ward"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Fill the membership form for a minor player as Guardian
      </A>
      <A
        href="/registration/others"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Fill the membership form for another player
      </A>
      <A
        href="/help#import-players-from-a-spreadsheet"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Import players information from a Spreadsheet
      </A>
      <A
        href="/membership/group"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Pay the membership fee for a group
      </A>
      <A
        href="/validate-rosters"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Validate your Team Roster for an event
      </A>
      <button
        disabled={!supported()}
        onClick={onCreatePasskeyClick}
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 text-left hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 disabled:text-gray-600 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500 disabled:dark:text-gray-400"
      >
        <Show
          when={supported()}
          fallback={"One-Tab Login is not available for this browser or device"}
        >
          Enable One-Tap Login for this device
        </Show>
      </button>
    </div>
  );
};

const StaffActions = () => {
  return (
    <div class="w-90 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white">
      <A
        href="/players"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        View Registered players
      </A>
      <A
        href="/validate-rosters"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Validate Event Roster
      </A>
      <A
        href="/validate-transactions"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Validate Transactions
      </A>
      <A
        href="/check-memberships"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Check Membership Status
      </A>
      <A
        href="/tournament-manager"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Create / Manage Tournament
      </A>
    </div>
  );
};

const Dashboard = () => {
  const [store] = useStore();
  const [success, setSuccess] = createSignal();
  const [error, setError] = createSignal();

  createEffect(() => {
    console.log(success(), error());
  });

  return (
    <div>
      <div class="w-full">
        <h2 class="mx-auto mb-5 flex w-fit items-center text-center text-lg font-bold text-gray-900 dark:text-white">
          <Icon class="mr-2.5 h-6 w-6" path={inboxStack} />
          Dashboard
        </h2>
      </div>

      <h1 class="mb-4 text-2xl font-bold text-blue-500 md:text-4xl">
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
              class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
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
            <div class="border-b border-gray-200 py-5 dark:border-gray-700">
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
                    class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
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
                  <div class="border-b border-gray-200 py-5 dark:border-gray-700">
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
            class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
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
          <div class="border-b border-gray-200 py-5 dark:border-gray-700">
            <Actions
              player={store.data.player}
              setSuccess={setSuccess}
              setError={setError}
            />
          </div>
        </div>
        <Show when={store.data.is_staff}>
          <h2 id="accordion-heading-staff">
            <button
              type="button"
              class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
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
            <div class="border-b border-gray-200 py-5 dark:border-gray-700">
              <StaffActions player={store.data.player} />
            </div>
          </div>
        </Show>
        <h2 id="accordion-heading-transactions">
          <button
            type="button"
            class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
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
          <div class="border-b border-gray-200 py-5 dark:border-gray-700">
            <TransactionList />
          </div>
        </div>
      </div>

      <Show when={success()}>
        <div
          id="toast-success"
          class="fixed left-1/2 top-24 mb-4 flex w-full max-w-xs -translate-x-1/2 items-center rounded-lg bg-white p-4 text-gray-500 shadow dark:bg-gray-800 dark:text-gray-400"
          role="alert"
        >
          <div class="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-green-100 text-green-500 dark:bg-green-800 dark:text-green-200">
            <svg
              class="h-5 w-5"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5Zm3.707 8.207-4 4a1 1 0 0 1-1.414 0l-2-2a1 1 0 0 1 1.414-1.414L9 10.586l3.293-3.293a1 1 0 0 1 1.414 1.414Z" />
            </svg>
            <span class="sr-only">Check icon</span>
          </div>
          <div class="ms-3 text-sm font-normal">{success()}</div>
          <button
            type="button"
            class="-mx-1.5 -my-1.5 ms-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-900 focus:ring-2 focus:ring-gray-300 dark:bg-gray-800 dark:text-gray-500 dark:hover:bg-gray-700 dark:hover:text-white"
            data-dismiss-target="#toast-success"
            aria-label="Close"
          >
            <span class="sr-only">Close</span>
            <svg
              class="h-3 w-3"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 14 14"
            >
              <path
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="m1 1 6 6m0 0 6 6M7 7l6-6M7 7l-6 6"
              />
            </svg>
          </button>
        </div>
      </Show>

      <Show when={error()}>
        <div
          id="toast-danger"
          class="fixed left-1/2 top-24 mb-4 flex w-full max-w-xs -translate-x-1/2 items-center rounded-lg bg-white p-4 text-gray-500 shadow dark:bg-gray-800 dark:text-gray-400"
          role="alert"
        >
          <div class="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-red-100 text-red-500 dark:bg-red-800 dark:text-red-200">
            <svg
              class="h-5 w-5"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5Zm3.707 11.793a1 1 0 1 1-1.414 1.414L10 11.414l-2.293 2.293a1 1 0 0 1-1.414-1.414L8.586 10 6.293 7.707a1 1 0 0 1 1.414-1.414L10 8.586l2.293-2.293a1 1 0 0 1 1.414 1.414L11.414 10l2.293 2.293Z" />
            </svg>
            <span class="sr-only">Error icon</span>
          </div>
          <div class="ms-3 text-sm font-normal">{error()}</div>
          <button
            type="button"
            class="-mx-1.5 -my-1.5 ms-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-900 focus:ring-2 focus:ring-gray-300 dark:bg-gray-800 dark:text-gray-500 dark:hover:bg-gray-700 dark:hover:text-white"
            data-dismiss-target="#toast-danger"
            aria-label="Close"
          >
            <span class="sr-only">Close</span>
            <svg
              class="h-3 w-3"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 14 14"
            >
              <path
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="m1 1 6 6m0 0 6 6M7 7l6-6M7 7l-6 6"
              />
            </svg>
          </button>
        </div>
      </Show>
    </div>
  );
};

export default Dashboard;
