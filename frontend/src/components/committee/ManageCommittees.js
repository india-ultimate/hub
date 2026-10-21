import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import {
  card,
  Field,
  input,
  primaryButton,
  secondaryButton
} from "../../committees";
import { deleteCommittee, fetchCommittee, saveCommittee } from "../../queries";
import ConfirmDialog from "../ConfirmDialog";
import PostSwitch from "./PostSwitch";

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

  const setCanPost = async data => {
    await saveCommittee(data);
    props.onSaved();
    await queryClient.invalidateQueries(
      { queryKey: ["committees"] },
      { throwOnError: true }
    );
  };

  // The roles it would take with it, counted once the dialog asks.
  const [request, setRequest] = createSignal(null);
  const detail = createQuery(
    () => ["committee", c.slug],
    () => fetchCommittee(c.slug),
    {
      get enabled() {
        return Boolean(request());
      },
      // The counts must be current: it is a deletion.
      staleTime: 0
    }
  );
  const remove = createMutation({
    mutationFn: deleteCommittee,
    onSuccess: () => {
      props.onSaved();
      queryClient.removeQueries({ queryKey: ["committee", c.slug] });
      queryClient.invalidateQueries({ queryKey: ["committees"] });
      queryClient.invalidateQueries({ queryKey: ["ticket-routes"] });
    }
  });
  const askDelete = () =>
    setRequest({
      title: "Delete committee",
      get message() {
        if (!detail.data) return `Delete ${c.name}?`;
        const { roles, past_roles } = detail.data;
        return `Delete ${c.name}? This removes ${roles.length} current and ${past_roles.length} past roles, and its ticket routing goes too. Tickets are kept.`;
      },
      get disabled() {
        return !detail.isSuccess || detail.isFetching;
      },
      get error() {
        return detail.error?.message;
      },
      retry: () => detail.refetch(),
      confirm: "Delete committee",
      danger: true,
      run: () => remove.mutate(c.slug)
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
      <Show when={c.slug}>
        <PostSwitch
          label="Everyone in this committee can post announcements"
          checked={c.can_post_announcements}
          onChange={can_post_announcements =>
            setCanPost({
              slug: c.slug,
              name: c.name,
              email: c.email,
              description: c.description,
              order: c.order,
              can_post_announcements,
              can_create_forms: c.can_create_forms
            })
          }
        />
        <PostSwitch
          label="Everyone in this committee can create forms"
          checked={c.can_create_forms}
          onChange={can_create_forms =>
            setCanPost({
              slug: c.slug,
              name: c.name,
              email: c.email,
              description: c.description,
              order: c.order,
              can_post_announcements: c.can_post_announcements,
              can_create_forms
            })
          }
        />
      </Show>
      <div class="flex flex-wrap items-end justify-end gap-2 sm:col-span-2">
        <Show when={c.slug}>
          <button type="button" class={secondaryButton} onClick={askDelete}>
            Delete committee
          </button>
        </Show>
        <button type="submit" class={primaryButton} disabled={save.isLoading}>
          {c.slug ? "Save" : "Add committee"}
        </button>
      </div>
      <Show when={remove.error}>
        <p
          role="alert"
          class="text-sm text-red-700 dark:text-red-400 sm:col-span-2"
        >
          {remove.error.message}
        </p>
      </Show>
      <ConfirmDialog request={request} close={() => setRequest(null)} />
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
