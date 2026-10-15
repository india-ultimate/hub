import { createMutation } from "@tanstack/solid-query";
import { createSignal } from "solid-js";

import {
  dangerButton,
  Field,
  input,
  secondaryButton,
  todayInput
} from "../../committees";
import { updateCommitteeRole } from "../../queries";

// Ending a term: the role stops holding on the end date, and access with it.
const EndTermForm = props => {
  const [end, setEnd] = createSignal(todayInput());
  const endTerm = createMutation({
    mutationFn: updateCommitteeRole,
    onSuccess: props.done
  });

  return (
    <form
      onSubmit={e => {
        e.preventDefault();
        endTerm.mutate({ id: props.role.id, end_date: end() });
      }}
      class="space-y-4"
    >
      <p class="text-sm">
        End {props.role.person.full_name}'s term as {props.role.title}? They
        lose access to this committee's tickets from the end date.
      </p>
      <Field id="end-date" label="End date" error={endTerm.error?.message}>
        <input
          id="end-date"
          type="date"
          required
          value={end()}
          onInput={e => setEnd(e.currentTarget.value)}
          class={input}
        />
      </Field>
      <div class="flex flex-wrap justify-end gap-2">
        <button type="button" class={secondaryButton} onClick={props.cancel}>
          Cancel
        </button>
        <button type="submit" class={dangerButton} disabled={endTerm.isLoading}>
          End term
        </button>
      </div>
    </form>
  );
};

export default EndTermForm;
