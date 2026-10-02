import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { createUniqueId, Show } from "solid-js";

import { actionBase, actionHover, kindOf, KINDS } from "../../reasonKinds";

const primary =
  "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 motion-reduce:transition-none dark:bg-blue-600 dark:focus-visible:ring-blue-800";
const primaryHover = "hover:bg-blue-800 dark:hover:bg-blue-700";
const link =
  "inline-flex min-h-[44px] items-center px-2 text-sm font-semibold text-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-blue-400";

// Greyed buttons stay focusable (aria-disabled, not disabled) so a screen
// reader still reaches the reason line that says why.
const ReasonButton = props => {
  const id = createUniqueId();
  const blocked = () => Boolean(props.reason) || Boolean(props.busy);
  const isPrimary = () => props.primary !== false;
  return (
    <div>
      <button
        ref={props.ref}
        type="button"
        class={clsx(
          props.link ? link : isPrimary() ? primary : actionBase,
          // Hover only when it can be pressed.
          blocked()
            ? "cursor-not-allowed opacity-[0.45]"
            : props.link
            ? "hover:underline"
            : isPrimary()
            ? primaryHover
            : actionHover
        )}
        aria-disabled={blocked() ? "true" : undefined}
        aria-describedby={props.reason ? id : undefined}
        onClick={() => !blocked() && props.onClick?.()}
      >
        <Show when={props.busy} fallback={props.label}>
          <Icon
            path={KINDS.progress.icon}
            class="h-4 w-4 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
          {props.busyLabel || "Working…"}
        </Show>
      </button>
      <Show when={props.reason}>
        <p
          id={id}
          class={clsx(
            "mt-1 flex items-start gap-1.5 text-xs",
            kindOf(props.reason.kind).tone
          )}
        >
          <Icon
            path={kindOf(props.reason.kind).icon}
            class="mt-0.5 h-4 w-4 flex-none"
            aria-hidden="true"
          />
          <span>{props.reason.text}</span>
        </p>
      </Show>
    </div>
  );
};

export default ReasonButton;
