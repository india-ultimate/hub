import { Icon } from "solid-heroicons";
import { trash } from "solid-heroicons/solid";
import { Show } from "solid-js";

const ChatHeader = props => {
  return (
    <div class="border-b border-gray-200 p-4 dark:border-gray-700">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-bold text-blue-600 md:text-2xl">Chat</h2>
        <Show when={props.onClearHistory}>
          <button
            onClick={props.onClearHistory}
            class="inline-flex items-center gap-2 rounded-lg bg-rose-100 px-4 py-2 text-sm font-medium text-rose-600 hover:bg-rose-200 focus:outline-none focus:ring-4 focus:ring-rose-200 dark:bg-rose-900/30 dark:text-rose-400 dark:hover:bg-rose-900/50 dark:focus:ring-rose-900/50"
          >
            <Icon class="h-4 w-4" path={trash} />
            Clear
          </button>
        </Show>
      </div>
      <p class="mt-3 text-xs italic text-gray-500 md:text-sm">
        This is a AI Chatbot that can help you with all the data in the Hub. It
        can perform analysis and provide insights as well! :D
      </p>
    </div>
  );
};

export default ChatHeader;
