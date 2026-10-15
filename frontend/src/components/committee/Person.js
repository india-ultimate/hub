import clsx from "clsx";
import { Show } from "solid-js";

import { ChairBadge } from "../../committees";
import Avatar from "./Avatar";

// One role holder: photo, name, and the title (a badge for chairs).
const Person = props => (
  <div
    class={clsx(
      "flex min-w-0 items-center gap-3",
      props.stacked && "flex-col text-center"
    )}
  >
    <Avatar
      src={props.role.person.profile_pic_url}
      name={props.role.person.full_name}
      class={props.stacked ? "h-20 w-20 text-xl" : "h-10 w-10 text-sm"}
    />
    <div class="min-w-0">
      <p class="break-words font-medium text-gray-900 dark:text-white">
        {props.role.person.full_name}
      </p>
      <p class="text-sm text-gray-600 dark:text-gray-400">
        <Show when={props.role.is_chair} fallback={props.role.title}>
          <ChairBadge />
        </Show>
        <Show when={props.role.is_chair && props.role.title !== "Chair"}>
          <span class="ml-1.5">{props.role.title}</span>
        </Show>
      </p>
    </div>
  </div>
);

export default Person;
