import { useQueryClient } from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import { relationChoices } from "../../constants";
import { saveGuardian } from "../../queries";
import Modal from "../Modal";

const input =
  "block min-h-[44px] w-full rounded-lg border border-gray-300 bg-white px-3 text-base text-gray-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600 dark:border-gray-500 dark:bg-gray-700 dark:text-white";

const Labelled = props => (
  <label class="block text-sm font-medium">
    {props.label}
    <div class="mt-1">{props.children}</div>
  </label>
);

// Replaces a minor's guardian; the server emails the new guardian a link.
const ChangeGuardian = props => {
  const queryClient = useQueryClient();
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal("");
  let dialog;

  const submit = async e => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError("");
    try {
      await saveGuardian(props.playerId, data);
      await queryClient.invalidateQueries({
        queryKey: ["guardian", props.playerId]
      });
      dialog.close();
      props.onSaved(`Link sent to ${data.email.trim()}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      ref={el => {
        dialog = el;
        props.ref?.(el);
      }}
      title={props.guardian ? "Change guardian" : "Add guardian"}
      fullWidth
      staticBackdrop
    >
      <form onSubmit={submit} class="flex flex-col gap-3">
        <Labelled label="Guardian's first name">
          <input name="first_name" required autocomplete="off" class={input} />
        </Labelled>
        <Labelled label="Guardian's last name">
          <input name="last_name" required autocomplete="off" class={input} />
        </Labelled>
        <Labelled label="Guardian's email">
          <input
            name="email"
            type="email"
            required
            autocomplete="off"
            placeholder="guardian.name@email.com"
            class={input}
          />
        </Labelled>
        <Labelled label="Guardian's phone number">
          <input
            name="phone"
            type="tel"
            required
            autocomplete="off"
            pattern="\+\d{8,}"
            title="Enter a phone number along with the country code, like +919998887776"
            placeholder="+919998887776"
            class={input}
          />
        </Labelled>
        <Labelled label="Guardian's relation">
          <select name="relation" required class={input}>
            <option value="" disabled selected>
              Mother / Father / Legal Guardian?
            </option>
            <For each={relationChoices}>
              {c => <option value={c.value}>{c.label}</option>}
            </For>
          </select>
        </Labelled>
        <Show when={error()}>
          <p
            role="alert"
            class="text-sm font-semibold text-red-700 dark:text-red-400"
          >
            {error()}
          </p>
        </Show>
        <p class="text-sm text-gray-600 dark:text-gray-300">
          We email the new guardian a link to sign in and sign.
        </p>
        <button
          type="submit"
          disabled={busy()}
          class="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 disabled:opacity-50 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus-visible:ring-blue-800"
        >
          {busy() ? "Saving…" : "Save"}
        </button>
      </form>
    </Modal>
  );
};

export default ChangeGuardian;
