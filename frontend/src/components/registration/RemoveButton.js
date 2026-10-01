import clsx from "clsx";
import { createUniqueId, Show } from "solid-js";

// The square ✕ on every unpaid row. Greyed with a reason, never hidden.
// The button is the 44px target; the pastel square inside it is what shows.
const RemoveButton = props => {
  const id = createUniqueId();
  const off = () => Boolean(props.disabledReason) || props.busy;
  return (
    <>
      <button
        type="button"
        class={clsx(
          "group inline-flex min-h-[44px] min-w-[44px] flex-none items-center justify-center rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-red-600 dark:focus-visible:ring-red-400",
          off() && "cursor-not-allowed"
        )}
        aria-label={`Remove ${props.name}`}
        aria-disabled={off() ? "true" : undefined}
        aria-describedby={props.disabledReason ? id : undefined}
        title={props.disabledReason || `Remove ${props.name}`}
        onClick={() => !off() && props.onClick()}
      >
        <span
          aria-hidden="true"
          class={clsx(
            "inline-flex h-8 w-8 items-center justify-center rounded-md border text-base font-bold",
            "border-red-200 bg-red-100 text-red-700 dark:border-red-800 dark:bg-red-900/40 dark:text-red-300",
            off()
              ? "opacity-[0.45]"
              : "group-hover:bg-red-200 dark:group-hover:bg-red-900/60"
          )}
        >
          ✕
        </span>
      </button>
      <Show when={props.disabledReason}>
        <span id={id} class="sr-only">
          {props.disabledReason}
        </span>
      </Show>
    </>
  );
};

export default RemoveButton;
