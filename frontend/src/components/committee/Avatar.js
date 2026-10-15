import clsx from "clsx";
import { Show } from "solid-js";

import { initials } from "../../committees";

// A profile photo, or the person's initials on gray.
const Avatar = props => (
  <Show
    when={props.src}
    fallback={
      <div
        role="img"
        aria-label={props.name}
        class={clsx(
          "flex shrink-0 items-center justify-center rounded-full bg-gray-200 font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300",
          props.class ?? "h-10 w-10 text-sm"
        )}
      >
        {initials(props.name)}
      </div>
    }
  >
    <img
      src={props.src}
      alt={props.name}
      class={clsx(
        "shrink-0 rounded-full object-cover",
        props.class ?? "h-10 w-10"
      )}
      loading="lazy"
    />
  </Show>
);

export default Avatar;
