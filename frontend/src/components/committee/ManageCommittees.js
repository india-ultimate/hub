import { createMutation, useQueryClient } from "@tanstack/solid-query";
import { createSignal, For } from "solid-js";

import { card, Field, input, primaryButton } from "../../committees";
import { saveCommittee } from "../../queries";

// Name, email, description and order for one committee, or a new one.
const CommitteeForm = props => {
  const c = props.committee ?? {};
  const [form, setForm] = createSignal({
    name: c.name ?? "",
    email: c.email ?? "",
    description: c.description ?? "",
    order: c.order ?? props.nextOrder
  });
  const set = key => e => setForm({ ...form(), [key]: e.currentTarget.value });
  const id = name => `${c.slug ?? "new"}-${name}`;

  const queryClient = useQueryClient();
  const save = createMutation({
    mutationFn: saveCommittee,
    onSuccess: () => {
      props.onSaved();
      queryClient.invalidateQueries({ queryKey: ["committees"] });
      if (!c.slug) setForm({ ...form(), name: "", email: "", description: "" });
    }
  });

  return (
    <form
      class={`${card} grid gap-3 sm:grid-cols-2`}
      onSubmit={e => {
        e.preventDefault();
        save.mutate({
          slug: c.slug,
          ...form(),
          order: Number(form().order)
        });
      }}
    >
      <Field id={id("name")} label="Name" error={save.error?.message}>
        <input
          id={id("name")}
          required
          maxlength="100"
          value={form().name}
          onInput={set("name")}
          class={input}
        />
      </Field>
      <Field id={id("email")} label="Shared email">
        <input
          id={id("email")}
          type="email"
          value={form().email}
          onInput={set("email")}
          class={input}
        />
      </Field>
      <Field id={id("description")} label="Description" class="sm:col-span-2">
        <input
          id={id("description")}
          maxlength="300"
          value={form().description}
          onInput={set("description")}
          class={input}
        />
      </Field>
      <Field id={id("order")} label="Order">
        <input
          id={id("order")}
          type="number"
          min="0"
          required
          value={form().order}
          onInput={set("order")}
          class={input}
        />
      </Field>
      <div class="flex items-end justify-end">
        <button type="submit" class={primaryButton} disabled={save.isLoading}>
          {c.slug ? "Save" : "Add committee"}
        </button>
      </div>
    </form>
  );
};

// The Committees tab.
const ManageCommittees = props => (
  <div class="space-y-4">
    <For each={props.committees}>
      {committee => (
        <CommitteeForm committee={committee} onSaved={props.onSaved} />
      )}
    </For>
    <h2 class="pt-2 text-lg font-semibold text-gray-900 dark:text-white">
      New committee
    </h2>
    <CommitteeForm
      onSaved={props.onSaved}
      nextOrder={props.committees.length + 1}
    />
  </div>
);

export default ManageCommittees;
