import { Icon } from "solid-heroicons";
import { check, documentDuplicate } from "solid-heroicons/outline";
import { createSignal, onCleanup, Show } from "solid-js";

// Copies a code block's text, such as a prompt to paste into an AI agent.
const CopyButton = props => {
  const [state, setState] = createSignal("idle");
  let timer;
  onCleanup(() => clearTimeout(timer));

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(props.text());
      setState("copied");
    } catch {
      setState("failed");
    }
    clearTimeout(timer);
    timer = setTimeout(() => setState("idle"), 2000);
  };

  const label = () =>
    ({ copied: "Copied", failed: "Couldn't copy. Select the text instead." })[
      state()
    ] ?? "Copy";

  return (
    <>
      <button
        type="button"
        onClick={copy}
        aria-label={label()}
        title={label()}
        class="absolute right-1.5 top-1.5 inline-flex h-10 w-10 items-center justify-center rounded-md text-gray-500 transition-colors duration-150 hover:bg-gray-200 hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-white"
      >
        <Show
          when={state() === "copied"}
          fallback={
            <Icon path={documentDuplicate} class="h-5 w-5" aria-hidden="true" />
          }
        >
          <Icon
            path={check}
            class="h-5 w-5 text-green-600 dark:text-green-400"
            aria-hidden="true"
          />
        </Show>
      </button>
      <span class="sr-only" role="status">
        <Show when={state() !== "idle"}>{label()}</Show>
      </span>
    </>
  );
};

export default CopyButton;
