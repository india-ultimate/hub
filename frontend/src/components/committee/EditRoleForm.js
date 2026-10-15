import { createMutation } from "@tanstack/solid-query";
import { createSignal, Show } from "solid-js";

import {
  dangerButton,
  Field,
  focusRing,
  input,
  primaryButton,
  secondaryButton
} from "../../committees";
import { deleteCommitteeRole, updateCommitteeRole } from "../../queries";

// Fix a role's title, chair flag or start date, or delete one added by mistake.
const EditRoleForm = props => {
  const [title, setTitle] = createSignal(props.role.title);
  const [chair, setChair] = createSignal(props.role.is_chair);
  const [start, setStart] = createSignal(props.role.start_date);
  const [confirming, setConfirming] = createSignal(false);

  const save = createMutation({
    mutationFn: updateCommitteeRole,
    onSuccess: props.done
  });
  const remove = createMutation({
    mutationFn: deleteCommitteeRole,
    onSuccess: props.done
  });
  const error = () => save.error?.message || remove.error?.message;

  return (
    <Show
      when={!confirming()}
      fallback={
        <div class="space-y-4">
          <p class="text-sm">
            Delete {props.role.person.full_name}'s role? Use this only for a
            role added by mistake; to record a past term, end it instead.
          </p>
          <Show when={error()}>
            <p role="alert" class="text-sm text-red-700 dark:text-red-400">
              {error()}
            </p>
          </Show>
          <div class="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              class={secondaryButton}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              class={dangerButton}
              disabled={remove.isLoading}
              onClick={() => remove.mutate(props.role.id)}
            >
              Delete
            </button>
          </div>
        </div>
      }
    >
      <form
        onSubmit={e => {
          e.preventDefault();
          save.mutate({
            id: props.role.id,
            title: title(),
            is_chair: chair(),
            start_date: start()
          });
        }}
        class="space-y-4"
      >
        <Field id="edit-title" label="Title">
          <input
            id="edit-title"
            required
            maxlength="60"
            value={title()}
            onInput={e => setTitle(e.currentTarget.value)}
            class={input}
          />
        </Field>
        <label class="flex min-h-[44px] items-center gap-2 text-sm text-gray-900 dark:text-white">
          <input
            type="checkbox"
            checked={chair()}
            onChange={e => setChair(e.currentTarget.checked)}
            class="h-5 w-5 rounded border-gray-300 text-blue-700 focus:ring-blue-500"
          />
          Chair
        </label>
        <Field id="edit-start" label="Start date">
          <input
            id="edit-start"
            type="date"
            required
            value={start()}
            onInput={e => setStart(e.currentTarget.value)}
            class={input}
          />
        </Field>
        <Show when={error()}>
          <p role="alert" class="text-sm text-red-700 dark:text-red-400">
            {error()}
          </p>
        </Show>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setConfirming(true)}
            class={`min-h-[44px] rounded px-2 text-sm font-medium text-red-700 underline dark:text-red-400 ${focusRing}`}
          >
            Delete: added by mistake
          </button>
          <button type="submit" class={primaryButton} disabled={save.isLoading}>
            Save
          </button>
        </div>
      </form>
    </Show>
  );
};

export default EditRoleForm;
