import { A, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import {
  chatBubbleOvalLeftEllipsis,
  lockClosed
} from "solid-heroicons/outline";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";
import { createStore, reconcile } from "solid-js/store";

import {
  addTicketMessage,
  deleteTicketMessage,
  fetchTicketDetail,
  fetchUser,
  updateTicket
} from "../../queries";
import {
  CategoryChip,
  formatDate,
  formatDateTime,
  fullName,
  PriorityBadge,
  StatusBadge,
  STATUSES
} from "../../tickets";
import { MAX_CLOUDINARY_PIXELS, uploadError } from "../../uploads";
import ErrorAlert from "../alerts/Error";
import Breadcrumbs from "../Breadcrumbs";
import FileInput from "../FileInput";
import Modal from "../Modal";
import Assignees from "./Assignees";
import Description from "./Description";
import Message from "./Message";
import UpvoteButton from "./UpvoteButton";

const card =
  "rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 sm:p-6";
const primary =
  "inline-flex min-h-[44px] items-center justify-center rounded-lg bg-blue-700 px-5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus-visible:ring-blue-800";
const TicketDetail = () => {
  const params = useParams();
  const queryClient = useQueryClient();
  const [reply, setReply] = createSignal("");
  const [attachment, setAttachment] = createSignal(null);
  const [attachmentError, setAttachmentError] = createSignal("");
  // Attachments go to Cloudinary as they are, so its own photo limit applies.
  let latestPick;
  const chooseAttachment = async file => {
    latestPick = file;
    const error = await uploadError(file, MAX_CLOUDINARY_PIXELS);
    if (file !== latestPick) return; // a newer pick has taken over
    setAttachmentError(error);
    setAttachment(error ? null : file);
  };
  const [replyError, setReplyError] = createSignal("");
  const [updateError, setUpdateError] = createSignal("");

  const userQuery = createQuery(() => ["me"], fetchUser);
  const ticketQuery = createQuery(
    () => ["ticket", params.id],
    () => fetchTicketDetail(params.id)
  );

  const me = () => userQuery.data;
  const ticket = () => ticketQuery.data;
  const isStaff = () => Boolean(me()?.is_staff);
  const isCreator = () => me() && me().id === ticket()?.created_by.id;
  const canManage = () => isStaff() || ticket()?.can_handle || isCreator();

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries(["ticket", params.id]),
      queryClient.invalidateQueries(["tickets"])
    ]);

  const replyMutation = createMutation({
    mutationFn: data => addTicketMessage(params.id, data),
    onSuccess: () => {
      setReply("");
      setAttachment(null);
      setReplyError("");
      refresh();
    },
    onError: error =>
      setReplyError(
        error.message || "Couldn't send your reply. Please try again."
      )
  });

  const updateMutation = createMutation({
    mutationFn: data => updateTicket(params.id, data),
    onMutate: () => setUpdateError(""),
    onSuccess: refresh,
    onError: error =>
      setUpdateError(error.message || "Couldn't update the ticket.")
  });

  const send = e => {
    e.preventDefault();
    if (!reply().trim() || replyMutation.isLoading) return;
    replyMutation.mutate({ message: reply(), attachment: attachment() });
  };

  // Kept in place by id, so a refetch doesn't draw a reply again and close
  // its open edit.
  const [messages, setMessages] = createStore([]);
  createEffect(() =>
    setMessages(reconcile(ticket()?.messages || [], { key: "id" }))
  );
  const replyCount = () => messages.filter(m => !m.is_deleted).length;

  let deleteDialog;
  const [deleting, setDeleting] = createSignal(null);
  const deleteMutation = createMutation({
    mutationFn: id => deleteTicketMessage(params.id, id),
    onSuccess: async () => {
      await refresh();
      deleteDialog.close();
      // Its Delete button is gone: land back in the conversation instead.
      document.getElementById("conversation-heading")?.focus();
    }
  });
  const askDelete = message => {
    deleteMutation.reset();
    setDeleting(message);
    deleteDialog.showModal();
  };

  return (
    <div class="mx-auto max-w-6xl space-y-4">
      <Breadcrumbs
        icon={chatBubbleOvalLeftEllipsis}
        pageList={[
          { name: "Help", url: "/tickets" },
          { name: `Ticket #${params.id}`, url: "" }
        ]}
      />

      <Show when={!userQuery.isLoading && !me()}>
        <div class="rounded-xl border border-yellow-300 bg-yellow-50 p-6 text-yellow-900">
          <h2 class="text-lg font-semibold">Log in to see this ticket</h2>
          <A href="/login" class={clsx(primary, "mt-4")}>
            Log in
          </A>
        </div>
      </Show>

      <Show when={me()}>
        <Switch>
          <Match when={ticketQuery.isLoading}>
            <div class={clsx(card, "flex gap-4")} aria-hidden="true">
              <div class="h-16 w-16 animate-pulse rounded-lg bg-gray-200 motion-reduce:animate-none dark:bg-gray-700" />
              <div class="flex-1 space-y-3">
                <div class="h-6 w-2/3 animate-pulse rounded bg-gray-200 motion-reduce:animate-none dark:bg-gray-700" />
                <div class="h-4 w-1/3 animate-pulse rounded bg-gray-200 motion-reduce:animate-none dark:bg-gray-700" />
              </div>
            </div>
          </Match>
          <Match when={ticketQuery.isError}>
            <div class={clsx(card, "text-center")}>
              <p class="font-semibold text-gray-900 dark:text-white">
                This ticket doesn't exist, or you can't see it.
              </p>
              <A href="/tickets" class={clsx(primary, "mt-4")}>
                Back to the Help Center
              </A>
            </div>
          </Match>
          <Match when={ticket()}>
            <header id="ticket-header" class={clsx(card, "flex gap-4")}>
              <UpvoteButton ticket={ticket()} userId={me().id} size="lg" />
              <div class="min-w-0 flex-1">
                <h1 class="break-words text-2xl font-bold text-gray-900 dark:text-white">
                  {ticket().title}
                </h1>
                <div class="mt-2 flex flex-wrap items-center gap-2">
                  <StatusBadge status={ticket().status} />
                  <PriorityBadge priority={ticket().priority} />
                  <CategoryChip category={ticket().category_name} />
                  <Show when={ticket().is_private}>
                    <span
                      id="private-badge"
                      class="inline-flex items-center gap-1 rounded-full bg-gray-800 px-2.5 py-0.5 text-xs font-medium text-white dark:bg-gray-200 dark:text-gray-900"
                    >
                      <Icon
                        path={lockClosed}
                        class="h-3.5 w-3.5"
                        aria-hidden="true"
                      />
                      Private
                    </span>
                  </Show>
                </div>
                <p class="mt-3 text-sm text-gray-600 dark:text-gray-400">
                  {fullName(ticket().created_by)} opened this on{" "}
                  {formatDate(ticket().created_at)}
                  <Show when={isStaff()}>
                    {" "}
                    (
                    <a
                      href={`mailto:${ticket().created_by.username}`}
                      class="break-all text-blue-700 underline dark:text-blue-300"
                    >
                      {ticket().created_by.username}
                    </a>
                    )
                  </Show>
                </p>
              </div>
            </header>

            <div class="grid gap-4 lg:grid-cols-3">
              <aside class="space-y-4 lg:order-2">
                <section class={card} aria-labelledby="details-heading">
                  <h2
                    id="details-heading"
                    class="text-sm font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400"
                  >
                    Details
                  </h2>
                  <dl class="mt-3 space-y-2 text-sm">
                    <div class="flex justify-between gap-4">
                      <dt class="text-gray-600 dark:text-gray-400">Opened</dt>
                      <dd class="text-right text-gray-900 dark:text-white">
                        {formatDateTime(ticket().created_at)}
                      </dd>
                    </div>
                    <div class="flex justify-between gap-4">
                      <dt class="text-gray-600 dark:text-gray-400">
                        Last updated
                      </dt>
                      <dd class="text-right text-gray-900 dark:text-white">
                        {formatDateTime(ticket().updated_at)}
                      </dd>
                    </div>
                  </dl>
                  <div class="mt-4 border-t border-gray-200 pt-4 dark:border-gray-700">
                    <Assignees
                      ticket={ticket()}
                      ticketId={params.id}
                      me={me()}
                      isStaff={isStaff()}
                    />
                  </div>

                  <Show when={canManage()}>
                    <div class="mt-4 space-y-4 border-t border-gray-200 pt-4 dark:border-gray-700">
                      <div>
                        <label
                          for="ticket-status"
                          class="mb-1 block text-sm font-medium text-gray-900 dark:text-white"
                        >
                          Status
                        </label>
                        <select
                          id="ticket-status"
                          value={ticket().status}
                          disabled={updateMutation.isLoading}
                          onChange={e =>
                            updateMutation.mutate({
                              status: e.currentTarget.value
                            })
                          }
                          class="min-h-[44px] w-full rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        >
                          <For each={Object.entries(STATUSES)}>
                            {([value, status]) => (
                              <option value={value}>{status.label}</option>
                            )}
                          </For>
                        </select>
                      </div>
                    </div>
                  </Show>
                  <Show when={isStaff() || isCreator()}>
                    <div class="mt-4 space-y-4 border-t border-gray-200 pt-4 dark:border-gray-700">
                      <div class="flex items-start justify-between gap-4">
                        <div>
                          <p
                            id="privacy-label"
                            class="flex items-center gap-1.5 text-sm font-medium text-gray-900 dark:text-white"
                          >
                            <Icon
                              path={lockClosed}
                              class="h-4 w-4"
                              aria-hidden="true"
                            />
                            Private
                          </p>
                          <p
                            id="privacy-help"
                            class="mt-1 text-xs text-gray-600 dark:text-gray-400"
                          >
                            Only the person who opened it and the India Ultimate
                            team can see this ticket.
                          </p>
                        </div>
                        <button
                          type="button"
                          id="privacy-switch"
                          role="switch"
                          aria-checked={ticket().is_private}
                          aria-labelledby="privacy-label"
                          aria-describedby="privacy-help"
                          disabled={updateMutation.isLoading}
                          onClick={() =>
                            updateMutation.mutate({
                              is_private: !ticket().is_private
                            })
                          }
                          class="inline-flex h-11 w-14 shrink-0 items-center justify-center rounded-full focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 disabled:opacity-60 dark:focus-visible:ring-blue-800"
                        >
                          <span
                            aria-hidden="true"
                            class={clsx(
                              "inline-flex h-7 w-12 items-center rounded-full transition-colors duration-150 motion-reduce:transition-none",
                              ticket().is_private
                                ? "bg-blue-700 dark:bg-blue-600"
                                : "bg-gray-300 dark:bg-gray-600"
                            )}
                          >
                            <span
                              class={clsx(
                                "inline-block h-5 w-5 rounded-full bg-white shadow transition-transform duration-150 motion-reduce:transition-none",
                                ticket().is_private
                                  ? "translate-x-6"
                                  : "translate-x-1"
                              )}
                            />
                          </span>
                        </button>
                      </div>
                    </div>
                  </Show>
                  <Show when={updateError()}>
                    <div class="mt-4">
                      <ErrorAlert text={updateError()} />
                    </div>
                  </Show>
                </section>
              </aside>

              <div class="space-y-4 lg:order-1 lg:col-span-2">
                <Description class={card} ticket={ticket()} onSaved={refresh} />

                <section class={card} aria-labelledby="conversation-heading">
                  <h2
                    id="conversation-heading"
                    tabIndex={-1}
                    class="text-base font-semibold text-gray-900 focus:outline-none dark:text-white"
                  >
                    Conversation ({replyCount()})
                  </h2>
                  <Show when={messages.length === 0}>
                    <p class="mt-3 text-sm text-gray-600 dark:text-gray-400">
                      No replies yet.
                    </p>
                  </Show>
                  <ol class="mt-4 space-y-4">
                    <For each={messages}>
                      {message => (
                        <Message
                          message={message}
                          me={me()}
                          isStaff={isStaff()}
                          ticketId={params.id}
                          onChanged={refresh}
                          onDelete={askDelete}
                        />
                      )}
                    </For>
                  </ol>

                  <form
                    onSubmit={send}
                    class="mt-6 border-t border-gray-200 pt-4 dark:border-gray-700"
                  >
                    <label
                      for="reply"
                      class="mb-2 block text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Write a reply
                    </label>
                    <textarea
                      id="reply"
                      rows="4"
                      value={reply()}
                      onInput={e => setReply(e.currentTarget.value)}
                      onKeyDown={e => {
                        if (e.key === "Enter" && (e.ctrlKey || e.metaKey))
                          send(e);
                      }}
                      aria-describedby="reply-hint"
                      placeholder="Type your reply…"
                      class="block w-full rounded-lg border border-gray-300 bg-white p-3 text-base text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400"
                    />
                    <p
                      id="reply-hint"
                      class="mt-1 text-xs text-gray-600 dark:text-gray-400"
                    >
                      Press Ctrl + Enter (⌘ + Enter on a Mac) to send.
                    </p>
                    <FileInput
                      class="mt-3 !px-0"
                      name="attachment"
                      label="Attachment (optional)"
                      accept="image/*,application/pdf"
                      value={attachment()}
                      onInput={e => chooseAttachment(e.target.files[0])}
                      error={attachmentError()}
                      subLabel="Images or PDF, up to 10 MB"
                    />
                    <Show when={attachment()}>
                      <div class="mt-2 flex items-center gap-2 text-sm text-gray-900 dark:text-white">
                        <span class="truncate">
                          Selected: {attachment().name}
                        </span>
                        <button
                          type="button"
                          class="min-h-[44px] px-2 text-red-600 underline"
                          onClick={() => setAttachment(null)}
                        >
                          Remove
                        </button>
                      </div>
                    </Show>
                    <Show when={replyError()}>
                      <div class="mt-3">
                        <ErrorAlert text={replyError()} />
                      </div>
                    </Show>
                    <div class="mt-4 flex justify-end">
                      <button
                        type="submit"
                        id="send-reply"
                        class={primary}
                        disabled={replyMutation.isLoading || !reply().trim()}
                      >
                        {replyMutation.isLoading ? "Sending…" : "Send reply"}
                      </button>
                    </div>
                  </form>
                </section>
              </div>
            </div>
          </Match>
        </Switch>
      </Show>

      <Modal
        ref={el => (deleteDialog = el)}
        title={
          <span class="font-semibold text-gray-900 dark:text-white">
            Delete this reply?
          </span>
        }
        close={() => deleteDialog.close()}
      >
        <p class="text-sm">
          It's removed from the ticket for everyone. Anyone already emailed
          keeps their copy.
        </p>
        <Show when={deleteMutation.isError}>
          <p role="alert" class="mt-2 text-sm text-red-700 dark:text-red-400">
            {deleteMutation.error?.message}
          </p>
        </Show>
        <div class="mt-4 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={() => deleteDialog.close()}
            class="inline-flex min-h-[44px] items-center rounded-lg px-4 text-sm font-semibold text-gray-700 hover:bg-gray-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:text-gray-200 dark:hover:bg-gray-700"
          >
            Cancel
          </button>
          <button
            type="button"
            id="confirm-delete-reply"
            disabled={deleteMutation.isLoading}
            onClick={() => deleteMutation.mutate(deleting().id)}
            class="inline-flex min-h-[44px] items-center rounded-lg bg-red-700 px-4 text-sm font-semibold text-white hover:bg-red-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-600 focus-visible:ring-offset-2 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default TicketDetail;
