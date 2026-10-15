import { createMutation, createQuery } from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import {
  Field,
  focusRing,
  input,
  primaryButton,
  todayInput
} from "../../committees";
import { addCommitteeRole, searchUsers } from "../../queries";

// Pick a person from the Hub's users, then give them a role.
const AddPersonForm = props => {
  const [text, setText] = createSignal("");
  const [person, setPerson] = createSignal(null);
  const [title, setTitle] = createSignal("Member");
  const [chair, setChair] = createSignal(false);
  const [start, setStart] = createSignal(todayInput());

  const users = createQuery({
    queryKey: () => ["users", "search", text()],
    queryFn: () => searchUsers(text()),
    get enabled() {
      return text().trim().length > 2 && !person();
    }
  });
  const add = createMutation({
    mutationFn: addCommitteeRole,
    onSuccess: props.done
  });

  const submit = e => {
    e.preventDefault();
    add.mutate({
      slug: props.slug,
      user_id: person().id,
      title: title(),
      is_chair: chair(),
      start_date: start()
    });
  };

  return (
    <form onSubmit={submit} class="space-y-4">
      <Field id="person-search" label="Person">
        <Show
          when={person()}
          fallback={
            <>
              <input
                id="person-search"
                type="search"
                autocomplete="off"
                placeholder="Search by name"
                value={text()}
                onInput={e => setText(e.currentTarget.value)}
                class={input}
              />
              <p class="mt-1 text-xs text-gray-600 dark:text-gray-300">
                Type at least 3 letters to search.
              </p>
              <ul aria-label="Matching people" class="mt-1 space-y-1">
                <For each={users.data ?? []}>
                  {user => (
                    <li>
                      <button
                        type="button"
                        onClick={() => setPerson(user)}
                        class={`min-h-[44px] w-full rounded-lg px-3 text-left text-sm text-gray-900 hover:bg-gray-200 dark:text-white dark:hover:bg-gray-700 ${focusRing}`}
                      >
                        {user.full_name || user.username}
                      </button>
                    </li>
                  )}
                </For>
              </ul>
            </>
          }
        >
          <div class="flex items-center justify-between gap-2 rounded-lg bg-white px-3 py-1 dark:bg-gray-700">
            <span class="text-sm font-medium text-gray-900 dark:text-white">
              {person().full_name}
            </span>
            <button
              type="button"
              onClick={() => setPerson(null)}
              class={`min-h-[44px] rounded px-2 text-sm text-blue-700 underline dark:text-blue-300 ${focusRing}`}
            >
              Change
            </button>
          </div>
        </Show>
      </Field>
      <Field id="role-title" label="Title">
        <input
          id="role-title"
          required
          maxlength="60"
          value={title()}
          onInput={e => setTitle(e.currentTarget.value)}
          class={input}
        />
      </Field>
      <label class="flex min-h-[44px] items-center gap-2 text-sm text-gray-900 dark:text-white">
        <input
          type="checkbox"
          checked={chair()}
          onChange={e => setChair(e.currentTarget.checked)}
          class="h-5 w-5 rounded border-gray-300 text-blue-700 focus:ring-blue-500"
        />
        Chair (gets new tickets for this committee)
      </label>
      <Field id="role-start" label="Start date">
        <input
          id="role-start"
          type="date"
          required
          value={start()}
          onInput={e => setStart(e.currentTarget.value)}
          class={input}
        />
      </Field>
      <Show when={add.isError}>
        <p role="alert" class="text-sm text-red-700 dark:text-red-400">
          {add.error.message}
        </p>
      </Show>
      <div class="flex justify-end">
        <button
          type="submit"
          class={primaryButton}
          disabled={!person() || add.isLoading}
        >
          Add person
        </button>
      </div>
    </form>
  );
};

export default AddPersonForm;
