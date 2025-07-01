import { useNavigate, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { chatBubbleOvalLeftEllipsis } from "solid-heroicons/outline";
import { createEffect, createSignal, For, Show } from "solid-js";

import {
  addTicketMessage,
  fetchTicketDetail,
  fetchUser,
  updateTicket
} from "../../queries";
import { useStore } from "../../store";
import Error from "../alerts/Error";
import Breadcrumbs from "../Breadcrumbs";
import FileInput from "../FileInput";
import TextAreaInput from "../TextAreaInput";

const TicketDetail = () => {
  const params = useParams();
  const navigate = useNavigate();
  const [store] = useStore();
  const [message, setMessage] = createSignal("");
  const [isSubmitting, setIsSubmitting] = createSignal(false);
  const [isAdmin, setIsAdmin] = createSignal(false);
  const [isCreator, setIsCreator] = createSignal(false);
  const [messageError, setMessageError] = createSignal("");
  const queryClient = useQueryClient();
  const [attachment, setAttachment] = createSignal(null);

  const userQuery = createQuery(() => ["me"], fetchUser);
  const ticketQuery = createQuery(
    () => ["ticket", params.id],
    () => fetchTicketDetail(params.id)
  );

  createEffect(() => {
    if (userQuery.data && ticketQuery.data) {
      setIsAdmin(userQuery.data.is_staff || false);
      setIsCreator(userQuery.data.id === ticketQuery.data.created_by.id);
    }
  });

  const addMessageMutation = createMutation({
    mutationFn: data => addTicketMessage(params.id, data),
    onSuccess: () => {
      setMessage("");
      setMessageError("");
      setIsSubmitting(false);
      queryClient.invalidateQueries(["ticket", params.id]);
    },
    onError: error => {
      console.error("Error adding message:", error);
      setMessageError(
        error.message || "Failed to send message. Please try again."
      );
      setIsSubmitting(false);
    }
  });

  const updateTicketMutation = createMutation({
    mutationFn: data => updateTicket(params.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(["ticket", params.id]);
      queryClient.invalidateQueries(["tickets"]);
    },
    onError: error => {
      console.error("Error updating ticket:", error);
      queryClient.invalidateQueries(["tickets"]);
    }
  });

  const handleSubmitMessage = e => {
    e.preventDefault();
    if (!message().trim()) return;

    setIsSubmitting(true);
    addMessageMutation.mutate({ message: message(), attachment: attachment() });
  };

  const handleStatusChange = status => {
    updateTicketMutation.mutate({ status });
  };

  const handleLoginRedirect = () => {
    navigate("/login");
  };

  const handleAssignToMe = () => {
    if (!userQuery.data) return;

    updateTicketMutation.mutate({
      assigned_to_id: userQuery.data.id
    });
  };

  const getStatusBadgeClass = status => {
    switch (status) {
      case "OPN":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300";
      case "PRG":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300";
      case "RES":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300";
      case "CLS":
        return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300";
    }
  };

  const getPriorityBadgeClass = priority => {
    switch (priority) {
      case "URG":
        return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300";
      case "HIG":
        return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300";
      case "MED":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300";
      case "LOW":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300";
    }
  };

  const getStatusText = status => {
    switch (status) {
      case "OPN":
        return "Open";
      case "PRG":
        return "In Progress";
      case "RES":
        return "Resolved";
      case "CLS":
        return "Closed";
      default:
        return status;
    }
  };

  const getPriorityText = priority => {
    switch (priority) {
      case "URG":
        return "Urgent";
      case "HIG":
        return "High";
      case "MED":
        return "Medium";
      case "LOW":
        return "Low";
      default:
        return priority;
    }
  };

  const downloadAttachment = async (url, filename) => {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("Failed to fetch file");

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = filename || "attachment";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // Clean up the object URL
      window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      console.error("Download failed:", error);
      // Fallback: open in new tab
      window.open(url, "_blank");
    }
  };

  const getFilenameFromUrl = url => {
    try {
      const urlObj = new URL(url);
      const pathname = urlObj.pathname;
      const filename = pathname.split("/").pop();
      return filename || "attachment";
    } catch {
      return "attachment";
    }
  };

  return (
    <div class="space-y-4">
      <Show
        when={userQuery.data}
        fallback={
          <div class="rounded-lg bg-yellow-100 p-6 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
            <div class="flex items-center">
              <svg
                class="mr-2 h-5 w-5"
                fill="currentColor"
                viewBox="0 0 20 20"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fill-rule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clip-rule="evenodd"
                />
              </svg>
              <h3 class="text-lg font-medium">Authentication Required</h3>
            </div>
            <div class="mt-2">
              <p>You need to be logged in to view ticket details.</p>
              <button
                onClick={handleLoginRedirect}
                class="mt-3 inline-flex items-center rounded-lg bg-blue-700 px-4 py-2 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
              >
                Log In
              </button>
            </div>
          </div>
        }
      >
        {/* Breadcrumb Navigation */}
        <Breadcrumbs
          icon={chatBubbleOvalLeftEllipsis}
          pageList={[
            { name: "Help", url: "/tickets" },
            { name: `Ticket #${params.id}`, url: "" }
          ]}
        />

        <div class="rounded-lg bg-white dark:bg-gray-800 md:shadow">
          <Show when={ticketQuery.isLoading}>
            <div class="flex justify-center p-8">
              <div class="h-12 w-12 animate-spin rounded-full border-b-2 border-t-2 border-blue-600" />
            </div>
          </Show>

          <Show when={ticketQuery.isError}>
            <div class="md:p-8">
              <div class="text-center text-red-600 dark:text-red-400">
                <p class="text-xl font-bold">Error loading ticket</p>
                <p>
                  {ticketQuery.error?.message || "An unknown error occurred"}
                </p>
              </div>
            </div>
          </Show>

          <Show when={ticketQuery.isSuccess}>
            <div class="border-gray-200 dark:border-gray-700 md:border-b md:p-6">
              <div class="flex items-center justify-between">
                <h2 class="text-2xl font-bold text-gray-800 dark:text-white">
                  Ticket #{ticketQuery.data.id}: {ticketQuery.data.title}
                </h2>
              </div>
              <div class="mt-2 flex space-x-2">
                <span
                  class={`rounded px-2.5 py-0.5 text-sm font-medium ${getStatusBadgeClass(
                    ticketQuery.data.status
                  )}`}
                >
                  {getStatusText(ticketQuery.data.status)}
                </span>
                <span
                  class={`rounded px-2.5 py-0.5 text-sm font-medium ${getPriorityBadgeClass(
                    ticketQuery.data.priority
                  )}`}
                >
                  {getPriorityText(ticketQuery.data.priority)}
                </span>
              </div>

              <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <p class="text-sm text-gray-500 dark:text-gray-400">
                    Created by:{" "}
                    <span class="font-medium text-gray-800 dark:text-white">
                      {ticketQuery.data.created_by.first_name}{" "}
                      {ticketQuery.data.created_by.last_name}
                    </span>
                    <Show
                      when={isAdmin() && ticketQuery.data.created_by.username}
                    >
                      <span class="ml-1 text-sm text-gray-500 dark:text-gray-400">
                        (
                        <a
                          href={`mailto:${ticketQuery.data.created_by.username}`}
                          class="text-blue-600 hover:underline dark:text-blue-400"
                        >
                          {ticketQuery.data.created_by.username}
                        </a>
                        )
                      </span>
                    </Show>
                  </p>
                  <p class="text-sm text-gray-500 dark:text-gray-400">
                    Created on:{" "}
                    <span class="font-medium text-gray-800 dark:text-white">
                      {new Date(ticketQuery.data.created_at).toLocaleString()}
                    </span>
                  </p>
                </div>
                <div>
                  <p class="text-sm text-gray-500 dark:text-gray-400">
                    Assigned to:{" "}
                    <span class="font-medium text-gray-800 dark:text-white">
                      {ticketQuery.data.assigned_to
                        ? `${ticketQuery.data.assigned_to.first_name} ${ticketQuery.data.assigned_to.last_name}`
                        : "Unassigned"}
                    </span>
                    <Show
                      when={isAdmin() && ticketQuery.data.assigned_to?.email}
                    >
                      <span class="ml-1 text-sm text-gray-500 dark:text-gray-400">
                        (
                        <a
                          href={`mailto:${ticketQuery.data.assigned_to.email}`}
                          class="text-blue-600 hover:underline dark:text-blue-400"
                        >
                          {ticketQuery.data.assigned_to.email}
                        </a>
                        )
                      </span>
                    </Show>
                  </p>
                  <Show when={ticketQuery.data.category}>
                    <p class="text-sm text-gray-500 dark:text-gray-400">
                      Category:{" "}
                      <span class="font-medium text-gray-800 dark:text-white">
                        {ticketQuery.data.category}
                      </span>
                    </p>
                  </Show>
                </div>
              </div>

              <div class="mt-6">
                <h3 class="mb-2 text-lg font-medium text-gray-800 dark:text-white">
                  Description
                </h3>
                <div class="rounded-lg bg-gray-50 p-4 dark:bg-gray-700">
                  <p class="whitespace-pre-wrap text-gray-800 dark:text-gray-200">
                    {ticketQuery.data.description}
                  </p>
                </div>
              </div>

              <Show when={isAdmin() || isCreator()}>
                <div class="mt-6">
                  <h3 class="mb-2 text-lg font-medium text-gray-800 dark:text-white">
                    Status Management
                  </h3>
                  <div class="flex flex-wrap gap-2">
                    <button
                      onClick={() => handleStatusChange("OPN")}
                      disabled={ticketQuery.data.status === "OPN"}
                      class="rounded-lg bg-blue-100 px-4 py-2 text-sm font-medium text-blue-800 hover:bg-blue-200 disabled:opacity-50 dark:bg-blue-900 dark:text-blue-300 dark:hover:bg-blue-800"
                    >
                      Mark as Open
                    </button>
                    <button
                      onClick={() => handleStatusChange("PRG")}
                      disabled={ticketQuery.data.status === "PRG"}
                      class="rounded-lg bg-yellow-100 px-4 py-2 text-sm font-medium text-yellow-800 hover:bg-yellow-200 disabled:opacity-50 dark:bg-yellow-900 dark:text-yellow-300 dark:hover:bg-yellow-800"
                    >
                      Mark as In Progress
                    </button>
                    <button
                      onClick={() => handleStatusChange("RES")}
                      disabled={ticketQuery.data.status === "RES"}
                      class="rounded-lg bg-green-100 px-4 py-2 text-sm font-medium text-green-800 hover:bg-green-200 disabled:opacity-50 dark:bg-green-900 dark:text-green-300 dark:hover:bg-green-800"
                    >
                      Mark as Resolved
                    </button>
                    <button
                      onClick={() => handleStatusChange("CLS")}
                      disabled={ticketQuery.data.status === "CLS"}
                      class="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-800 hover:bg-gray-200 disabled:opacity-50 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
                    >
                      Close Ticket
                    </button>
                    <Show when={isAdmin() && userQuery.data}>
                      <button
                        disabled={
                          ticketQuery.data.assigned_to?.id === userQuery.data.id
                        }
                        onClick={handleAssignToMe}
                        class="rounded-lg bg-purple-100 px-4 py-2 text-sm font-medium text-purple-800 hover:bg-purple-200 disabled:opacity-50 dark:bg-purple-900 dark:text-purple-300 dark:hover:bg-purple-800"
                      >
                        Assign to Myself
                      </button>
                    </Show>
                  </div>
                </div>
              </Show>
            </div>

            <div class="pt-6 md:p-6">
              <h3 class="mb-4 text-lg font-medium text-gray-800 dark:text-white">
                Conversation
              </h3>

              <div class="mb-6 max-h-[500px] space-y-4 overflow-y-auto border-b border-gray-200 p-2">
                <Show when={ticketQuery.data.messages.length === 0}>
                  <div class="py-8 text-center text-gray-500 dark:text-gray-400">
                    No messages yet. Start the conversation!
                  </div>
                </Show>

                <For each={ticketQuery.data.messages}>
                  {message => (
                    <div
                      class={`flex ${
                        message.sender.id === store.data?.id
                          ? "justify-end"
                          : "justify-start"
                      }`}
                    >
                      <div
                        class={`max-w-[80%] rounded-lg p-4 ${
                          message.sender.id === store.data?.id
                            ? "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                            : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200"
                        }`}
                      >
                        <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                          <div class="flex items-center gap-1">
                            <span class="font-medium">
                              {message.sender.first_name}{" "}
                              {message.sender.last_name}
                            </span>
                            <Show when={isAdmin() && message.sender.username}>
                              <span class="text-gray-600 dark:text-gray-400">
                                (
                                <a
                                  href={`mailto:${message.sender.username}`}
                                  class="text-blue-600 hover:underline dark:text-blue-400"
                                >
                                  {message.sender.username}
                                </a>
                                )
                              </span>
                            </Show>
                          </div>
                          <span>
                            {(() => {
                              const date = new Date(message.created_at);
                              const now = new Date();
                              const diffInHours =
                                (now - date) / (1000 * 60 * 60);

                              if (diffInHours < 24) {
                                return date.toLocaleTimeString([], {
                                  hour: "numeric",
                                  minute: "2-digit"
                                });
                              } else if (diffInHours < 48) {
                                return `Yesterday ${date.toLocaleTimeString(
                                  [],
                                  { hour: "numeric", minute: "2-digit" }
                                )}`;
                              } else {
                                return (
                                  date.toLocaleDateString([], {
                                    month: "short",
                                    day: "numeric"
                                  }) +
                                  " " +
                                  date.toLocaleTimeString([], {
                                    hour: "numeric",
                                    minute: "2-digit"
                                  })
                                );
                              }
                            })()}
                          </span>
                        </div>
                        <p class="mt-2 whitespace-pre-wrap">
                          {message.message}
                        </p>
                        <Show when={message.attachment}>
                          <div class="mt-2 flex flex-col gap-2">
                            {/* Preview if image */}
                            <Show
                              when={/\.(jpe?g|png|gif|webp|bmp|tiff)$/i.test(
                                message.attachment
                              )}
                            >
                              <img
                                src={message.attachment}
                                alt="Attachment preview"
                                class="max-h-48 rounded border border-gray-300 dark:border-gray-700"
                                style={{
                                  "object-fit": "contain",
                                  "max-width": "100%"
                                }}
                              />
                            </Show>
                            {/* Download button */}
                            <button
                              onClick={() =>
                                downloadAttachment(
                                  message.attachment,
                                  getFilenameFromUrl(message.attachment)
                                )
                              }
                              class="inline-flex cursor-pointer items-center gap-1 border-none bg-transparent p-0 text-sm text-blue-600 hover:underline dark:text-blue-400"
                            >
                              <svg
                                xmlns="http://www.w3.org/2000/svg"
                                class="h-4 w-4"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                              >
                                <path
                                  stroke-linecap="round"
                                  stroke-linejoin="round"
                                  stroke-width="2"
                                  d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V4"
                                />
                              </svg>
                              Download Attachment
                            </button>
                          </div>
                        </Show>
                      </div>
                    </div>
                  )}
                </For>
              </div>

              <form onSubmit={handleSubmitMessage} class="mt-4">
                <Show when={messageError()}>
                  <div class="mb-4">
                    <Error text={messageError()} />
                  </div>
                </Show>
                <TextAreaInput
                  name="message"
                  label="Your message"
                  value={message()}
                  onInput={e => setMessage(e.target.value)}
                  placeholder="Type your message here..."
                  padding={false}
                />
                <div class="mb-4">
                  <FileInput
                    name="attachment"
                    label="Attachment (optional)"
                    accept="image/*,application/pdf"
                    value={attachment()}
                    onInput={e => setAttachment(e.target.files[0])}
                    subLabel="Allowed: images or PDF, max 20MB"
                  />
                  <Show when={attachment()}>
                    <div class="mt-2 flex items-center gap-2 text-sm">
                      <span>Selected: {attachment().name}</span>
                      <button
                        type="button"
                        class="text-red-600 underline"
                        onClick={() => setAttachment(null)}
                      >
                        Remove
                      </button>
                    </div>
                  </Show>
                </div>
                <button
                  type="submit"
                  disabled={isSubmitting() || !message().trim()}
                  class="rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:opacity-50 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                >
                  {isSubmitting() ? "Sending..." : "Send Message"}
                </button>
              </form>
            </div>
          </Show>
        </div>
      </Show>
    </div>
  );
};

export default TicketDetail;
