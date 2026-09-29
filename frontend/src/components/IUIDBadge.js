import { Show } from "solid-js";

// tabular-nums so the digits don't reflow; blue pair matches the role badges.
const IUIDBadge = props => (
  <Show when={props.id}>
    <span
      class="inline-flex items-center whitespace-nowrap rounded-full bg-blue-100 px-3 py-1 font-mono text-sm font-semibold tabular-nums tracking-wide text-blue-800 dark:bg-blue-900 dark:text-blue-300"
      title="India Ultimate ID"
      aria-label={`India Ultimate ID ${props.id}`}
      data-testid="iu-id"
    >
      {props.id}
    </span>
  </Show>
);

export default IUIDBadge;
