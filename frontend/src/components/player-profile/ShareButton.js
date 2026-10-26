import { Icon } from "solid-heroicons";
import { share } from "solid-heroicons/solid";
import { createSignal } from "solid-js";

const ShareButton = props => {
  const [message, setMessage] = createSignal("");
  let timer;
  const say = text => {
    setMessage(text);
    clearTimeout(timer);
    timer = setTimeout(() => setMessage(""), 2000);
  };
  const onShare = async () => {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title: props.name, url });
      } catch {
        // Dismissing the share sheet rejects; there is nothing to recover.
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      say("Link copied");
    } catch {
      say("Couldn't copy link");
    }
  };
  return (
    <div class="mt-8 text-center">
      <button
        type="button"
        onClick={onShare}
        class="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm ring-1 ring-gray-200 transition duration-200 hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:bg-gray-700 dark:text-gray-200 dark:ring-gray-600 dark:hover:bg-gray-600"
      >
        <Icon class="h-4 w-4" path={share} />
        {props.label}
      </button>
      <p
        role="status"
        aria-live="polite"
        class="mt-2 min-h-5 text-sm text-gray-600 dark:text-gray-300"
      >
        {message()}
      </p>
    </div>
  );
};

export default ShareButton;
