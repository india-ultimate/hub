import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { arrowDown, arrowUp, xMark } from "solid-heroicons/solid-mini";
import { createMemo, createSignal, For, Show } from "solid-js";

import {
  card,
  createSaved,
  Field,
  focusRing,
  input,
  primaryButton,
  secondaryButton
} from "../../committees";
import {
  addTicketCategory,
  fetchCommittees,
  fetchTicketCategories,
  fetchTicketRoutes,
  saveTicketRoute,
  updateTicketCategory
} from "../../queries";

const iconButton = `inline-flex h-11 w-11 items-center justify-center rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-100 disabled:opacity-40 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700 ${focusRing}`;

// The category's name: saves on Enter or blur, with the error beside it. A
// name that can't be saved goes back to the saved one.
const NameInput = props => {
  const [saved, flash] = createSaved();
  let field;
  const save = name => {
    name = name.trim();
    if (name === props.category.name) {
      field.value = name;
      return;
    }
    props.setError("");
    if (!name) {
      field.value = props.category.name;
      return props.setError("Give the category a name.");
    }
    props.update.mutate(
      { key: props.category.key, name },
      {
        onSuccess: flash,
        onError: e => {
          field.value = props.category.name;
          props.setError(e.message);
        }
      }
    );
  };

  return (
    <Field
      class="w-full sm:w-52"
      id={`name-${props.category.key}`}
      label={`Name of ${props.category.name}`}
      error={props.error}
    >
      <input
        ref={field}
        id={`name-${props.category.key}`}
        type="text"
        value={props.category.name}
        maxLength={100}
        onChange={e => save(e.currentTarget.value)}
        onKeyDown={e => e.key === "Enter" && e.currentTarget.blur()}
        class={input}
      />
      <p role="status" class="h-5 text-sm text-green-700 dark:text-green-400">
        <Show when={saved()}>Saved</Show>
      </p>
    </Field>
  );
};

// One category: its committees as removable chips, and a menu to add one.
const Committees = props => {
  const slugs = () => props.route.committees;
  const name = slug =>
    props.committees.find(c => c.slug === slug)?.name ?? slug;
  const save = committees =>
    props.save.mutate({ category: props.route.category, committees });

  return (
    <div class="flex flex-wrap items-center gap-2">
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
              aria-label={`Remove ${name(slug)} from ${props.name}`}
              disabled={props.busy}
              onClick={() => save(slugs().filter(s => s !== slug))}
              class={`inline-flex h-11 w-11 items-center justify-center rounded-full hover:bg-blue-200 disabled:opacity-40 dark:hover:bg-blue-800 ${focusRing}`}
            >
              <Icon path={xMark} class="h-4 w-4" aria-hidden="true" />
            </button>
          </span>
        )}
      </For>
      {/* aria-disabled, not disabled, so a keyboard user keeps their place */}
      <select
        aria-label={`Add a committee to ${props.name}`}
        value=""
        aria-disabled={props.busy ? "true" : "false"}
        onChange={e => {
          if (!props.busy) save([...slugs(), e.currentTarget.value]);
          e.currentTarget.value = "";
        }}
        class={`${input} !w-auto aria-disabled:opacity-40`}
      >
        <option value="">+ Add</option>
        <For each={props.committees.filter(c => !slugs().includes(c.slug))}>
          {c => <option value={c.slug}>{c.name}</option>}
        </For>
      </select>
    </div>
  );
};

const Category = props => {
  const queryClient = useQueryClient();
  const [error, setError] = createSignal("");
  const update = createMutation({
    mutationFn: updateTicketCategory,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      return queryClient.invalidateQueries({ queryKey: ["ticket-categories"] });
    }
  });
  const arrow = (step, label, icon, disabled) => (
    <button
      type="button"
      id={`move-${props.category.key}-${step}`}
      aria-label={`Move ${props.category.name} ${label}`}
      disabled={disabled || props.moving}
      onClick={() => props.move(step)}
      class={iconButton}
    >
      <Icon path={icon} class="h-4 w-4" aria-hidden="true" />
    </button>
  );

  return (
    <li class={`${card} !p-3`}>
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div class="flex gap-1">
          {arrow(-1, "up", arrowUp, props.first)}
          {arrow(1, "down", arrowDown, props.last)}
        </div>
        <NameInput
          category={props.category}
          update={update}
          error={error()}
          setError={setError}
        />
        <div class="min-w-0 flex-1">
          <Committees
            name={props.category.name}
            route={props.route}
            committees={props.committees}
            save={props.save}
            busy={props.busy}
          />
        </div>
        <button
          type="button"
          class={secondaryButton}
          onClick={() => {
            setError("");
            update.mutate(
              { key: props.category.key, is_retired: true },
              { onError: e => setError(e.message) }
            );
          }}
        >
          Retire
          <span class="sr-only"> {props.category.name}</span>
        </button>
      </div>
    </li>
  );
};

const AddCategory = props => {
  const [name, setName] = createSignal("");
  const [error, setError] = createSignal("");
  const submit = e => {
    e.preventDefault();
    setError("");
    props.add.mutate(name().trim(), {
      onSuccess: () => setName(""),
      onError: e => setError(e.message)
    });
  };

  return (
    <form onSubmit={submit} class={`${card} mb-6 flex items-start gap-2`}>
      <Field
        class="min-w-0 flex-1"
        id="new-category"
        label="Add category"
        error={error()}
      >
        <input
          id="new-category"
          type="text"
          value={name()}
          maxLength={100}
          onInput={e => setName(e.currentTarget.value)}
          class={input}
        />
      </Field>
      <button type="submit" class={`${primaryButton} mt-6`}>
        Add
      </button>
    </form>
  );
};

