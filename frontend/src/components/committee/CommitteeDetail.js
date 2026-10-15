import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { For, Show } from "solid-js";

import { card, EmailLink, NoOneListed, termLabel } from "../../committees";
import { fetchCommittee } from "../../queries";
import Error404 from "../Error404";
import Person from "./Person";

const CommitteeDetail = () => {
  const params = useParams();
  const query = createQuery(
    () => ["committee", params.slug],
    () => fetchCommittee(params.slug)
  );
  const committee = () => query.data;
  const past = () => [
    ...committee().past_roles.reduce((terms, role) => {
      const term = termLabel(role);
      return terms.set(term, [...(terms.get(term) ?? []), role]);
    }, new Map())
  ];

  return (
    <Show
      when={!query.isError}
      fallback={
        <Show
          when={query.error?.status === 404}
          fallback={
            <p role="alert" class="text-red-700">
              Couldn't load this committee. Try again later.
            </p>
          }
        >
          <Error404 />
        </Show>
      }
    >
      <Show when={committee()}>
        <div class="mx-auto max-w-3xl">
          <A
            href="/committees"
            class="text-sm text-blue-700 hover:underline dark:text-blue-300"
          >
            All committees
          </A>
          <h1 class="mb-2 mt-2 text-4xl font-bold text-blue-700 dark:text-white">
            {committee().name}
          </h1>
          <Show when={committee().description}>
            <p class="text-lg text-gray-600 dark:text-gray-400">
              {committee().description}
            </p>
          </Show>
          <Show when={committee().email}>
            <EmailLink email={committee().email} />
          </Show>
          <section class={`${card} mt-6`} aria-labelledby="current-heading">
            <h2
              id="current-heading"
              class="mb-3 text-xl font-semibold text-blue-700 dark:text-white"
            >
              Current members
            </h2>
            <ul class="space-y-3">
              <For each={committee().roles} fallback={<NoOneListed />}>
                {role => (
                  <li>
                    <Person role={role} />
                  </li>
                )}
              </For>
            </ul>
          </section>
          <Show when={committee().past_roles.length}>
            <section class="mt-8" aria-labelledby="past-heading">
              <h2
                id="past-heading"
                class="mb-3 text-xl font-semibold text-blue-700 dark:text-white"
              >
                Past members
              </h2>
              <For each={past()}>
                {([term, roles]) => (
                  <div class="mb-4">
                    <h3 class="mb-2 text-sm font-semibold text-gray-600 dark:text-gray-400">
                      {term}
                    </h3>
                    <ul class="space-y-3">
                      <For each={roles}>
                        {role => (
                          <li>
                            <Person role={role} />
                          </li>
                        )}
                      </For>
                    </ul>
                  </div>
                )}
              </For>
            </section>
          </Show>
        </div>
      </Show>
    </Show>
  );
};

export default CommitteeDetail;
