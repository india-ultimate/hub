import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { createSignal, For, onCleanup, Show, Suspense } from "solid-js";

import {
  addRosterEntry,
  fetchRosterCandidates,
  removeRosterEntry
} from "../../queries";

const HINT_TONE = {
  ready: "text-green-800 dark:text-green-300",
  action: "text-amber-800 dark:text-amber-300",
  waiting: "text-amber-800 dark:text-amber-300",
  blocked: "text-gray-600 dark:text-gray-400",
  limit: "text-gray-600 dark:text-gray-400",
  timing: "text-gray-600 dark:text-gray-400"
};
const btn =
  "inline-flex min-h-[44px] flex-none items-center rounded-lg px-3 text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600";

const initials = name =>
  (name || "?")
    .split(" ")
    .filter(Boolean)
    .map(w => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

// Yourself, your series roster and past teammates first; search finds
// anyone. Adding takes effect at once, with an undo.
const AddPlayersDialog = props => {
  const [text, setText] = createSignal("");
  const [query, setQuery] = createSignal("");
  const [page, setPage] = createSignal(1);
  const [added, setAdded] = createSignal({}); // id -> true
  const [busy, setBusy] = createSignal(null);
  const [errors, setErrors] = createSignal({}); // id -> message
  let dialog;
  let timer;
  onCleanup(() => clearTimeout(timer));

  const results = createQuery(
    () => ["roster-candidates", props.args, query(), page()],
    () => fetchRosterCandidates({ ...props.args, text: query(), page: page() }),
    {
      keepPreviousData: true,
      // Fresh on each open: the roster may have changed since.
      staleTime: 0,
      get enabled() {
        return props.open;
      }
    }
  );
  const count = () =>
    (results.data?.groups || []).reduce((n, g) => n + g.players.length, 0);

  const act = async (player, undo, mine) => {
    setBusy(player.id);
    setErrors(e => ({ ...e, [player.id]: null }));
    try {
      if (undo) await removeRosterEntry({ ...props.args, playerId: player.id });
      else await addRosterEntry({ ...props.args, playerId: player.id });
      setAdded(a => ({ ...a, [player.id]: !undo }));
      props.announce(
        !undo
          ? `Added ${player.name}`
          : mine && props.series
          ? "Removed you from this list — you stay on the series roster"
          : `Removed ${player.name}`
      );
      props.onChanged();
    } catch (e) {
      const message =
        undo && e.status === 409 ? "Already paid, can't undo" : e.message;
      setErrors(x => ({ ...x, [player.id]: message }));
    } finally {
      setBusy(null);
    }
  };

  const Row = rowProps => {
    const p = () => rowProps.player;
    return (
      <li
        data-player-id={p().id}
        class={clsx(
          "flex items-center gap-3 border-t border-gray-100 px-4 py-2 dark:border-gray-700",
          rowProps.class
        )}
      >
        <span
          aria-hidden="true"
          class="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-800 dark:bg-blue-900 dark:text-blue-200"
        >
          {initials(p().name)}
        </span>
        <div class="min-w-0 flex-1">
          <p class="truncate font-medium text-gray-900 dark:text-white">
            {rowProps.title || p().name}
          </p>
          <p class="text-xs text-gray-600 dark:text-gray-400">
            {p().last_event
              ? `Last: ${p().last_event}${
                  p().events > 1 ? ` · ${p().events} events` : ""
                }`
              : p().city}
          </p>
          <Show when={p().hint}>
            <p class={clsx("text-xs", HINT_TONE[p().hint.kind])}>
              {p().hint.text}
            </p>
          </Show>
          <Show when={errors()[p().id]}>
            <p role="alert" class="text-xs text-red-700 dark:text-red-400">
              {errors()[p().id]}
            </p>
          </Show>
        </div>
        <Show
          when={!added()[p().id]}
          fallback={
            <span class="flex flex-none items-center gap-1">
              <span class="rounded-lg bg-green-100 px-2 py-1 text-xs font-semibold text-green-800 dark:bg-green-900 dark:text-green-200">
                ✓ Added
              </span>
              <button
                type="button"
                class={clsx(btn, "text-blue-700 underline dark:text-blue-400")}
                aria-label={`Undo adding ${p().name}`}
                onClick={() =>
                  busy() !== p().id && act(p(), true, rowProps.mine)
                }
              >
                Undo
              </button>
            </span>
          }
        >
          <Show
            when={p().button}
            fallback={
              <span class="flex-none rounded-lg bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                {p().on_list ? "On the list" : "Unavailable"}
              </span>
            }
          >
            <button
              type="button"
              class={clsx(
                btn,
                "border border-blue-700 text-blue-700 hover:bg-blue-50 dark:border-blue-400 dark:text-blue-400 dark:hover:bg-gray-700",
                busy() === p().id && "cursor-not-allowed opacity-[0.45]"
              )}
              aria-disabled={busy() === p().id ? "true" : undefined}
              aria-label={`${p().button === "invite" ? "Invite" : "Add"} ${
                p().name
              }`}
              onClick={() => busy() !== p().id && act(p(), false)}
            >
              {busy() === p().id
                ? "Adding…"
                : p().button === "invite"
                ? "Invite"
                : "Add"}
            </button>
          </Show>
        </Show>
      </li>
    );
  };

  const addedCount = () => Object.values(added()).filter(Boolean).length;

  return (
    <dialog
      ref={el => {
        dialog = el;
        props.setRef(el);
      }}
      aria-label="Add players"
      class="m-0 h-full max-h-none w-full max-w-none p-0 backdrop:bg-gray-900/60 sm:m-auto sm:h-auto sm:max-h-[85vh] sm:max-w-lg sm:rounded-xl"
      onClose={() => {
        clearTimeout(timer);
        setText("");
        setQuery("");
        setPage(1);
        setAdded({});
        setErrors({});
      }}
    >
      <div class="flex h-full flex-col bg-white text-gray-900 dark:bg-gray-800 dark:text-white">
        <div class="flex items-center justify-between px-4 pt-4">
          <h2 class="text-lg font-bold">Add players · {props.teamName}</h2>
          <button
            type="button"
            class="inline-flex h-11 w-11 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-gray-400 dark:hover:bg-gray-700"
            aria-label="Close"
            onClick={() => dialog.close()}
          >
            ✕
          </button>
        </div>
        <Show when={props.meter?.max_total}>
          <p class="px-4 text-xs text-gray-600 dark:text-gray-400">
            {props.meter.total} of {props.meter.max_total} spots
          </p>
        </Show>
        <div class="px-4 py-2">
          <label for="add-players-search" class="sr-only">
            Search anyone by name or email
          </label>
          <input
            id="add-players-search"
            type="search"
            autocomplete="off"
            autofocus
            placeholder="Search anyone by name or email"
            class="block min-h-[44px] w-full rounded-lg border border-gray-300 bg-gray-50 px-3 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400"
            value={text()}
            onInput={e => {
              setText(e.currentTarget.value);
              clearTimeout(timer);
              timer = setTimeout(() => {
                setPage(1);
                setQuery(text().trim());
              }, 250);
            }}
          />
          <p class="sr-only" aria-live="polite">
            <Suspense>
              {results.isSuccess
                ? `${count()} result${count() === 1 ? "" : "s"}`
                : ""}
            </Suspense>
          </p>
        </div>
        <div class="flex-1 overflow-y-auto">
          {/* A first fetch suspends here, never the page around the dialog:
              that would drop the dialog out of the top layer. */}
          <Suspense
            fallback={
              <p class="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                Loading…
              </p>
            }
          >
            <Show when={results.data?.me && query().length < 2}>
              <ul
                aria-label="Add myself"
                class="mx-4 mb-2 overflow-hidden rounded-lg border border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/40"
              >
                <Row
                  player={results.data.me}
                  title="Add myself"
                  mine
                  class="border-t-0"
                />
              </ul>
            </Show>
            <For each={results.data?.groups || []}>
              {group => (
                <Show when={group.players.length}>
                  <h3 class="px-4 pb-1 pt-2 text-xs font-bold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                    {group.title} · {group.players.length}
                  </h3>
                  <ul aria-label={group.title}>
                    <For each={group.players}>{p => <Row player={p} />}</For>
                  </ul>
                </Show>
              )}
            </For>
            <Show
              when={
                results.isSuccess &&
                !count() &&
                !(results.data?.me && query().length < 2)
              }
            >
              <p class="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
                {query().length < 2
                  ? "No past teammates yet — search anyone by name or email."
                  : "No one found. They need a Hub account before you can add them."}
              </p>
            </Show>
            <Show when={results.data?.has_more}>
              <button
                type="button"
                class={clsx(btn, "mx-4 my-2 text-blue-700 dark:text-blue-400")}
                onClick={() => setPage(p => p + 1)}
              >
                Show more
              </button>
            </Show>
          </Suspense>
        </div>
        <div class="flex items-center justify-between border-t border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
          <span class="text-sm text-gray-600 dark:text-gray-400">
            {addedCount()} added
          </span>
          <button
            type="button"
            class={clsx(
              btn,
              "bg-blue-700 text-white hover:bg-blue-800 dark:bg-blue-600 dark:hover:bg-blue-700"
            )}
            onClick={() => dialog.close()}
          >
            Done
          </button>
        </div>
      </div>
    </dialog>
  );
};

export default AddPlayersDialog;
