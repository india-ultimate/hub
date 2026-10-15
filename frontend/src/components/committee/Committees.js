import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { arrowRight } from "solid-heroicons/outline";
import { For, Show } from "solid-js";

import { card, EmailLink, focusRing, NoOneListed } from "../../committees";
import { fetchCommittees } from "../../queries";
import { useStore } from "../../store";
import Person from "./Person";

const EXECUTIVE_BOARD = "executive-board";

const CommitteeCard = props => (
  <section
    class={`${card} flex flex-col`}
    aria-labelledby={`committee-${props.committee.slug}`}
  >
    <h2
      id={`committee-${props.committee.slug}`}
      class="text-xl font-semibold text-blue-700 dark:text-white"
    >
      {props.committee.name}
    </h2>
    <Show when={props.committee.description}>
      <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
        {props.committee.description}
      </p>
    </Show>
    <Show when={props.committee.email}>
      <EmailLink email={props.committee.email} />
    </Show>
    <ul class="mt-3 grow space-y-3">
      <For each={props.committee.roles} fallback={<NoOneListed />}>
        {role => (
          <li>
            <Person role={role} />
          </li>
        )}
      </For>
    </ul>
    <A
      href={`/committees/${props.committee.slug}`}
      class={`mt-4 inline-flex min-h-[44px] items-center gap-1 self-start rounded text-sm font-medium text-blue-700 hover:underline dark:text-blue-300 ${focusRing}`}
    >
      View committee
      <Icon path={arrowRight} class="h-4 w-4" aria-hidden="true" />
    </A>
  </section>
);

const Committees = () => {
  const [store] = useStore();
  const query = createQuery(() => ["committees"], fetchCommittees);
  const board = () => query.data?.find(c => c.slug === EXECUTIVE_BOARD);
  const others = () => query.data?.filter(c => c.slug !== EXECUTIVE_BOARD);

  return (
    <div class="mx-auto">
      <div class="mb-8">
        <h1 class="mb-4 text-4xl font-bold text-blue-700 dark:text-white">
          Committees
        </h1>
        <p class="text-lg text-gray-600 dark:text-gray-400">
          The people who run India Ultimate.
        </p>
        <Show when={store.data?.is_staff}>
          <A
            href="/committees/manage"
            class={`mt-2 inline-flex min-h-[44px] items-center rounded text-sm font-medium text-blue-700 underline dark:text-blue-300 ${focusRing}`}
          >
            Manage committees
          </A>
        </Show>
      </div>
      <Show when={query.isError}>
        <p role="alert" class="text-red-700">
          Couldn't load the committees. Please try again.
        </p>
      </Show>
      <Show when={board()}>
        <section class="mb-8" aria-labelledby="executive-board">
          <h2
            id="executive-board"
            class="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400"
          >
            {board().name}
          </h2>
          <ul class="grid grid-cols-2 gap-4 md:grid-cols-4">
            <For each={board().roles} fallback={<NoOneListed />}>
              {role => (
                <li class={`${card} !p-4`}>
                  <Person role={role} stacked />
                </li>
              )}
            </For>
          </ul>
        </section>
      </Show>
      <div class="grid gap-4 lg:grid-cols-2">
        <For each={others()}>
          {committee => <CommitteeCard committee={committee} />}
        </For>
      </div>
    </div>
  );
};

export default Committees;
