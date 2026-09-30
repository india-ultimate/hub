import { createForm, getValue, required, reset } from "@modular-forms/solid";
import { A, useNavigate } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import {
  chatBubbleOvalLeftEllipsis,
  lockClosed
} from "solid-heroicons/outline";
import {
  createEffect,
  createSignal,
  For,
  Index,
  on,
  onCleanup,
  Show
} from "solid-js";

import { createTicket, fetchTickets, fetchUser } from "../../queries";
import { CATEGORIES, PRIORITIES, StatusBadge } from "../../tickets";
import ErrorAlert from "../alerts/Error";
import Breadcrumbs from "../Breadcrumbs";
import UpvoteButton from "./UpvoteButton";

const input =
  "block w-full rounded-lg border border-gray-300 bg-white p-3 text-base text-gray-900 focus:border-blue-500 focus:ring-blue-500 aria-[invalid=true]:border-red-600 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400";
const label = "mb-2 block text-sm font-medium text-gray-900 dark:text-white";
const fieldError = "mt-1 text-sm text-red-600 dark:text-red-400";

const CreateTicket = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [error, setError] = createSignal("");
  const userQuery = createQuery(() => ["me"], fetchUser);

  const [form, { Form, Field }] = createForm({
    initialValues: {
      title: "",
      category: "",
      priority: "MED",
      description: "",
      is_private: false
    },
    validateOn: "touched",
    revalidateOn: "input"
  });

  // Suggestions follow the title, 400ms after typing stops
  const [typed, setTyped] = createSignal("");
  let timer;
  onCleanup(() => clearTimeout(timer));
  createEffect(
    on(
      () => getValue(form, "title") ?? "",
      title => {
        clearTimeout(timer);
        timer = setTimeout(() => setTyped(title.trim()), 400);
      }
    )
  );

  // A private ticket is about you, so a public one won't be the same issue
  const suggesting = () => typed().length >= 5 && !getValue(form, "is_private");

  const suggestionsQuery = createQuery(
    () => ["tickets", "suggestions", typed()],
    () => fetchTickets({ q: typed(), excludePrivate: true, sort: "relevance" }),
    {
      get enabled() {
        return suggesting();
      }
    }
  );

  // Only tickets that matched: a title of filler words ("How do I get") is no
  // search at all, and the API then lists every ticket, newest first
  const suggestions = () =>
    suggesting()
      ? (suggestionsQuery.data?.items ?? [])
          .filter(ticket => ticket.score)
          .slice(0, 3)
      : [];

  const mutation = createMutation({
    mutationFn: createTicket,
    onSuccess: data => {
      queryClient.invalidateQueries(["tickets"]);
      reset(form);
      navigate(`/tickets/${data.id}`);
    },
    onError: e =>
      setError(e.message || "Couldn't create the ticket. Please try again.")
  });

  const submit = values => {
    setError("");
    mutation.mutate({ ...values, category: values.category || null });
  };

  return (
    <div class="mx-auto max-w-2xl space-y-4">
      <Breadcrumbs
        icon={chatBubbleOvalLeftEllipsis}
        pageList={[
          { name: "Help", url: "/tickets" },
          { name: "New ticket", url: "" }
        ]}
      />

      <Show when={!userQuery.isLoading && !userQuery.data}>
        <div class="rounded-xl border border-yellow-300 bg-yellow-50 p-6 text-yellow-900">
          <h2 class="text-lg font-semibold">Log in to ask for help</h2>
          <A
            href="/login"
            class="mt-4 inline-flex min-h-[44px] items-center rounded-lg bg-blue-700 px-5 text-sm font-medium text-white hover:bg-blue-800"
          >
            Log in
          </A>
        </div>
      </Show>

      <Show when={userQuery.data}>
        <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800 sm:p-6">
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
            New ticket
          </h1>
          <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
            Ask a question, report a problem or make a request. The right people
            at India Ultimate will pick it up.
          </p>

          <Form onSubmit={submit} class="mt-6 space-y-6">
            <Field
              name="title"
              validate={required("Please give your ticket a title.")}
            >
              {(field, props) => (
                <div>
                  <label for="title" class={label}>
                    Title{" "}
                    <span class="text-red-600" aria-hidden="true">
                      *
                    </span>
                  </label>
                  <input
                    {...props}
                    id="title"
                    type="text"
                    value={field.value}
                    required
                    aria-invalid={Boolean(field.error)}
                    aria-describedby={field.error ? "title-error" : undefined}
                    placeholder="e.g. Scores not updating on the live page"
                    class={input}
                  />
                  <Show when={field.error}>
                    <p id="title-error" class={fieldError}>
                      {field.error}
                    </p>
                  </Show>
                </div>
              )}
            </Field>

            <Show when={suggestions().length > 0}>
              <section
                id="ticket-suggestions"
                aria-labelledby="suggestions-heading"
                class="rounded-xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950"
              >
                <h2
                  id="suggestions-heading"
                  class="text-sm font-semibold text-blue-900 dark:text-blue-100"
                >
                  Has someone already asked?
                </h2>
                <p class="mt-0.5 text-sm text-blue-900 dark:text-blue-200">
                  If one of these is your question, upvote it instead of opening
                  a new ticket.
                </p>
                <ul class="mt-3 space-y-2">
                  {/* Index, not For, so a vote doesn't rebuild the row (see TicketList) */}
                  <Index each={suggestions()}>
                    {ticket => (
                      <li class="relative flex items-center gap-3 rounded-lg bg-white p-2 dark:bg-gray-800">
                        <div class="relative z-10">
                          <UpvoteButton
                            ticket={ticket()}
                            userId={userQuery.data.id}
                          />
                        </div>
                        <div class="min-w-0 flex-1">
                          <A
                            href={`/tickets/${ticket().id}`}
                            class="break-words font-medium text-gray-900 after:absolute after:inset-0 hover:underline focus:outline-none focus-visible:underline dark:text-white"
                          >
                            {ticket().title}
                          </A>
                          <div class="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
                            <StatusBadge status={ticket().status} />
                            <Show when={ticket().status === "RES"}>
                              <span>See how it was answered</span>
                            </Show>
                          </div>
                        </div>
                      </li>
                    )}
                  </Index>
                </ul>
              </section>
            </Show>

            {/* Each option says whether it's chosen: modular-forms sets the
                select's value before <For> has rendered the options */}
            <div class="grid gap-6 md:grid-cols-2">
              <Field name="category">
                {(field, props) => (
                  <div>
                    <label for="category" class={label}>
                      Category
                    </label>
                    <select
                      {...props}
                      id="category"
                      value={field.value}
                      class={input}
                    >
                      <option value="">Choose a category</option>
                      <For each={CATEGORIES}>
                        {category => (
                          <option
                            value={category}
                            selected={field.value === category}
                          >
                            {category}
                          </option>
                        )}
                      </For>
                    </select>
                  </div>
                )}
              </Field>
              <Field name="priority">
                {(field, props) => (
                  <div>
                    <label for="priority" class={label}>
                      Priority
                    </label>
                    <select
                      {...props}
                      id="priority"
                      value={field.value}
                      class={input}
                    >
                      <For each={Object.entries(PRIORITIES)}>
                        {([value, priority]) => (
                          <option
                            value={value}
                            selected={field.value === value}
                          >
                            {priority.label}
                          </option>
                        )}
                      </For>
                    </select>
                  </div>
                )}
              </Field>
            </div>

            <Field
              name="description"
              validate={required("Please describe what you need help with.")}
            >
              {(field, props) => (
                <div>
                  <label for="description" class={label}>
                    Description{" "}
                    <span class="text-red-600" aria-hidden="true">
                      *
                    </span>
                  </label>
                  <textarea
                    {...props}
                    id="description"
                    rows="6"
                    value={field.value}
                    required
                    aria-invalid={Boolean(field.error)}
                    aria-describedby={
                      field.error
                        ? "description-help description-error"
                        : "description-help"
                    }
                    class={input}
                  />
                  <p
                    id="description-help"
                    class="mt-1 text-sm text-gray-600 dark:text-gray-400"
                  >
                    What happened, where, and what you expected. The more
                    detail, the faster someone can help.
                  </p>
                  <Show when={field.error}>
                    <p id="description-error" class={fieldError}>
                      {field.error}
                    </p>
                  </Show>
                </div>
              )}
            </Field>

            <Field name="is_private" type="boolean">
              {(field, props) => (
                <label
                  for="is_private"
                  class="flex cursor-pointer items-start justify-between gap-4 rounded-xl border border-gray-200 p-4 transition-colors duration-150 hover:bg-gray-50 motion-reduce:transition-none dark:border-gray-700 dark:hover:bg-gray-700/50"
                >
                  <span>
                    <span class="flex items-center gap-1.5 font-medium text-gray-900 dark:text-white">
                      <Icon
                        path={lockClosed}
                        class="h-5 w-5"
                        aria-hidden="true"
                      />
                      Keep this private
                    </span>
                    <span
                      id="is_private-help"
                      class="mt-1 block text-sm text-gray-600 dark:text-gray-400"
                    >
                      Only you and the India Ultimate team can see it. Use this
                      for personal details like phone numbers or payments.
                    </span>
                  </span>
                  <input
                    {...props}
                    id="is_private"
                    type="checkbox"
                    role="switch"
                    checked={field.value}
                    aria-describedby="is_private-help"
                    class="peer sr-only"
                  />
                  <span
                    aria-hidden="true"
                    class="mt-1 inline-flex h-7 w-12 shrink-0 items-center rounded-full bg-gray-300 transition-colors duration-150 peer-checked:bg-blue-700 peer-focus-visible:ring-4 peer-focus-visible:ring-blue-300 motion-reduce:transition-none dark:bg-gray-600 dark:peer-checked:bg-blue-600 dark:peer-focus-visible:ring-blue-800 peer-checked:[&>span]:translate-x-6"
                  >
                    <span class="ml-1 inline-block h-5 w-5 rounded-full bg-white shadow transition-transform duration-150 motion-reduce:transition-none" />
                  </span>
                </label>
              )}
            </Field>

            <Show when={error()}>
              <ErrorAlert text={error()} />
            </Show>

            <div class="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <A
                href="/tickets"
                class="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-gray-300 bg-white px-5 text-sm font-medium text-gray-900 hover:bg-gray-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-gray-200 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700"
              >
                Cancel
              </A>
              <button
                type="submit"
                id="create-ticket"
                disabled={mutation.isLoading}
                class="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-blue-700 px-5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus-visible:ring-blue-800"
              >
                {mutation.isLoading ? "Creating…" : "Create ticket"}
              </button>
            </div>
          </Form>
        </div>
      </Show>
    </div>
  );
};

export default CreateTicket;
