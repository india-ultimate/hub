import { Icon } from "solid-heroicons";
import { paperAirplane } from "solid-heroicons/solid";
import { createEffect, createSignal } from "solid-js";

import { Spinner } from "../../icons";

const ChatInput = props => {
  const [message, setMessage] = createSignal("");
  let textareaRef;

  const handleSubmit = e => {
    e.preventDefault();
    if (message().trim() && !props.loading) {
      props.onSendMessage(message());
      setMessage("");
      // Reset textarea height after sending
      if (textareaRef) {
        textareaRef.style.height = "auto";
      }
    }
  };

  // Auto-resize textarea
  createEffect(() => {
    if (textareaRef) {
      textareaRef.style.height = "auto";
      const scrollHeight = textareaRef.scrollHeight;
      textareaRef.style.height = scrollHeight + "px";
      console.log(message());
    }
  });

  return (
    <form onSubmit={handleSubmit} class="flex gap-2">
      <div class="relative flex-1">
        <textarea
          ref={textareaRef}
          value={message()}
          onInput={e => setMessage(e.target.value)}
          placeholder="Ask anything..."
          rows="1"
          class="block w-full resize-none overflow-hidden rounded-lg border border-gray-300 bg-white p-3 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          disabled={props.loading}
          style={{ "min-height": "42px", "max-height": "200px" }}
        />
      </div>
      <button
        type="submit"
        disabled={props.loading || !message().trim()}
        class="inline-flex items-center rounded-lg bg-blue-700 px-4 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800  disabled:cursor-not-allowed disabled:opacity-50 "
      >
        {props.loading ? (
          <Spinner noMargin height="16" width="16" />
        ) : (
          <Icon path={paperAirplane} class="h-4 w-4" />
        )}
      </button>
    </form>
  );
};

export default ChatInput;
