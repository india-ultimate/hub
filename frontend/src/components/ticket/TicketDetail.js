import { A, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import {
  arrowDownTray,
  chatBubbleOvalLeftEllipsis,
  lockClosed
} from "solid-heroicons/outline";
import { createSignal, For, Match, Show, Switch } from "solid-js";

import {
  addTicketMessage,
  fetchTicketDetail,
  fetchUser,
  updateTicket
} from "../../queries";
import {
  CategoryChip,
  formatDate,
  formatDateTime,
  PriorityBadge,
  StatusBadge,
  STATUSES
} from "../../tickets";
import ErrorAlert from "../alerts/Error";
import Breadcrumbs from "../Breadcrumbs";
import FileInput from "../FileInput";
import UpvoteButton from "./UpvoteButton";

const card =
  "rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 sm:p-6";
const primary =
  "inline-flex min-h-[44px] items-center justify-center rounded-lg bg-blue-700 px-5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus-visible:ring-blue-800";
const secondary =
  "inline-flex min-h-[44px] w-full items-center justify-center rounded-lg border border-gray-300 bg-white px-4 text-sm font-medium text-gray-900 hover:bg-gray-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-gray-200 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700";
const IMAGE = /\.(jpe?g|png|gif|webp|bmp|tiff)$/i;

const fullName = user => `${user.first_name} ${user.last_name}`.trim();

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

const TicketDetail = () => {
  const params = useParams();
  const queryClient = useQueryClient();
  const [reply, setReply] = createSignal("");
  const [attachment, setAttachment] = createSignal(null);
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
  const canManage = () =>
    isStaff() || (me() && me().id === ticket()?.created_by.id);

  const refresh = () => {
    queryClient.invalidateQueries(["ticket", params.id]);
    queryClient.invalidateQueries(["tickets"]);
  };

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
                  <CategoryChip category={ticket().category} />
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
                      <dt class="text-gray-600 dark:text-gray-400">
                        Assigned to
                      </dt>
                      <dd class="text-right font-medium text-gray-900 dark:text-white">
                        {ticket().assigned_to
                          ? fullName(ticket().assigned_to)
                          : "Unassigned"}
                      </dd>
                    </div>
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
                      <Show
                        when={isStaff() && ticket().assigned_to?.id !== me().id}
                      >
                        <button
                          type="button"
                          id="assign-to-me"
                          class={secondary}
                          disabled={updateMutation.isLoading}
                          onClick={() =>
                            updateMutation.mutate({ assigned_to_id: me().id })
                          }
                        >
                          Assign to me
                        </button>
                      </Show>
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
                      <Show when={updateError()}>
                        <ErrorAlert text={updateError()} />
                      </Show>
                    </div>
                  </Show>
                </section>
              </aside>

              <div class="space-y-4 lg:order-1 lg:col-span-2">
                <section class={card} aria-labelledby="description-heading">
                  <h2
                    id="description-heading"
                    class="text-base font-semibold text-gray-900 dark:text-white"
                  >
                    Description
                  </h2>
                  <p class="mt-2 whitespace-pre-wrap break-words text-gray-800 dark:text-gray-200">
                    {ticket().description}
                  </p>
                </section>

                <section class={card} aria-labelledby="conversation-heading">
                  <h2
                    id="conversation-heading"
                    class="text-base font-semibold text-gray-900 dark:text-white"
                  >
                    Conversation ({ticket().messages.length})
                  </h2>
                  <Show when={ticket().messages.length === 0}>
                    <p class="mt-3 text-sm text-gray-600 dark:text-gray-400">
                      No replies yet.
                    </p>
                  </Show>
                  <ol class="mt-4 space-y-4">
                    <For each={ticket().messages}>
                      {message => {
                        const mine = () => message.sender.id === me().id;
                        return (
                          <li
                            class={clsx(
                              "flex",
                              mine() ? "justify-end" : "justify-start"
                            )}
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
                                  mine()
                                    ? "text-blue-100"
                                    : "text-gray-600 dark:text-gray-300"
                                )}
                              >
                                <span class="font-semibold">
                                  {mine() ? "You" : fullName(message.sender)}
                                </span>{" "}
                                ·{" "}
                                <time datetime={message.created_at}>
                                  {formatDateTime(message.created_at)}
                                </time>
                                <Show when={isStaff() && !mine()}>
                                  {" "}
                                  (
                                  <a
                                    href={`mailto:${message.sender.username}`}
                                    class="break-all underline"
                                  >
                                    {message.sender.username}
                                  </a>
                                  )
                                </Show>
                              </p>
                              <p class="mt-1 whitespace-pre-wrap break-words">
                                {message.message}
                              </p>
                              <Show when={message.attachment}>
                                <div class="mt-2 space-y-2">
                                  <Show when={IMAGE.test(message.attachment)}>
                                    <img
                                      src={message.attachment}
                                      alt={`Attachment from ${fullName(
                                        message.sender
                                      )}`}
                                      loading="lazy"
                                      class="max-h-48 max-w-full rounded-lg object-contain"
                                    />
                                  </Show>
                                  <button
                                    type="button"
                                    onClick={() => download(message.attachment)}
                                    class={clsx(
                                      "inline-flex min-h-[44px] items-center gap-1.5 text-sm font-medium underline",
                                      mine()
                                        ? "text-white"
                                        : "text-blue-700 dark:text-blue-300"
                                    )}
                                  >
                                    <Icon
                                      path={arrowDownTray}
                                      class="h-4 w-4"
                                      aria-hidden="true"
                                    />
                                    Download {fileName(message.attachment)}
                                  </button>
                                </div>
                              </Show>
                            </div>
                          </li>
                        );
                      }}
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
                      onInput={e => setAttachment(e.target.files[0])}
                      subLabel="Images or PDF, up to 20MB"
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
    </div>
  );
};

export default TicketDetail;
