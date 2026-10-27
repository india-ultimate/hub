import { A, useParams, useSearchParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { userGroup } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import {
  fetchTeamBySlug,
  fetchTeamSuggestions,
  fetchUser,
  markNotDuplicate,
  mergeTeams,
  previewTeamMerge,
  searchTeams,
  teamSuggestionsQueryKey
} from "../../queries";
import Breadcrumbs from "../Breadcrumbs";

const Logo = props => (
  <Show
    when={props.src}
    fallback={
      <span
        aria-hidden="true"
        class="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-gray-300 bg-white text-sm font-semibold text-gray-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300"
      >
        {props.name?.trim().slice(0, 1).toUpperCase()}
      </span>
    }
  >
    <img
      src={props.src}
      alt=""
      class="h-9 w-9 shrink-0 rounded-full border border-gray-300 object-cover dark:border-gray-600"
    />
  </Show>
);

const joinNames = names =>
  names.length > 1
    ? `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
    : names[0];

const count = (n, word) => `${n} ${word}${Number(n) === 1 ? "" : "s"}`;

const MergeTeams = () => {
  const params = useParams();
  const queryClient = useQueryClient();
  let doneRef;

  const teamQuery = createQuery(
    () => ["teams", params.slug],
    () => fetchTeamBySlug(params.slug)
  );
  const team = () => teamQuery.data;
  const userQuery = createQuery(() => ["me"], fetchUser);

  const [search, setSearch] = createSignal("");
  // The ticked teams themselves, so they stay listed whatever is searched.
  const [picked, setPicked] = createSignal([]);
  const [keeperId, setKeeperId] = createSignal();
  // Until the person picks a logo, it follows the kept team.
  const [logoPick, setLogoPick] = createSignal();
  const [message, setMessage] = createSignal("");
  const [done, setDone] = createSignal();

  // Copies are usually named the same, so start by looking for this name.
  createEffect(() => {
    if (team()?.name && !search()) setSearch(team().name.trim());
  });

  const searchQuery = createQuery(
    () => ["team-merge-search", search()],
    () => searchTeams(search(), { pageIndex: 0 }),
    {
      get enabled() {
        return search().length > 1;
      }
    }
  );
  // Teams the Hub thinks are copies of this one; a link can tick them.
  const [searchParams] = useSearchParams();
  const suggestionsQuery = createQuery(
    () => teamSuggestionsQueryKey(team()?.id),
    () => fetchTeamSuggestions(team().id),
    {
      get enabled() {
        return !!team();
      }
    }
  );
  const suggested = () =>
    (suggestionsQuery.data?.[0]?.copies || []).map(copy => ({
      ...copy,
      image_url: copy.logo
    }));
  const isSuggested = id => suggested().some(copy => copy.id === id);
  let fromLink = false;
  createEffect(() => {
    const wanted = (searchParams.copies || "").split(",").map(Number);
    if (fromLink || !suggestionsQuery.isSuccess || !wanted[0]) return;
    fromLink = true;
    const ticked = suggested().filter(copy => wanted.includes(copy.id));
    if (ticked.length === 0) return;
    setPicked(ticked);
    setMessage("The Hub suggested these teams have a matching name.");
  });

  const pickedIds = () => picked().map(t => t.id);
  const results = () => {
    const seen = new Set(pickedIds());
    const rest = [...suggested(), ...(searchQuery.data?.items || [])].filter(
      t => t.id !== team()?.id && !seen.has(t.id) && seen.add(t.id)
    );
    return [...picked(), ...rest];
  };

  const [dismissed, setDismissed] = createSignal("");
  const dismissMutation = createMutation({
    mutationFn: markNotDuplicate,
    onSuccess: (_, { otherId, label }) => {
      setPicked(teams => teams.filter(t => t.id !== otherId));
      setDismissed(`We won't suggest ${label} again.`);
      queryClient.invalidateQueries({ queryKey: ["team-merge-suggestions"] });
    }
  });

  const teamIds = () => (team() ? [team().id, ...pickedIds()] : []);
  const previewQuery = createQuery(
    () => ["team-merge-preview", teamIds()],
    () => previewTeamMerge(teamIds()),
    {
      get enabled() {
        return picked().length > 0 && !!team();
      }
    }
  );
  const preview = () => (picked().length > 0 ? previewQuery.data : undefined);

  // The server's pick, until the person makes their own.
  createEffect(() => {
    const ids = preview()?.teams.map(t => t.id) || [];
    if (preview() && !ids.includes(keeperId()))
      setKeeperId(preview().keeper_id);
  });

  const columns = () => preview()?.teams || [];
  const stat = (label, index) =>
    preview()?.lines.find(line => line.label === label)?.values[index];
  const usage = index =>
    `${count(stat("Tournaments", index), "tournament")}, ${count(
      stat("Players", index),
      "player"
    )}`;
  const kept = () => columns().find(t => t.id === keeperId());
  const logos = () =>
    new Set(
      columns()
        .map(t => t.logo)
        .filter(Boolean)
    );
  const logoId = () =>
    columns().find(t => t.id === logoPick() && t.logo)?.id ??
    (kept()?.logo ? keeperId() : columns().find(t => t.logo)?.id);
  const gone = () =>
    joinNames(
      columns()
        .map((t, i) => ({ t, i }))
        .filter(({ t }) => t.id !== keeperId())
        .map(({ t, i }) => `${t.label} (${usage(i)})`)
    );
  const notAdmin = () =>
    joinNames(
      columns()
        .filter(t => !preview().admin_of.includes(t.id))
        .map(t => t.label)
    );

  const toggle = result =>
    setPicked(teams =>
      teams.some(t => t.id === result.id)
        ? teams.filter(t => t.id !== result.id)
        : [...teams, result]
    );

  const mutation = createMutation({
    mutationFn: mergeTeams,
    onSuccess: data => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      setDone({ ...data, kept: kept()?.label });
      // The form is gone, so say so where the person's focus now lands.
      doneRef?.focus();
    }
  });

  const submit = event => {
    event.preventDefault();
    mutation.mutate({
      teamIds: teamIds(),
      keeperId: keeperId(),
      logoId: logoId(),
      message: message()
    });
  };

  const blocked = () => preview()?.blockers.length > 0;
  const keeping = column => column.id === keeperId() && !blocked();

  return (
    <div class="mx-auto max-w-4xl">
      <Breadcrumbs
        icon={userGroup}
        pageList={[
          { url: "/teams", name: "Teams" },
          { url: `/team/${params.slug}`, name: team()?.name || "Team" },
          { name: "Merge duplicates" }
        ]}
      />
      <h1 class="mb-4 text-2xl font-bold text-gray-900 dark:text-white">
        Merge duplicate teams
      </h1>

      <div
        id="team-merge-done"
        ref={doneRef}
        tabindex="-1"
        role="status"
        classList={{ hidden: !done() }}
        class="rounded-lg border border-green-300 bg-green-50 p-4 text-green-900 focus:outline-none dark:border-green-700 dark:bg-green-900 dark:text-green-100"
      >
        <Show when={done()}>
          <Show
            when={done().merged}
            fallback={
              <>
                <p class="font-semibold">Request sent</p>
                <p class="mt-1 text-sm">
                  Our staff will compare the teams and merge them if they match.
                  We&apos;ll email you at {userQuery.data?.email} once
                  they&apos;ve decided.
                </p>
                <A
                  href={`/team/${params.slug}`}
                  class="mt-2 inline-flex min-h-[44px] items-center text-sm font-medium text-blue-700 underline dark:text-blue-300"
                >
                  Back to {team()?.name?.trim() || "the team"}
                </A>
              </>
            }
          >
            <p class="font-semibold">Merged into {done().kept}</p>
            <A
              href={`/team/${done().slug}`}
              class="mt-2 inline-flex min-h-[44px] items-center text-sm font-medium text-blue-700 underline dark:text-blue-300"
            >
              Go to the team
            </A>
          </Show>
        </Show>
      </div>

      <Show when={!done()}>
        <div class="mb-6 rounded-lg border border-blue-300 bg-blue-50 p-3 text-sm text-blue-900 dark:border-blue-700 dark:bg-blue-900 dark:text-blue-100">
          <p class="font-semibold">
            Made the same team twice? Merge the copies into one.
          </p>
          <ul class="mt-2 list-disc space-y-1 pl-5">
            <li>
              Tournaments, rosters, matches, series, players and admins move to
              the team you keep.
            </li>
            <li>The other teams are then deleted. This cannot be undone.</li>
            <li>
              If you aren&apos;t an admin of every team, our staff check first.
            </li>
          </ul>
        </div>

        <section class="mb-6" aria-labelledby="team-merge-find">
          <h2
            id="team-merge-find"
            class="mb-2 text-lg font-semibold text-gray-900 dark:text-white"
          >
            1. Find the copies of {team()?.name?.trim()}
          </h2>
          <label class="block text-sm text-gray-900 dark:text-white">
            Team name
            <input
              id="team-merge-search"
              type="search"
              class="mt-1 block min-h-[44px] w-full rounded border border-gray-500 p-2 focus:border-blue-600 focus:ring-blue-600 dark:border-gray-400 dark:bg-gray-700 dark:text-white"
              value={search()}
              onInput={e => setSearch(e.currentTarget.value)}
            />
          </label>
          <fieldset class="mt-3">
            <legend class="sr-only">Copies of this team</legend>
            <Show
              when={results().length > 0}
              fallback={
                <p class="text-sm text-gray-500 dark:text-gray-400">
                  <Show
                    when={!searchQuery.isError}
                    fallback="Couldn't search the teams. Please try again."
                  >
                    <Show
                      when={searchQuery.isFetching}
                      fallback="No other teams by that name."
                    >
                      Searching…
                    </Show>
                  </Show>
                </p>
              }
            >
              <ul class="divide-y divide-gray-200 rounded-lg border border-gray-200 dark:divide-gray-700 dark:border-gray-700">
                <For each={results()}>
                  {result => (
                    <li>
                      <label class="flex min-h-[56px] cursor-pointer items-center gap-3 px-3 py-2 focus-within:bg-gray-50 hover:bg-gray-50 dark:focus-within:bg-gray-800 dark:hover:bg-gray-800">
                        <input
                          type="checkbox"
                          class="h-5 w-5 rounded border-gray-500 text-blue-600 focus:ring-2 focus:ring-blue-500 dark:border-gray-400"
                          checked={pickedIds().includes(result.id)}
                          onChange={() => toggle(result)}
                        />
                        <Logo
                          src={result.image || result.image_url}
                          name={result.name}
                        />
                        <span class="min-w-0">
                          <span class="block truncate font-medium text-gray-900 dark:text-white">
                            {result.name}{" "}
                            <span class="font-normal text-gray-500 dark:text-gray-400">
                              #{result.id}
                            </span>
                          </span>
                          <span class="block truncate text-sm text-gray-500 dark:text-gray-400">
                            {[result.category, result.city]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </span>
                      </label>
                      <Show when={isSuggested(result.id)}>
                        <div class="flex items-center justify-between gap-2 px-3 pb-2 pl-11 text-sm">
                          <span class="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-900 dark:bg-yellow-900 dark:text-yellow-100">
                            Matching name
                          </span>
                          <button
                            type="button"
                            class="min-h-[44px] rounded px-2 font-medium text-gray-700 underline hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:text-gray-300 dark:hover:text-white"
                            disabled={dismissMutation.isLoading}
                            onClick={() =>
                              dismissMutation.mutate({
                                teamId: team().id,
                                otherId: result.id,
                                label: `${result.name.trim()} #${result.id}`
                              })
                            }
                          >
                            Not a copy
                            <span class="sr-only">
                              : {result.name} #{result.id}
                            </span>
                          </button>
                        </div>
                      </Show>
                    </li>
                  )}
                </For>
              </ul>
            </Show>
          </fieldset>
          <p
            role="status"
            class="mt-2 text-sm text-gray-600 dark:text-gray-300"
          >
            {dismissed()}
          </p>
        </section>

        <Show when={picked().length > 0 && !preview()}>
          <p
            role="status"
            class="mb-4 text-sm text-gray-600 dark:text-gray-300"
          >
            <Show when={previewQuery.isError} fallback="Comparing the teams…">
              <span class="text-red-700 dark:text-red-400">
                Couldn&apos;t compare these teams: {previewQuery.error?.message}
              </span>
            </Show>
          </p>
        </Show>

        <Show when={preview()}>
          <section aria-labelledby="team-merge-keep">
            <h2
              id="team-merge-keep"
              class="mb-2 text-lg font-semibold text-gray-900 dark:text-white"
            >
              <Show when={!blocked()} fallback="These teams can't be merged">
                2. Choose the team to keep
              </Show>
            </h2>

            <Show
              when={!blocked()}
              fallback={
                <div
                  id="team-merge-blocked"
                  role="alert"
                  class="mb-4 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900 dark:border-red-700 dark:bg-red-900 dark:text-red-100"
                >
                  <p>
                    Teams that entered the same event or series are treated as
                    separate teams.
                  </p>
                  <ul class="mt-2 list-disc space-y-1 pl-5">
                    <For each={preview().blockers}>
                      {line => <li>{line}</li>}
                    </For>
                  </ul>
                  <p class="mt-2 font-medium">
                    Untick any team that isn&apos;t a copy of this one.
                  </p>
                </div>
              }
            >
              <p
                id="team-merge-who"
                class="mb-3 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100"
              >
                <Show
                  when={preview().can_merge}
                  fallback={
                    <>
                      You aren&apos;t an admin of {notAdmin()}, so our staff
                      check this first. Nothing changes until they do.
                    </>
                  }
                >
                  You&apos;re an admin of all these teams, so this merges them
                  straight away.
                </Show>
              </p>
            </Show>

            <form onSubmit={submit}>
              <Show when={!blocked()}>
                <fieldset class="mb-4">
                  <legend class="mb-1 text-sm font-medium text-gray-900 dark:text-white">
                    Team to keep{" "}
                    <span class="font-normal text-gray-500 dark:text-gray-400">
                      (picked for you: the one in the most tournaments)
                    </span>
                  </legend>
                  <div class="space-y-2">
                    <For each={columns()}>
                      {(column, i) => (
                        <label
                          classList={{
                            "border-blue-600 bg-blue-50 dark:border-blue-400 dark:bg-blue-950":
                              keeping(column),
                            "border-gray-200 dark:border-gray-700":
                              !keeping(column)
                          }}
                          class="flex min-h-[56px] cursor-pointer items-center gap-3 rounded-lg border-2 px-3 py-2 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-blue-600"
                        >
                          <input
                            type="radio"
                            name="keeper"
                            class="h-5 w-5 border-gray-500 text-blue-600 dark:border-gray-400"
                            value={column.id}
                            checked={column.id === keeperId()}
                            onChange={() => setKeeperId(column.id)}
                          />
                          <Logo src={column.logo} name={column.name} />
                          <span class="min-w-0 text-sm">
                            <span class="block font-semibold text-gray-900 [overflow-wrap:anywhere] dark:text-white">
                              {column.label}
                            </span>
                            <span class="block text-gray-500 dark:text-gray-400">
                              {[usage(i()), stat("City", i())]
                                .filter(Boolean)
                                .join(" · ")}
                            </span>
                          </span>
                          <Show when={keeping(column)}>
                            <span class="ml-auto shrink-0 rounded-full bg-blue-700 px-2 py-0.5 text-xs font-semibold text-white">
                              Keeping
                            </span>
                          </Show>
                        </label>
                      )}
                    </For>
                  </div>
                </fieldset>
                <Show when={logos().size > 1}>
                  <fieldset class="mb-4">
                    <legend class="mb-1 text-sm font-medium text-gray-900 dark:text-white">
                      Logo to keep
                    </legend>
                    <div class="flex flex-wrap gap-2">
                      <For each={columns().filter(t => t.logo)}>
                        {column => (
                          <label
                            classList={{
                              "border-blue-600 bg-blue-50 dark:border-blue-400 dark:bg-blue-950":
                                column.id === logoId(),
                              "border-gray-200 dark:border-gray-700":
                                column.id !== logoId()
                            }}
                            class="flex min-h-[56px] cursor-pointer items-center gap-3 rounded-lg border-2 px-3 py-2 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-blue-600"
                          >
                            <input
                              type="radio"
                              name="logo"
                              class="h-5 w-5 border-gray-500 text-blue-600 dark:border-gray-400"
                              value={column.id}
                              checked={column.id === logoId()}
                              onChange={() => setLogoPick(column.id)}
                            />
                            <Logo src={column.logo} name={column.name} />
                            <span class="text-sm font-semibold text-gray-900 [overflow-wrap:anywhere] dark:text-white">
                              <span class="sr-only">Logo of </span>
                              {column.label}
                            </span>
                          </label>
                        )}
                      </For>
                    </div>
                  </fieldset>
                </Show>
              </Show>

              <h3 class="mb-1 text-sm font-medium text-gray-900 dark:text-white">
                How they compare{" "}
                <span class="font-normal text-gray-500 dark:text-gray-400">
                  (<span class="text-red-700 dark:text-red-400">≠</span> marks
                  details they disagree on)
                </span>
              </h3>
              <div class="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
                <table class="w-full border-collapse text-left text-sm text-gray-900 dark:text-gray-100">
                  <thead>
                    <tr>
                      <th
                        scope="col"
                        class="sticky left-0 z-10 bg-white dark:bg-gray-900"
                      >
                        <span class="sr-only">Detail</span>
                      </th>
                      <For each={columns()}>
                        {column => (
                          <th
                            scope="col"
                            classList={{
                              "bg-blue-50 dark:bg-blue-950": keeping(column),
                              "bg-gray-50 dark:bg-gray-800": !keeping(column)
                            }}
                            class="min-w-[9rem] px-3 py-2 align-top font-normal"
                          >
                            <span class="flex items-center gap-2">
                              <span>
                                <span class="block font-semibold [overflow-wrap:break-word]">
                                  {column.name}
                                </span>
                                <span class="block text-gray-500 dark:text-gray-400">
                                  #{column.id}
                                  <Show when={keeping(column)}> · Keeping</Show>
                                </span>
                              </span>
                            </span>
                          </th>
                        )}
                      </For>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
                    <For each={preview().lines}>
                      {line => (
                        <tr>
                          <th
                            scope="row"
                            class="sticky left-0 z-10 whitespace-nowrap bg-white px-3 py-2 font-normal text-gray-600 dark:bg-gray-900 dark:text-gray-300"
                          >
                            {line.label}
                            <Show when={line.differs}>
                              <span
                                aria-hidden="true"
                                class="ml-1 font-semibold text-red-700 dark:text-red-400"
                              >
                                ≠
                              </span>
                              <span class="sr-only"> (they differ)</span>
                            </Show>
                          </th>
                          <For each={line.values}>
                            {(value, i) => (
                              <td
                                classList={{
                                  "bg-blue-50 dark:bg-blue-950": keeping(
                                    columns()[i()] || {}
                                  )
                                }}
                                class="px-3 py-2"
                              >
                                {value || "—"}
                              </td>
                            )}
                          </For>
                        </tr>
                      )}
                    </For>
                  </tbody>
                </table>
              </div>

              <Show when={!blocked()}>
                <Show when={preview().pending && !preview().can_merge}>
                  <p
                    role="status"
                    class="mt-4 rounded-lg border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-900 dark:border-yellow-700 dark:bg-yellow-900 dark:text-yellow-100"
                  >
                    A merge request for these teams is already waiting for our
                    staff.
                  </p>
                </Show>

                <div class="mt-4 max-w-2xl space-y-3 text-sm text-gray-900 dark:text-gray-100">
                  <p>
                    <strong class="text-red-700 dark:text-red-400">
                      <Show when={!preview().can_merge}>
                        If our staff approve,{" "}
                      </Show>
                      {gone()} will be deleted. This cannot be undone.
                    </strong>{" "}
                    Everything they hold moves to {kept()?.label}, which keeps
                    its own name
                    <Show when={logos().size > 1}>
                      {" "}
                      and takes the logo picked above
                    </Show>
                    . Its blank <Show when={logos().size <= 1}>logo, </Show>
                    city, state and Ultimate Central ID are filled in from the
                    others, oldest first. Links to the deleted teams&apos; pages
                    stop working.
                  </p>

                  <Show when={!preview().can_merge}>
                    <label class="block">
                      <span class="font-medium">
                        Why are these the same team?
                      </span>
                      <span class="block text-gray-500 dark:text-gray-400">
                        This helps our staff check quickly.
                      </span>
                      <textarea
                        id="team-merge-message"
                        required
                        rows="3"
                        class="mt-1 block w-full rounded border border-gray-500 p-2 focus:border-blue-600 focus:ring-blue-600 dark:border-gray-400 dark:bg-gray-700 dark:text-white"
                        value={message()}
                        onInput={e => setMessage(e.currentTarget.value)}
                      />
                    </label>
                  </Show>

                  <Show when={!preview().can_merge}>
                    <p class="font-medium">
                      Nothing changes until our staff approve.
                    </p>
                  </Show>
                  <button
                    id="team-merge-submit"
                    type="submit"
                    disabled={
                      mutation.isLoading ||
                      (preview().pending && !preview().can_merge)
                    }
                    classList={{
                      "bg-red-700 hover:bg-red-800 focus:ring-red-300":
                        preview().can_merge,
                      "bg-blue-700 hover:bg-blue-800 focus:ring-blue-300":
                        !preview().can_merge
                    }}
                    class="min-h-[44px] rounded-lg px-5 py-2.5 text-sm font-medium text-white focus:outline-none focus:ring-4 disabled:opacity-50"
                  >
                    <Show
                      when={preview().can_merge}
                      fallback="Send to our staff"
                    >
                      Merge into {kept()?.label}
                    </Show>
                  </button>
                  <Show when={mutation.isError}>
                    <p role="alert" class="text-red-700 dark:text-red-400">
                      {mutation.error.message}
                    </p>
                  </Show>
                </div>
              </Show>
            </form>
          </section>
        </Show>
      </Show>
    </div>
  );
};

export default MergeTeams;
