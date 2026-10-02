import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/outline";
import { createUniqueId, Show } from "solid-js";

// A quiet grey ✕ on every unpaid row; red only on hover or focus.
// Greyed with a reason, never hidden. The button is the 44px target.
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
        <Icon
          path={xMark}
          aria-hidden="true"
          class={clsx(
            "h-5 w-5 text-gray-400 dark:text-gray-500",
            off()
              ? "opacity-[0.45]"
              : "group-hover:text-red-700 group-focus-visible:text-red-700 dark:group-hover:text-red-400"
          )}
        />
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
