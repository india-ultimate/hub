import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { checkBadge } from "solid-heroicons/solid";
import { createSignal, createUniqueId, For, onMount, Show } from "solid-js";

import { getCookie, timeAgo } from "../../utils";
import Modal from "../Modal";

const MAX_LENGTH = 2000;

const request = async (url, options = {}) => {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    }
  });
  if (response.status === 429)
    throw new Error("You're posting too fast. Wait a minute and try again.");
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      data.message || data.detail || "Something went wrong. Try again."
    );
  }
  return response.status === 204 ? null : response.json();
};

const focusRing =
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900";
// A text button, 44px tall on touch.
const action = clsx(
  "inline-flex min-h-[44px] items-center rounded px-2 text-sm font-medium text-gray-600 dark:text-gray-300 [@media(pointer:fine)]:min-h-[32px]",
  focusRing
);
const fullDate = iso =>
  new Date(iso).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short"
  });

// A textarea for a comment or a reply, with its Post/Reply button.
const Composer = props => {
  const queryClient = useQueryClient();
  const [text, setText] = createSignal("");
  let textarea, form;

  const grow = () => {
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  };

  const mutation = createMutation({
    mutationFn: body =>
      request(`/api/announcements/${props.slug}/comments`, {
        method: "POST",
        body: JSON.stringify({ body, parent_id: props.parentId ?? null })
      }),
    onSuccess: async comment => {
      setText("");
      grow();
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["announcement-comments", props.slug]
        }),
        queryClient.invalidateQueries({
          queryKey: ["announcement", props.slug]
        }),
        queryClient.invalidateQueries({ queryKey: ["announcements"] })
      ]);
      props.onPosted?.(comment.id);
    }
  });

  const empty = () => !text().trim();
  const submit = e => {
    e.preventDefault();
    if (!empty() && !mutation.isLoading) mutation.mutate(text().trim());
  };
  const left = () => MAX_LENGTH - text().length;

  onMount(() => props.autofocus && textarea.focus());

  return (
    <form ref={form} onSubmit={submit} class="mt-3">
      <label for={props.id} class="sr-only">
        {props.label}
      </label>
      <textarea
        ref={textarea}
        id={props.id}
        rows={2}
        maxLength={MAX_LENGTH}
        value={text()}
        placeholder={props.label}
        onInput={e => {
          setText(e.currentTarget.value);
          grow();
        }}
        onKeyDown={e => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            form.requestSubmit();
          }
        }}
        class="block max-h-48 w-full resize-none overflow-y-auto rounded-lg border border-gray-300 bg-white p-2.5 text-base text-gray-900 placeholder:text-gray-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder:text-gray-400 sm:text-sm"
      />
      <Show when={mutation.isError}>
        <p role="alert" class="mt-2 text-sm text-red-700 dark:text-red-400">
          {mutation.error?.message}
        </p>
      </Show>
      <div class="mt-2 flex flex-wrap items-center justify-end gap-2">
        <Show when={left() < 200}>
          <span class="mr-auto text-xs text-gray-600 dark:text-gray-400">
            {left()} left
          </span>
        </Show>
        <Show when={props.onCancel}>
          <button
            type="button"
            onClick={() => props.onCancel()}
            class={clsx(
              action,
              "px-3 hover:bg-gray-100 dark:hover:bg-gray-700"
            )}
          >
            Cancel
          </button>
        </Show>
        <button
          type="submit"
          disabled={empty() || mutation.isLoading}
          class={clsx(
            "inline-flex min-h-[44px] items-center rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-blue-600 [@media(pointer:fine)]:min-h-[36px]",
            focusRing
          )}
        >
          {mutation.isLoading ? "Posting…" : props.submitLabel}
        </button>
      </div>
    </form>
  );
};

const Avatar = props => (
  <Show
    when={props.comment.author_profile_pic_url}
    fallback={
      <div
        aria-hidden="true"
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-200 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300"
      >
        {props.comment.author.first_name?.[0]}
        {props.comment.author.last_name?.[0]}
      </div>
    }
  >
    <img
      src={props.comment.author_profile_pic_url}
      alt=""
      class="h-8 w-8 shrink-0 rounded-full object-cover"
      loading="lazy"
    />
  </Show>
);

