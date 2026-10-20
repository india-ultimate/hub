import { createMutation } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { pencilSquare } from "solid-heroicons/outline";
import { createSignal, Show } from "solid-js";

import { updateTicket } from "../../queries";
import { formatDateTime } from "../../tickets";
import ErrorAlert from "../alerts/Error";

const TITLE_MAX_LENGTH = 200;
const field =
  "block w-full rounded-lg border border-gray-300 bg-white p-3 text-base text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white sm:text-sm";
const textButton =
  "inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-lg px-4 text-sm font-medium focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50 dark:focus-visible:ring-blue-800";

// The ticket's description, which whoever opened it (and staff) can fix,
// together with its title.
const Description = props => {
  const [editing, setEditing] = createSignal(false);
  const [title, setTitle] = createSignal("");
  const [description, setDescription] = createSignal("");
  let editButton, titleInput;

  const stopEditing = () => {
    setEditing(false);
    queueMicrotask(() => editButton?.focus());
  };

  const mutation = createMutation({
    mutationFn: data => updateTicket(props.ticket.id, data),
    onSuccess: async () => {
      await props.onSaved();
      stopEditing();
    }
  });

  const startEditing = () => {
    mutation.reset();
    setTitle(props.ticket.title);
    setDescription(props.ticket.description);
    setEditing(true);
    queueMicrotask(() => titleInput?.focus());
  };

  const blank = () => !title().trim() || !description().trim();
  const save = e => {
    e.preventDefault();
    if (blank() || mutation.isLoading) return;
    mutation.mutate({ title: title(), description: description() });
  };

  return (
    <section
      class={props.class}
      aria-labelledby="description-heading"
      onKeyDown={e => editing() && e.key === "Escape" && stopEditing()}
    >
      <div class="flex items-center justify-between gap-2">
        <h2
          id="description-heading"
          class="text-base font-semibold text-gray-900 dark:text-white"
        >
          {editing() ? "Edit ticket" : "Description"}
        </h2>
        <Show when={props.ticket.can_edit && !editing()}>
          <button
            ref={editButton}
            type="button"
            id="edit-ticket"
            aria-label="Edit the title and description"
            onClick={startEditing}
            class={`${textButton} -my-2 -mr-2 px-3 text-blue-700 hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-gray-700`}
          >
            <Icon path={pencilSquare} class="h-4 w-4" aria-hidden="true" />
            Edit
          </button>
        </Show>
      </div>
      <Show
        when={editing()}
        fallback={
          <>
            <p class="mt-2 whitespace-pre-wrap break-words text-gray-800 dark:text-gray-200">
              {props.ticket.description}
            </p>
            <Show when={props.ticket.edited_at}>
              <p class="mt-2 text-xs italic text-gray-600 dark:text-gray-400">
                Edited {formatDateTime(props.ticket.edited_at)}
              </p>
            </Show>
          </>
        }
      >
        <form onSubmit={save} class="mt-3 space-y-3">
          <div>
            <label
              for="edit-title"
              class="mb-1 block text-sm font-medium text-gray-900 dark:text-white"
            >
              Title
            </label>
            <input
              ref={titleInput}
              id="edit-title"
              maxLength={TITLE_MAX_LENGTH}
              value={title()}
              onInput={e => setTitle(e.currentTarget.value)}
              class={field}
            />
          </div>
          <div>
            <label
              for="edit-description"
              class="mb-1 block text-sm font-medium text-gray-900 dark:text-white"
            >
              Description
            </label>
            <textarea
              id="edit-description"
              rows="5"
              value={description()}
              onInput={e => setDescription(e.currentTarget.value)}
              onKeyDown={e => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) save(e);
              }}
              class={field}
            />
          </div>
          <Show when={mutation.isError}>
            <ErrorAlert text={mutation.error?.message} />
          </Show>
          <div class="flex justify-end gap-2">
            <button
              type="button"
              onClick={stopEditing}
              class={`${textButton} text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-700`}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={blank() || mutation.isLoading}
              class={`${textButton} bg-blue-700 px-5 text-white hover:bg-blue-800 dark:bg-blue-600 dark:hover:bg-blue-700`}
            >
              {mutation.isLoading ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </Show>
    </section>
  );
};

export default Description;