// Staff only: add, rename, reorder and retire help categories, and set where
// each one's new tickets go.
const ManageCategories = () => {
  const queryClient = useQueryClient();
  const [saved, flash] = createSaved();
  const [error, setError] = createSignal("");
  const categories = createQuery(
    () => ["ticket-categories", "all"],
    () => fetchTicketCategories({ all: true })
  );
  const routes = createQuery(() => ["ticket-routes"], fetchTicketRoutes);
  const committees = createQuery(() => ["committees"], fetchCommittees);
  const refresh = key => queryClient.invalidateQueries({ queryKey: [key] });
  const add = createMutation({
    mutationFn: addTicketCategory,
    onSuccess: () => {
      flash();
      return refresh("ticket-categories");
    }
  });
  const restore = createMutation({
    mutationFn: updateTicketCategory,
    onSuccess: flash,
    onError: e => setError(e.message),
    onSettled: () => refresh("ticket-categories")
  });
  // Every changed row's new position at once: either all of them are saved
  // or the page says so, and the buttons wait until the list is back.
  const reorder = createMutation({
    mutationFn: changes => Promise.all(changes.map(updateTicketCategory)),
    onSuccess: flash,
    onError: () => setError("Couldn't save the new order. Try again."),
    onSettled: () => refresh("ticket-categories")
  });
  const save = createMutation({
    mutationFn: saveTicketRoute,
    onMutate: () => setError(""),
    onSuccess: flash,
    onError: e => setError(e.message),
    onSettled: () => refresh("ticket-routes")
  });

  const active = createMemo(() =>
    (categories.data ?? []).filter(c => !c.is_retired)
  );
  const keys = createMemo(() => active().map(c => c.key));
  const retired = () => categories.data.filter(c => c.is_retired);
  // Only when there's nothing to show: a failed refetch keeps the last data.
  const failed = () =>
    [categories, routes, committees].some(q => q.isError && !q.data);
  const routeOf = category =>
    routes.data.find(r => r.category === category) ?? {
      category,
      committees: []
    };
  // Swap with the neighbour and write the position of every row that
  // changed, so rows sharing an order still end up where the buttons put
  // them. Focus follows the moved row to its new place.
  const move = async (key, step) => {
    const rows = [...active()];
    const at = rows.findIndex(c => c.key === key);
    [rows[at], rows[at + step]] = [rows[at + step], rows[at]];
    setError("");
    await reorder
      .mutateAsync(
        rows.flatMap((c, order) =>
          c.order === order ? [] : [{ key: c.key, order }]
        )
      )
      .catch(() => {});
    // Once the buttons are enabled again
    requestAnimationFrame(() =>
      [step, -step]
        .map(s => document.getElementById(`move-${key}-${s}`))
        .find(b => b && !b.disabled)
        ?.focus()
    );
  };

  return (
    <div class="mx-auto max-w-4xl">
      <h1 class="mb-2 text-4xl font-bold text-blue-700 dark:text-white">
        Help categories
      </h1>
      <p class="mb-4 text-sm text-gray-600 dark:text-gray-400">
        New tickets go to every chair of the committees listed.
      </p>
      <p
        role="status"
        class="mb-2 h-6 text-sm font-medium text-green-700 dark:text-green-400"
      >
        <Show when={saved()}>Saved</Show>
      </p>
      <Show when={error() || failed()}>
        <p role="alert" class="mb-3 text-sm text-red-700 dark:text-red-400">
          {error() ||
            "Couldn't load the categories. Reload the page to try again."}
        </p>
      </Show>
      <AddCategory add={add} />
      <Show when={categories.data && committees.data && routes.data}>
        <ul class="space-y-3">
          <For each={keys()}>
            {key => (
              <Category
                category={active().find(c => c.key === key)}
                route={routeOf(key)}
                committees={committees.data}
                save={save}
                busy={save.isLoading && save.variables?.category === key}
                moving={reorder.isLoading}
                first={keys()[0] === key}
                last={keys()[keys().length - 1] === key}
                move={step => move(key, step)}
              />
            )}
          </For>
        </ul>
        <Show when={retired().length}>
          <details class="mt-6">
            <summary
              class={`min-h-[44px] cursor-pointer py-2 font-medium text-gray-900 dark:text-white ${focusRing}`}
            >
              Retired ({retired().length})
            </summary>
            <ul class="space-y-3">
              <For each={retired()}>
                {category => (
                  <li class={`${card} flex items-center justify-between !p-3`}>
                    <span class="text-gray-900 dark:text-white">
                      {category.name}
                    </span>
                    <button
                      type="button"
                      class={secondaryButton}
                      onClick={() => {
                        setError("");
                        restore.mutate({
                          key: category.key,
                          is_retired: false
                        });
                      }}
                    >
                      Restore
                      <span class="sr-only"> {category.name}</span>
                    </button>
                  </li>
                )}
              </For>
            </ul>
          </details>
        </Show>
      </Show>
    </div>
  );
};

export default ManageCategories;
