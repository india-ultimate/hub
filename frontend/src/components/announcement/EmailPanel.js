import { createMutation } from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import { card, secondaryButton } from "../../committees";
import { emailAnnouncement } from "../../queries";
import ConfirmDialog from "../ConfirmDialog";

const AUDIENCES = [
  { audience: "all", label: "Send to all users", who: "every user" },
  { audience: "members", label: "Send to members", who: "all members" }
];

// Emailing a saved post: staff to everyone or the members, anyone to themselves.
const EmailPanel = props => {
  const [request, setRequest] = createSignal(null);
  const send = createMutation({ mutationFn: emailAnnouncement });
  const result = () =>
    send.data &&
    `Queued ${send.data.queued} email${send.data.queued === 1 ? "" : "s"}.`;

  const ask = ({ audience, label, who }) =>
    setRequest({
      title: label,
      message: `Email "${props.title}" to ${who}? This can't be undone.`,
      confirm: label,
      run: () => send.mutate({ slug: props.slug, audience })
    });

  return (
    <section aria-labelledby="email-heading" class={`${card} space-y-3`}>
      <h2
        id="email-heading"
        class="text-lg font-semibold text-gray-900 dark:text-white"
      >
        Email
      </h2>
      <div class="flex flex-wrap gap-2">
        <Show when={props.isStaff && props.published}>
          <For each={AUDIENCES}>
            {a => (
              <button
                type="button"
                class={secondaryButton}
                disabled={send.isLoading}
                onClick={() => ask(a)}
              >
                {a.label}
              </button>
            )}
          </For>
        </Show>
        <button
          type="button"
          class={secondaryButton}
          disabled={send.isLoading}
          onClick={() => send.mutate({ slug: props.slug, audience: "test" })}
        >
          Send a test to me
        </button>
      </div>
      <p role="status" class="text-sm text-green-700 dark:text-green-400">
        {result()}
      </p>
      <Show when={send.error}>
        <p role="alert" class="text-sm text-red-700 dark:text-red-400">
          {send.error.message}
        </p>
      </Show>
      <ConfirmDialog request={request} close={() => setRequest(null)} />
    </section>
  );
};

export default EmailPanel;
