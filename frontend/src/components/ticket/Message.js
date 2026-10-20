import { createMutation } from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { arrowDownTray } from "solid-heroicons/outline";
import { createSignal, Show } from "solid-js";

import { editTicketMessage } from "../../queries";
import { formatDateTime, fullName } from "../../tickets";
import ErrorAlert from "../alerts/Error";

const IMAGE = /\.(jpe?g|png|gif|webp|bmp|tiff)$/i;
const focusRing =
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-800";
// A text button, 44px tall on touch.
const action = clsx(
  "inline-flex min-h-[44px] items-center rounded px-2 text-sm font-medium text-gray-600 dark:text-gray-300 [@media(pointer:fine)]:min-h-[32px]",
  focusRing
);

const fileName = url => {
  try {
    return new URL(url).pathname.split("/").pop() || "attachment";
  } catch {
    return "attachment";
  }
};

const download = async url => {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Failed to fetch file");
    const href = window.URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = href;
    link.download = fileName(url);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(href);
  } catch {
    window.open(url, "_blank");
  }
};

// One reply in a ticket's conversation, which its sender can edit in place.
const Message = props => {
  const m = () => props.message;
  const mine = () => m().sender.id === props.me.id;
  const [editing, setEditing] = createSignal(false);
  const [text, setText] = createSignal("");
  let editButton, textarea;

  const stopEditing = () => {
    setEditing(false);
    queueMicrotask(() => editButton?.focus());
  };

  const mutation = createMutation({
    mutationFn: message => editTicketMessage(props.ticketId, m().id, message),
    onSuccess: async () => {
      await props.onChanged();
      stopEditing();
    }
  });

  const startEditing = () => {
    mutation.reset();
    setText(m().message);
    setEditing(true);
    queueMicrotask(() => {
      textarea?.focus();
      textarea?.setSelectionRange(textarea.value.length, textarea.value.length);
    });
  };

  const save = e => {
    e.preventDefault();
    if (text().trim() && !mutation.isLoading) mutation.mutate(text());
  };

  return (
    <li
      id={`message-${m().id}`}
      class={clsx("flex flex-col", mine() ? "items-end" : "items-start")}
    >
      <Show
        when={!m().is_deleted}
        fallback={
          <p class="max-w-[85%] rounded-2xl border border-dashed border-gray-300 px-4 py-2 text-sm italic text-gray-600 dark:border-gray-600 dark:text-gray-400">
            Message deleted
          </p>
        }
      >
        <Show
          when={!editing()}
          fallback={
            <form onSubmit={save} class="w-full max-w-[85%]">
              <label
                for={`edit-message-${m().id}`}
                class="mb-1 block text-sm font-medium text-gray-900 dark:text-white"
              >
                Edit your reply
              </label>
              <textarea
                ref={textarea}
                id={`edit-message-${m().id}`}
                rows="3"
                value={text()}
                onInput={e => setText(e.currentTarget.value)}
                onKeyDown={e => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) save(e);
                  else if (e.key === "Escape") {
                    e.preventDefault();
                    stopEditing();
                  }
                }}
                class="block w-full rounded-lg border border-gray-300 bg-white p-3 text-base text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white sm:text-sm"
              />
              <Show when={mutation.isError}>
                <div class="mt-2">
                  <ErrorAlert text={mutation.error?.message} />
                </div>
              </Show>
              <div class="mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={stopEditing}
                  class={clsx(
                    action,
                    "px-3 hover:bg-gray-100 dark:hover:bg-gray-700"
                  )}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!text().trim() || mutation.isLoading}
                  class={clsx(
                    "inline-flex min-h-[44px] items-center rounded-lg bg-blue-700 px-4 text-sm font-medium text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-blue-600 dark:hover:bg-blue-700 [@media(pointer:fine)]:min-h-[36px]",
                    focusRing
                  )}
                >
                  {mutation.isLoading ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          }
        >
          <div
            class={clsx(
              "max-w-[85%] rounded-2xl px-4 py-3",
              mine()
                ? "rounded-br-sm bg-blue-700 text-white dark:bg-blue-600"
                : "rounded-bl-sm bg-gray-100 text-gray-900 dark:bg-gray-700 dark:text-gray-100"
            )}
          >
            <p
              class={clsx(
                "text-xs",
                mine() ? "text-blue-100" : "text-gray-600 dark:text-gray-300"
              )}
            >
              <span class="font-semibold">
                {mine() ? "You" : fullName(m().sender)}
              </span>{" "}
              ·{" "}
              <time datetime={m().created_at}>
                {formatDateTime(m().created_at)}
              </time>
              <Show when={m().edited_at}>
                {" "}
                ·{" "}
                <span
                  class="italic"
                  title={`Edited ${formatDateTime(m().edited_at)}`}
                >
                  edited
                </span>
              </Show>
              <Show when={props.isStaff && !mine()}>
                {" "}
                (
                <a
                  href={`mailto:${m().sender.username}`}
                  class="break-all underline"
                >
                  {m().sender.username}
                </a>
                )
              </Show>
            </p>
            <p class="mt-1 whitespace-pre-wrap break-words">{m().message}</p>
            <Show when={m().attachment}>
              <div class="mt-2 space-y-2">
                <Show when={IMAGE.test(m().attachment)}>
                  <img
                    src={m().attachment}
                    alt={`Attachment from ${fullName(m().sender)}`}
                    loading="lazy"
                    class="max-h-48 max-w-full rounded-lg object-contain"
                  />
                </Show>
                <button
                  type="button"
                  onClick={() => download(m().attachment)}
                  class={clsx(
                    "inline-flex min-h-[44px] items-center gap-1.5 text-sm font-medium underline",
                    mine() ? "text-white" : "text-blue-700 dark:text-blue-300"
                  )}
                >
                  <Icon
                    path={arrowDownTray}
                    class="h-4 w-4"
                    aria-hidden="true"
                  />
                  Download {fileName(m().attachment)}
                </button>
              </div>
            </Show>
          </div>
          <Show when={m().can_edit || m().can_delete}>
            <div class="mt-1 flex gap-1">
              <Show when={m().can_edit}>
                <button
                  ref={editButton}
                  type="button"
                  aria-label="Edit your reply"
                  onClick={startEditing}
                  class={clsx(
                    action,
                    "hover:text-blue-700 dark:hover:text-blue-300"
                  )}
                >
                  Edit
                </button>
              </Show>
              <Show when={m().can_delete}>
                <button
                  type="button"
                  aria-label={
                    mine()
                      ? "Delete your reply"
                      : `Delete the reply from ${fullName(m().sender)}`
                  }
                  onClick={() => props.onDelete(m())}
                  class={clsx(
                    action,
                    "hover:text-red-700 dark:hover:text-red-400"
                  )}
                >
                  Delete
                </button>
              </Show>
            </div>
          </Show>
        </Show>
      </Show>
    </li>
  );
};

export default Message;
