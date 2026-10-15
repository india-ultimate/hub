import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/solid-mini";
import { For, Show } from "solid-js";

import { card, focusRing, input } from "../../committees";
import { fetchTicketRoutes, saveTicketRoute } from "../../queries";
import { CATEGORIES } from "../../tickets";

// One category: its committees as removable chips, and a menu to add one.
const Category = props => {
  const slugs = () => props.route.committees;
  const name = slug =>
    props.committees.find(c => c.slug === slug)?.name ?? slug;
  const save = committees =>
    props.save.mutate({ category: props.route.category, committees });

  return (
    <li class={`${card} !p-3`}>
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="w-full font-medium text-gray-900 dark:text-white sm:w-36">
          {props.route.category}
        </h3>
        <For
          each={slugs()}
          fallback={
            <span class="text-sm text-gray-600 dark:text-gray-400">
              No committee: Ops assigns by hand
            </span>
          }
        >
          {slug => (
            <span class="inline-flex min-h-[44px] items-center gap-1 rounded-full bg-blue-100 pl-3 text-sm font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-200">
              {name(slug)}
              <button
                type="button"
                aria-label={`Remove ${name(slug)} from ${props.route.category}`}
                onClick={() => save(slugs().filter(s => s !== slug))}
                class={`inline-flex h-11 w-11 items-center justify-center rounded-full hover:bg-blue-200 dark:hover:bg-blue-800 ${focusRing}`}
              >
                <Icon path={xMark} class="h-4 w-4" aria-hidden="true" />
              </button>
            </span>
          )}
        </For>
        <select
          aria-label={`Add a committee to ${props.route.category}`}
          value=""
          onChange={e => {
            save([...slugs(), e.currentTarget.value]);
            e.currentTarget.value = "";
          }}
          class={`${input} !w-auto sm:ml-auto`}
        >
          <option value="">+ Add</option>
          <For each={props.committees.filter(c => !slugs().includes(c.slug))}>
            {c => <option value={c.slug}>{c.name}</option>}
          </For>
        </select>
      </div>
    </li>
  );
};

// The Ticket routing tab: which committees' chairs a category's new tickets go to.
const ManageRouting = props => {
  const queryClient = useQueryClient();
  const routes = createQuery(() => ["ticket-routes"], fetchTicketRoutes);
  const save = createMutation({
    mutationFn: saveTicketRoute,
    onSuccess: () => {
      props.onSaved();
      queryClient.invalidateQueries({ queryKey: ["ticket-routes"] });
    }
  });
  const routeOf = category =>
    routes.data?.find(r => r.category === category) ?? {
      category,
      committees: []
    };

  return (
    <div>
      <p class="mb-4 text-sm text-gray-600 dark:text-gray-400">
        New tickets go to every chair of these committees. Changes apply to new
        tickets only.
      </p>
      <Show when={save.isError}>
        <p role="alert" class="mb-3 text-sm text-red-700 dark:text-red-400">
          {save.error.message}
        </p>
      </Show>
      <Show when={routes.data}>
        <ul class="space-y-3">
          <For each={CATEGORIES}>
            {category => (
              <Category
                route={routeOf(category)}
                committees={props.committees}
                save={save}
              />
            )}
          </For>
        </ul>
      </Show>
    </div>
  );
};

export default ManageRouting;
