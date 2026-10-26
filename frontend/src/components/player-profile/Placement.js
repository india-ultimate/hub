import { Icon } from "solid-heroicons";
import { trophy } from "solid-heroicons/solid";
import { Show } from "solid-js";

import { ordinal } from "../../dates";

const PODIUM = {
  1: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  2: "bg-blue-50 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  3: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
};

const Placement = props => (
  <Show
    when={props.t.status === "LIV"}
    fallback={
      <Show when={props.t.placement}>
        <Show
          when={PODIUM[props.t.placement]}
          fallback={
            <span class="h-fit rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700 dark:bg-gray-700 dark:text-gray-300">
              {ordinal(props.t.placement)}
            </span>
          }
        >
          <span
            class={`inline-flex h-fit items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${PODIUM[props.t.placement]}`}
          >
            <Icon class="h-3.5 w-3.5" path={trophy} />
            {ordinal(props.t.placement)}
          </span>
        </Show>
      </Show>
    }
  >
    <span class="inline-flex h-fit items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900 dark:text-red-300">
      <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-red-500 motion-reduce:animate-none" />
      Live
    </span>
  </Show>
);

export default Placement;
