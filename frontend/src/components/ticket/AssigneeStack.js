import { For, Show } from "solid-js";

import { fullName } from "../../tickets";
import Avatar from "../committee/Avatar";

const SHOWN = 3;

// Up to three assignee photos, overlapping a little (so initials stay
// readable), then "+N".
const AssigneeStack = props => (
  <Show when={props.assignees.length}>
    <span class="inline-flex items-center">
      <span class="sr-only">
        Assigned to {props.assignees.map(fullName).join(", ")}
      </span>
      <span class="flex -space-x-1" aria-hidden="true">
        <For each={props.assignees.slice(0, SHOWN)}>
          {user => (
            <Avatar
              src={user.profile_pic_url}
              name={fullName(user)}
              class="h-6 w-6 text-[10px] ring-2 ring-white dark:ring-gray-800"
            />
          )}
        </For>
      </span>
      <Show when={props.assignees.length > SHOWN}>
        <span class="ml-1 text-xs" aria-hidden="true">
          +{props.assignees.length - SHOWN}
        </span>
      </Show>
    </span>
  </Show>
);

export default AssigneeStack;
