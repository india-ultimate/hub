import { useQueryClient } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { exclamationTriangle } from "solid-heroicons/outline";
import { createSignal, For, Show } from "solid-js";

import { relationChoices } from "../../constants";
import { saveGuardian } from "../../queries";
import { useStore } from "../../store";
import { fetchUserData } from "../../utils";
import Modal from "../Modal";

const input =
  "block min-h-[44px] w-full rounded-lg border border-gray-300 bg-white px-3 text-base text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600 placeholder:text-gray-400 dark:border-gray-500 dark:bg-gray-700 dark:text-white";

// Older records hold a bare 10-digit number; the form wants the country code.
const withCountryCode = phone =>
  /^\d{10}$/.test(phone) ? `+91${phone}` : phone;

const Labelled = props => (
  <label class="block text-sm font-medium">
    {props.label}
    <div class="mt-1">{props.children}</div>
    <Show when={props.hint}>
      <span class="mt-1 block text-sm font-normal text-gray-700 dark:text-gray-300">
        {props.hint}
      </span>
    </Show>
  </label>
);

// Replaces a minor's guardian; the server emails the new guardian a link.
const ChangeGuardian = props => {
  const queryClient = useQueryClient();
  const [, { userFetchSuccess }] = useStore();
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal("");
  // A new form each time the dialog opens, so it starts prefilled.
  const [version, setVersion] = createSignal(1);
  const emailProblem = () => /email|account|18 or older/i.test(error());
  let dialog;
  let alertEl;

  const submit = async e => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    const email = data.email.trim();
    const unchanged =
      email.toLowerCase() === props.guardian?.email?.toLowerCase();
    setBusy(true);
    setError("");
    try {
      await saveGuardian(props.playerId, data);
      await queryClient.invalidateQueries({
        queryKey: ["guardian", props.playerId]
      });
      await fetchUserData(userFetchSuccess, () => {});
      dialog.close();
      props.onSaved(unchanged ? "Guardian updated" : `Link sent to ${email}`);
    } catch (err) {
      setError(err.message);
      queueMicrotask(() => alertEl?.focus());
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      ref={el => {
        dialog = el;
        const open = el.showModal;
        el.showModal = () => {
          setError("");
          setVersion(v => v + 1);
          open();
        };
        props.ref?.(el);
      }}
      title={
        <span class="font-semibold text-gray-900 dark:text-white">
          {props.guardian ? "Change guardian" : "Add guardian"}
        </span>
      }
      fullWidth
      staticBackdrop
    >
      <For each={[version()]}>
        {() => (
          <form onSubmit={submit} class="flex flex-col gap-3">
            <Labelled label="Guardian's first name">
              <input
                name="first_name"
                required
                autocomplete="off"
                value={props.guardian?.first_name ?? ""}
                class={input}
              />
            </Labelled>
            <Labelled label="Guardian's last name">
              <input
                name="last_name"
                required
                autocomplete="off"
                value={props.guardian?.last_name ?? ""}
                class={input}
              />
            </Labelled>
            <Labelled label="Guardian's email">
              <input
                name="email"
                type="email"
                required
                autocomplete="off"
                placeholder="name@example.com"
                value={props.guardian?.email ?? ""}
                aria-invalid={emailProblem() ? "true" : undefined}
                aria-describedby={emailProblem() ? "guardian-error" : undefined}
                class={input}
              />
            </Labelled>
            <Labelled
              label="Guardian's phone number"
              hint="Include the country code, like +91."
            >
              <input
                name="phone"
                type="tel"
                required
                autocomplete="off"
                pattern="\+\d{8,}"
                title="Enter a phone number along with the country code, like +919998887776"
                placeholder="+919998887776"
                value={withCountryCode(props.guardian?.phone ?? "")}
                class={input}
              />
            </Labelled>
            <Labelled label="Guardian's relation">
              <select name="relation" required class={input}>
                <option value="" disabled selected={!props.guardian?.relation}>
                  Mother / Father / Legal Guardian?
                </option>
                <For each={relationChoices}>
                  {c => (
                    <option
                      value={c.value}
                      selected={props.guardian?.relation === c.value}
                    >
                      {c.label}
                    </option>
                  )}
                </For>
              </select>
            </Labelled>
            <Show when={error()}>
              <p
                id="guardian-error"
                ref={alertEl}
                tabindex="-1"
                role="alert"
                class="flex items-start gap-1.5 text-sm font-semibold text-red-700 focus:outline-none dark:text-red-400"
              >
                <Icon
                  path={exclamationTriangle}
                  class="mt-0.5 h-4 w-4 flex-none"
                  aria-hidden="true"
                />
                <span>{error()}</span>
              </p>
            </Show>
            <p class="text-sm text-gray-700 dark:text-gray-200">
              We will email them a link to sign the waiver. If there was a
              guardian before, we tell them it changed.
            </p>
            <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => dialog.close()}
                class="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-gray-300 bg-white px-4 text-sm font-semibold text-gray-900 hover:bg-gray-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 dark:border-gray-500 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-800 dark:focus-visible:ring-blue-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={busy()}
                class="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 disabled:opacity-50 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus-visible:ring-blue-800"
              >
                {busy() ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        )}
      </For>
    </Modal>
  );
};

export default ChangeGuardian;