// One comment: who, when, what, and what you can do with it.
const Row = props => {
  const c = () => props.comment;
  return (
    <div
      class={clsx(
        "-mx-2 flex gap-3 rounded-lg px-2 py-2 motion-safe:transition-colors motion-safe:duration-700",
        props.highlighted && "bg-blue-50 dark:bg-blue-900/30"
      )}
    >
      <Show
        when={!c().is_deleted}
        fallback={
          <div class="h-8 w-8 shrink-0 rounded-full bg-gray-100 dark:bg-gray-700" />
        }
      >
        <Avatar comment={c()} />
      </Show>
      <div class="min-w-0 flex-1">
        <Show
          when={!c().is_deleted}
          fallback={
            <p class="py-1.5 text-sm italic text-gray-500 dark:text-gray-400">
              Comment deleted
            </p>
          }
        >
          <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span class="text-sm font-bold text-gray-900 dark:text-white">
              {c().author.first_name} {c().author.last_name}
            </span>
            <Show when={c().author_is_staff}>
              <span class="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 ring-1 ring-blue-600/20 dark:bg-blue-900/40 dark:text-blue-200 dark:ring-blue-400/30">
                <Icon
                  path={checkBadge}
                  aria-hidden="true"
                  class="h-4 w-4 text-blue-600 dark:text-blue-400"
                />
                India Ultimate
              </span>
            </Show>
            <time
              datetime={c().created_at}
              title={fullDate(c().created_at)}
              class="text-xs text-gray-600 dark:text-gray-400"
            >
              {timeAgo(c().created_at)}
            </time>
          </div>
          <p class="mt-1 whitespace-pre-line break-words text-sm text-gray-800 dark:text-gray-200">
            {c().body}
          </p>
          <div class="-ml-2 flex gap-1">
            <Show when={props.onReply}>
              <button
                type="button"
                onClick={() => props.onReply()}
                class={clsx(
                  action,
                  "hover:text-blue-700 dark:hover:text-blue-300"
                )}
              >
                Reply
              </button>
            </Show>
            <Show when={c().can_delete}>
              <button
                type="button"
                onClick={() => props.onDelete(c())}
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
      </div>
    </div>
  );
};

