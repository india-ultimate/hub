import { createMutation, useQueryClient } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { plus, xMark } from "solid-heroicons/solid-mini";
import { createSignal, For, Show } from "solid-js";

import { focusRing, secondaryButton } from "../../committees";
import { setTicketAssignee } from "../../queries";
import { fullName } from "../../tickets";
import Avatar from "../committee/Avatar";
import AssigneePicker from "./AssigneePicker";

// Who a ticket is assigned to. Handlers get the controls; others see names.
const Assignees = props => {
  const queryClient = useQueryClient();
  const [picking, setPicking] = createSignal(false);
  const [error, setError] = createSignal("");
  let addButton;
  const closePicker = () => {
    setPicking(false);
    addButton.focus();
  };

  const change = createMutation({
    mutationFn: setTicketAssignee,
    onMutate: () => setError(""),
    onSuccess: () => {
      closePicker();
      queryClient.invalidateQueries({ queryKey: ["ticket", props.ticketId] });
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
    },
    onError: e => setError(e.message)
  });
  const set = (user, assigned) =>
    change.mutate({ ticketId: props.ticketId, userId: user.id, assigned });

  const ids = () => props.ticket.assignees.map(a => a.id);

  return (
    <div>
      <h3 id="assignees-label" class="text-sm text-gray-600 dark:text-gray-400">
        Assignees
      </h3>
      <ul
        aria-labelledby="assignees-label"
        class="mt-2 flex flex-wrap items-center gap-2"
      >
        <For
          each={props.ticket.assignees}
          fallback={
            <li class="text-sm font-medium text-gray-900 dark:text-white">
              Unassigned
            </li>
          }
        >
          {user => (
            <li class="inline-flex min-h-[44px] items-center gap-2 rounded-full bg-gray-100 pl-1 text-sm font-medium text-gray-900 dark:bg-gray-700 dark:text-white">
              <Avatar
                src={user.profile_pic_url}
                name={fullName(user)}
                class="h-8 w-8 text-xs"
              />
              <span class={props.ticket.can_handle ? "" : "pr-3"}>
                {fullName(user)}
              </span>
              <Show when={props.ticket.can_handle}>
                <button
                  type="button"
                  aria-label={`Remove ${fullName(user)}`}
                  disabled={change.isLoading}
                  onClick={() => set(user, false)}
                  class={`inline-flex h-11 w-11 items-center justify-center rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 ${focusRing}`}
                >
                  <Icon path={xMark} class="h-4 w-4" aria-hidden="true" />
                </button>
              </Show>
            </li>
          )}
        </For>
      </ul>
      <Show when={props.ticket.can_handle}>
        <div class="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            id="add-assignee"
            ref={addButton}
            aria-expanded={picking()}
            class={`${secondaryButton} gap-1`}
            onClick={() => setPicking(!picking())}
          >
            <Icon path={plus} class="h-4 w-4" aria-hidden="true" />
            Add
          </button>
          <Show when={props.isStaff && !ids().includes(props.me.id)}>
            <button
              type="button"
              id="assign-to-me"
              class={secondaryButton}
              disabled={change.isLoading}
              onClick={() => set(props.me, true)}
            >
              Assign to me
            </button>
          </Show>
        </div>
        <Show when={picking()}>
          <AssigneePicker
            assigned={ids()}
            routed={props.ticket.routed_committees}
            onPick={person => set(person, true)}
            onClose={closePicker}
          />
        </Show>
        <Show when={error()}>
          <p role="alert" class="mt-2 text-sm text-red-700 dark:text-red-400">
            {error()}
          </p>
        </Show>
      </Show>
    </div>
  );
};

export default Assignees;
