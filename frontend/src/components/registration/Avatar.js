import clsx from "clsx";
import { createSignal, Show } from "solid-js";

const initials = name =>
  (name || "?")
    .split(" ")
    .filter(Boolean)
    .map(w => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

// A player's photo, or their initials when there's none or it won't load.
// The name sits beside it, so the image itself says nothing to a reader.
const Avatar = props => {
  const [broken, setBroken] = createSignal(false);
  return (
    <Show
      when={props.photo && !broken()}
      fallback={
        <span
          aria-hidden="true"
          class={clsx(
            "flex h-8 w-8 flex-none items-center justify-center rounded-full text-xs font-bold",
            props.paid
              ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
              : "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
          )}
        >
          {initials(props.name)}
        </span>
      }
    >
      <img
        src={props.photo}
        alt=""
        loading="lazy"
        class="h-8 w-8 flex-none rounded-full object-cover"
        onError={() => setBroken(true)}
      />
    </Show>
  );
};

export default Avatar;