const Comments = props => {
  const queryClient = useQueryClient();
  const headingId = createUniqueId();
  const [replyingTo, setReplyingTo] = createSignal(null);
  const [highlighted, setHighlighted] = createSignal(null);
  const [deleting, setDeleting] = createSignal(null);
  let deleteDialog;

  const query = createQuery(
    () => ["announcement-comments", props.slug],
    () => request(`/api/announcements/${props.slug}/comments`)
  );

  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["announcement-comments", props.slug]
      }),
      queryClient.invalidateQueries({ queryKey: ["announcement", props.slug] }),
      queryClient.invalidateQueries({ queryKey: ["announcements"] })
    ]);

  const deleteMutation = createMutation({
    mutationFn: id =>
      request(`/api/announcements/comments/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await invalidate();
      deleteDialog.close();
    }
  });

  const posted = id => {
    setReplyingTo(null);
    setHighlighted(id);
    document
      .getElementById(`comment-${id}`)
      ?.scrollIntoView({ block: "nearest" });
    setTimeout(() => setHighlighted(h => (h === id ? null : h)), 1500);
  };

  const askDelete = comment => {
    deleteMutation.reset();
    setDeleting(comment);
    deleteDialog.showModal();
  };

  const comments = () => query.data || [];

  return (
    <section id="comments" aria-labelledby={headingId} class="mt-8">
      <h2
        id={headingId}
        class="text-lg font-semibold text-gray-900 dark:text-white"
      >
        Comments · {props.count ?? 0}
      </h2>

      <Show
        when={!query.isLoading}
        fallback={
          <div aria-hidden="true" class="mt-4 space-y-4">
            <For each={[1, 2]}>
              {() => (
                <div class="flex gap-3">
                  <div class="h-8 w-8 rounded-full bg-gray-200 motion-safe:animate-pulse dark:bg-gray-700" />
                  <div class="flex-1 space-y-2">
                    <div class="h-4 w-1/3 rounded bg-gray-200 motion-safe:animate-pulse dark:bg-gray-700" />
                    <div class="h-4 w-3/4 rounded bg-gray-200 motion-safe:animate-pulse dark:bg-gray-700" />
                  </div>
                </div>
              )}
            </For>
          </div>
        }
      >
        <Show when={query.isError}>
          <p role="alert" class="mt-4 text-sm text-red-700 dark:text-red-400">
            Couldn't load the comments. Try again later.
          </p>
        </Show>
        <Show
          when={!comments().length && props.allowComments && !query.isError}
        >
          <p class="mt-4 text-sm text-gray-600 dark:text-gray-400">
            No comments yet. Ask a question or share your thoughts.
          </p>
        </Show>
        <ul class="mt-4 space-y-2">
          <For each={comments()}>
            {comment => (
              <li id={`comment-${comment.id}`}>
                <Row
                  comment={comment}
                  highlighted={highlighted() === comment.id}
                  onReply={
                    props.allowComments && !comment.is_deleted
                      ? () => setReplyingTo(comment.id)
                      : undefined
                  }
                  onDelete={askDelete}
                />
                <Show
                  when={comment.replies.length || replyingTo() === comment.id}
                >
                  <div class="ml-4 border-l-2 border-gray-200 pl-3 dark:border-gray-700 sm:ml-12 sm:pl-4">
                    <ul class="space-y-2">
                      <For each={comment.replies}>
                        {reply => (
                          <li id={`comment-${reply.id}`}>
                            <Row
                              comment={reply}
                              highlighted={highlighted() === reply.id}
                              onDelete={askDelete}
                            />
                          </li>
                        )}
                      </For>
                    </ul>
                    <Show
                      when={props.allowComments && replyingTo() === comment.id}
                    >
                      <Composer
                        slug={props.slug}
                        parentId={comment.id}
                        id={`reply-${comment.id}`}
                        label={`Reply to ${comment.author.first_name}`}
                        submitLabel="Reply"
                        autofocus
                        onPosted={posted}
                        onCancel={() => setReplyingTo(null)}
                      />
                    </Show>
                  </div>
                </Show>
              </li>
            )}
          </For>
        </ul>
      </Show>

      <Show
        when={props.allowComments}
        fallback={
          <p class="mt-4 rounded-lg bg-gray-50 p-3 text-sm text-gray-600 dark:bg-gray-800 dark:text-gray-400">
            Comments are turned off for this announcement.
          </p>
        }
      >
        <Composer
          slug={props.slug}
          id="new-comment"
          label="Add a comment"
          submitLabel="Post"
          onPosted={posted}
        />
      </Show>

      <Modal
        ref={el => (deleteDialog = el)}
        title={
          <span class="font-semibold text-gray-900 dark:text-white">
            Delete this comment?
          </span>
        }
        close={() => deleteDialog.close()}
      >
        <p class="text-sm">This can't be undone.</p>
        <Show when={deleteMutation.isError}>
          <p role="alert" class="mt-2 text-sm text-red-700 dark:text-red-400">
            {deleteMutation.error?.message}
          </p>
        </Show>
        <div class="mt-4 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={() => deleteDialog.close()}
            class={clsx(
              "inline-flex min-h-[44px] items-center rounded-lg px-4 text-sm font-semibold text-gray-700 hover:bg-gray-200 dark:text-gray-200 dark:hover:bg-gray-700",
              focusRing
            )}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={deleteMutation.isLoading}
            onClick={() => deleteMutation.mutate(deleting().id)}
            class="inline-flex min-h-[44px] items-center rounded-lg bg-red-700 px-4 text-sm font-semibold text-white hover:bg-red-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-600 focus-visible:ring-offset-2 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </Modal>
    </section>
  );
};

export default Comments;
