import { A } from "@solidjs/router";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { For, Show } from "solid-js";

import { actionBase, actionHover, kindOf } from "../../reasonKinds";

const button = clsx(actionBase, actionHover);

// A link when the server gave a place to go, else a button for the page.
const ActionButton = props => (
  <Show
    when={props.action.href}
    fallback={
      <button
        type="button"
        class={button}
        onClick={() => props.onOp?.(props.action.op)}
      >
        {props.action.label}
      </button>
    }
  >
    <A href={props.action.href} class={button}>
      {props.action.label}
    </A>
  </Show>
);

// A tinted strip saying what the step is waiting on, with the fix beside it.
// Only the team fee has a second button (pay part now).
const Callout = props => {
  const kind = () => kindOf(props.callout.kind);
  const actions = () =>
    [props.callout.action, props.callout.secondary_action].filter(Boolean);
  return (
    <div
      class={clsx(
        "flex flex-wrap items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-sm",
        kind().strip,
        kind().tone
      )}
    >
      <span class="flex items-start gap-2">
        <Icon
          path={kind().icon}
          class="mt-0.5 h-5 w-5 flex-none"
          aria-hidden="true"
        />
        <span>{props.callout.text}</span>
      </span>
      <Show when={actions().length}>
        <div class="flex flex-wrap gap-2">
          <For each={actions()}>
            {action => <ActionButton action={action} onOp={props.onOp} />}
          </For>
        </div>
      </Show>
    </div>
  );
};

export default Callout;
