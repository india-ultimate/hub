import { createSignal, For, onMount, Show } from "solid-js";

import { dangerButton, secondaryButton } from "../../committees";
import { fetchUrl, getCookie } from "../../utils";
import Accordion from "../Accordion";
import Error from "../alerts/Error";

const connectedOn = iso =>
  new Date(iso).toLocaleDateString("en-IN", { dateStyle: "medium" });

// Renders nothing until the server lists at least one app (the route is a 404
// when MCP is off).
const ConnectedApps = () => {
  const [apps, setApps] = createSignal([]);
  const [confirming, setConfirming] = createSignal(null);
  const [error, setError] = createSignal("");
  const [status, setStatus] = createSignal("");
  const [pending, setPending] = createSignal(false);
  const [loadFailed, setLoadFailed] = createSignal(false);

  const focusSoon = id =>
    queueMicrotask(() => document.getElementById(id)?.focus());

  // No section at all when nothing is connected, or when MCP is off (404).
  onMount(() =>
    fetchUrl(
      "/api/me/connected-apps",
      async response => {
        if (response.ok) setApps(await response.json());
        else if (response.status !== 404) setLoadFailed(true);
      },
      () => setLoadFailed(true)
    )
  );

  const disconnect = async app => {
    setError("");
    setStatus("");
    setPending(true);
    const response = await fetch(
      `/api/me/connected-apps/${app.application_id}`,
      {
        method: "DELETE",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
        credentials: "same-origin"
      }
    ).catch(() => null);
    setPending(false);
    if (response?.ok || response?.status === 404) {
      const rest = apps().filter(a => a.application_id !== app.application_id);
      const index = apps().findIndex(
        a => a.application_id === app.application_id
      );
      setApps(rest);
      setConfirming(null);
      setStatus(`Disconnected ${app.name}`);
      const next = rest[Math.min(index, rest.length - 1)];
      if (next) focusSoon(`connected-app-disconnect-${next.application_id}`);
      else focusSoon("connected-apps-status");
    } else {
      setError(`Could not disconnect ${app.name}. Please try again.`);
    }
  };

  return (
    <>
      <p
        id="connected-apps-status"
        tabindex="-1"
        aria-live="polite"
        class="sr-only"
      >
        {status()}
      </p>
      <Show when={loadFailed()}>
        <Error text="Your connected AI agents could not be loaded. Please try again later." />
      </Show>
      <Show when={apps().length > 0}>
        <Accordion
          group="dashboard"
          id="connected-apps"
          title="Connected AI agents"
        >
          <p class="mb-3 text-sm text-gray-600 dark:text-gray-400">
            AI agents you have allowed to use your Hub account. Disconnecting
            stops the agent straight away.
          </p>
          <ul class="divide-y divide-gray-200 dark:divide-gray-700">
            <For each={apps()}>
              {app => (
                <li class="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div class="min-w-0">
                    <p class="font-medium text-gray-900 dark:text-white">
                      {app.name}
                    </p>
                    <p class="text-sm text-gray-600 dark:text-gray-400">
                      Connected {connectedOn(app.connected_at)}
                    </p>
                    <p class="text-sm text-gray-600 dark:text-gray-400">
                      {app.scopes.join(" · ")}
                    </p>
                  </div>
                  <Show
                    when={confirming() === app.application_id}
                    fallback={
                      <button
                        type="button"
                        class={secondaryButton}
                        id={`connected-app-disconnect-${app.application_id}`}
                        aria-label={`Disconnect ${app.name}`}
                        onClick={() => {
                          setError("");
                          setConfirming(app.application_id);
                          focusSoon(
                            `connected-app-confirm-${app.application_id}`
                          );
                        }}
                      >
                        Disconnect
                      </button>
                    }
                  >
                    <div
                      role="group"
                      aria-label={`Confirm disconnecting ${app.name}`}
                      class="flex flex-wrap items-center gap-2"
                    >
                      <span class="text-sm text-gray-900 dark:text-white">
                        Disconnect {app.name}?
                      </span>
                      <button
                        type="button"
                        id={`connected-app-confirm-${app.application_id}`}
                        class={dangerButton}
                        disabled={pending()}
                        onClick={() => disconnect(app)}
                      >
                        Yes, disconnect
                      </button>
                      <button
                        type="button"
                        class={secondaryButton}
                        disabled={pending()}
                        onClick={() => {
                          setConfirming(null);
                          focusSoon(
                            `connected-app-disconnect-${app.application_id}`
                          );
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </Show>
                </li>
              )}
            </For>
          </ul>
          <Show when={error()}>
            <p role="alert" class="mt-2 text-sm text-red-700 dark:text-red-400">
              {error()}
            </p>
          </Show>
        </Accordion>
      </Show>
    </>
  );
};

export default ConnectedApps;
