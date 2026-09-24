import { useNavigate } from "@solidjs/router";
import { createSignal, Show } from "solid-js";

import { useStore } from "../store";
import { getCookie } from "../utils";

export default function MergeRequest() {
  const [store] = useStore();
  const navigate = useNavigate();
  const [email, setEmail] = createSignal("");
  const [note, setNote] = createSignal("");
  const [error, setError] = createSignal();
  const [busy, setBusy] = createSignal(false);

  const keeper = () => store?.data?.email || store?.data?.username;

  const submit = async event => {
    event.preventDefault();
    setBusy(true);
    setError();
    try {
      const response = await fetch("/api/merge-accounts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
        },
        credentials: "same-origin",
        body: JSON.stringify({ email: email(), note: note() })
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data?.message || "Something went wrong");
        return;
      }
      navigate(`/merge-accounts/${data.token}`);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div class="mx-auto max-w-xl px-4 py-8">
      <h1 class="mb-4 text-2xl font-bold text-gray-900 dark:text-white">
        Merge a duplicate account into this one
      </h1>
      <div
        id="merge-request-keeper"
        class="mb-4 rounded-lg border border-blue-300 bg-blue-50 p-3 text-sm text-blue-900 dark:border-blue-700 dark:bg-blue-900 dark:text-blue-100"
      >
        <p class="font-semibold">
          You&apos;re signed in as {keeper()}. This is the account you&apos;ll
          keep.
        </p>
        <p>
          Everything from the other account — memberships, registrations,
          payments, teams — moves across, except where your account already has
          one, and the other account is then deleted. This cannot be undone. To
          keep the other account instead, sign in to it and start from there.
        </p>
      </div>
      <form onSubmit={submit} class="space-y-3">
        <label class="block text-sm text-gray-900 dark:text-white">
          The other account&apos;s email address
          <input
            id="merge-request-email"
            type="email"
            required
            class="mt-1 block w-full rounded border border-gray-300 p-2 dark:border-gray-600 dark:bg-gray-700"
            value={email()}
            onInput={e => setEmail(e.currentTarget.value)}
          />
        </label>
        <label class="block text-sm text-gray-900 dark:text-white">
          Anything our team should know (optional)
          <textarea
            id="merge-request-note"
            class="mt-1 block w-full rounded border border-gray-300 p-2 dark:border-gray-600 dark:bg-gray-700"
            value={note()}
            onInput={e => setNote(e.currentTarget.value)}
          />
        </label>
        <button
          id="merge-request-submit"
          type="submit"
          disabled={busy()}
          class="rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
        >
          Continue
        </button>
      </form>
      <Show when={error()}>
        <p id="merge-request-error" class="mt-4 text-red-600 dark:text-red-400">
          {error()}
        </p>
      </Show>
    </div>
  );
}
