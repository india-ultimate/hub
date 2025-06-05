import { createMutation, createQuery } from "@tanstack/solid-query";
import { createEffect, For, onMount, Show } from "solid-js";

import {
  clearChatHistory,
  fetchChatHistory,
  fetchMembershipStatus,
  sendChatMessage
} from "../../queries";
import { useStore } from "../../store";
import Error from "../alerts/Error";
import ChatHeader from "./ChatHeader";
import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";

const ChatPage = () => {
  const [store] = useStore();
  let messagesEndRef;

  // Fetch membership status
  const membershipQuery = createQuery({
    queryKey: () => ["membership", "status"],
    queryFn: fetchMembershipStatus
  });

  // Fetch chat history
  const historyQuery = createQuery({
    queryKey: () => ["chat", "history"],
    queryFn: fetchChatHistory
  });

  // Send message mutation
  const sendMessageMutation = createMutation({
    mutationFn: sendChatMessage,
    onSuccess: () => {
      // Refetch history after sending message
      historyQuery.refetch();
    }
  });

  // Clear history mutation
  const clearHistoryMutation = createMutation({
    mutationFn: clearChatHistory,
    onSuccess: () => {
      // Refetch history after clearing
      historyQuery.refetch();
    }
  });

  const scrollToBottom = () => {
    setTimeout(() => {
      messagesEndRef?.scrollIntoView({ behavior: "smooth" });
    }, 500);
  };

  // Scroll to bottom on mount and when messages change
  onMount(() => {
    scrollToBottom();
  });

  createEffect(() => {
    if (historyQuery.data?.messages) {
      scrollToBottom();
    }
  });

  const handleSendMessage = async message => {
    if (!message.trim()) return;
    sendMessageMutation.mutate(message);
  };

  const handleClearHistory = () => {
    clearHistoryMutation.mutate();
  };

  if (!store?.data) {
    return (
      <div class="flex h-full items-center justify-center">
        <a
          href="/login"
          class="rounded-lg bg-blue-600 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:focus:ring-blue-800"
        >
          Login to Chat
        </a>
      </div>
    );
  }

  return (
    <Show when={membershipQuery.isSuccess && historyQuery.isSuccess}>
      <Show
        when={membershipQuery.isSuccess && membershipQuery.data.is_active}
        fallback={
          <div class="flex h-full flex-col items-center justify-center gap-4 p-4 text-center">
            <h2 class="text-xl font-semibold text-gray-900 dark:text-white">
              India Ultimate Membership Required
            </h2>
            <p class="text-gray-600 dark:text-gray-400">
              You need an active India Ultimate membership to use the chat
              feature. This helps us maintain a safe and verified community.
            </p>
          </div>
        }
      >
        <div class="flex h-full flex-col">
          <ChatHeader onClearHistory={handleClearHistory} />
          <div class="flex-1 overflow-y-auto p-4">
            <Show when={historyQuery.isLoading || membershipQuery.isLoading}>
              <p class="text-center text-gray-500">Loading...</p>
            </Show>

            <Show when={historyQuery.error}>
              <Error text={historyQuery.error.message} />
            </Show>

            <Show when={membershipQuery.error}>
              <Error text={membershipQuery.error.message} />
            </Show>

            <Show when={sendMessageMutation.error}>
              <Error text={sendMessageMutation.error.message} />
            </Show>

            <Show when={clearHistoryMutation.error}>
              <Error text={clearHistoryMutation.error.message} />
            </Show>

            <div class="space-y-4">
              <Show
                when={historyQuery.data?.messages?.length}
                fallback={
                  <div class="flex h-full items-center justify-center py-8">
                    <p class="text-sm text-gray-500 dark:text-gray-400">
                      No messages available. Start a conversation!
                    </p>
                  </div>
                }
              >
                <For each={historyQuery.data?.messages}>
                  {msg => (
                    <ChatMessage
                      message={msg.message}
                      type={msg.type}
                      timestamp={msg.timestamp}
                    />
                  )}
                </For>
              </Show>
              <div ref={messagesEndRef} />
            </div>
          </div>
          <div class="border-t border-gray-200 p-4 dark:border-gray-700">
            <ChatInput
              onSendMessage={handleSendMessage}
              loading={sendMessageMutation.isLoading}
            />
            <p class="mt-3 text-center text-xs text-gray-400 dark:text-gray-500">
              Note: Only publicly available data is sent to Groq - our 3rd Party
              AI hosting provider which is using Open Source Llama-3.1 model
              internally. Personal information like email, phone number, or date
              of birth is never shared.
            </p>
          </div>
        </div>
      </Show>
    </Show>
  );
};

export default ChatPage;
