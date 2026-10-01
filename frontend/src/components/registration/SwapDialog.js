import clsx from "clsx";
import { createSignal, For, Show } from "solid-js";

import { swapRosterPlayer } from "../../queries";
import ReasonButton from "./ReasonButton";

const ROLES = {
  CAP: "Captain",
  SCAP: "Spirit captain",
  COACH: "Coach",
  ACOACH: "Assistant coach",
  MNGR: "Manager"
};
const first = name => (name || "").split(" ")[0];
// The server judges each row as a swap would: a full roster alone
// doesn't stop one, since the roster stays the same size.
const swappable = entry => entry.swap_state?.kind === "ready";
const option =
  "flex min-h-[44px] cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm";
const legend =
  "mb-2 text-xs font-bold uppercase tracking-wide text-gray-600 dark:text-gray-400";

// A paid place moves from one player to another: no refund, no charge.
const SwapDialog = props => {
  let dialog;
  const [out, setOut] = createSignal(null);
  const [into, setInto] = createSignal(null);
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal(null);
  const pick = (list, id) => list.find(e => e.player.id === id);
  const outEntry = () => pick(props.paid, out());
  const inEntry = () => pick(props.unpaid, into());

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await swapRosterPlayer({ ...props.args, outId: out(), inId: into() });
      props.announce(
        `Swapped ${outEntry().player.name} for ${inEntry().player.name}`,
        "success"
      );
      dialog.close();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      props.onChanged();
    }
  };

  const Choice = p => (
    <label
      class={clsx(
        option,
        p.checked
          ? "border-2 border-blue-700 bg-blue-50 dark:border-blue-400 dark:bg-blue-950/40"
          : "border-gray-200 dark:border-gray-700",
        p.disabled &&
          "cursor-not-allowed bg-gray-50 text-gray-600 dark:bg-gray-900 dark:text-gray-400"
      )}
    >
      <input
        type="radio"
        name={p.name}
        class="h-4 w-4"
        value={p.entry.player.id}
        checked={p.checked}
        disabled={p.disabled}
        onChange={() => p.onPick(p.entry.player.id)}
      />
      <span class="min-w-0 flex-1">
        <span class="block truncate font-medium">{p.entry.player.name}</span>
        <Show when={p.hint}>
          <span class="block text-xs">{p.hint}</span>
        </Show>
      </span>
    </label>
  );

  return (
    <dialog
      ref={el => {
        dialog = el;
        props.setRef(el);
      }}
      aria-label="Swap a player"
      class="m-0 h-full max-h-none w-full max-w-none p-0 backdrop:bg-gray-900/60 sm:m-auto sm:h-auto sm:max-h-[85vh] sm:max-w-xl sm:rounded-xl"
      onClose={() => {
        setOut(null);
        setInto(null);
        setError(null);
      }}
    >
      <div class="flex h-full flex-col bg-white text-gray-900 dark:bg-gray-800 dark:text-white">
        <div class="flex items-center justify-between px-4 pt-4">
          <h2 class="text-lg font-bold">Swap a player</h2>
          <button
            type="button"
            aria-label="Close"
            onClick={() => dialog.close()}
            class="inline-flex h-11 w-11 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-gray-400 dark:hover:bg-gray-700"
          >
            ✕
          </button>
        </div>
        <p class="px-4 text-xs text-gray-600 dark:text-gray-400">
          The paid place moves across: no refund, no charge.
          <Show when={props.until}> Open until {props.until}.</Show>
        </p>
        <div class="grid flex-1 gap-4 overflow-y-auto px-4 py-3 sm:grid-cols-2">
          <fieldset>
            <legend class={legend}>Take off (paid)</legend>
            <div class="space-y-2">
              <For each={props.paid}>
                {e => (
                  <Choice
                    name="swap-out"
                    entry={e}
                    checked={out() === e.player.id}
                    onPick={setOut}
                  />
                )}
              </For>
            </div>
          </fieldset>
          <fieldset>
            <legend class={legend}>Put on (not paid)</legend>
            <div class="space-y-2">
              <For each={props.unpaid}>
                {e => (
                  <Choice
                    name="swap-in"
                    entry={e}
                    checked={into() === e.player.id}
                    disabled={!swappable(e)}
                    hint={swappable(e) ? "Ready" : e.swap_state?.text}
                    onPick={setInto}
                  />
                )}
              </For>
              <Show when={!props.unpaid.length}>
                <p class="text-sm text-gray-600 dark:text-gray-400">
                  Add someone first — they'll show here once they're ready.
                </p>
              </Show>
            </div>
          </fieldset>
        </div>
        <Show when={outEntry() && inEntry()}>
          <p class="mx-4 mb-2 rounded-lg border border-gray-200 bg-gray-50 p-2 text-sm dark:border-gray-700 dark:bg-gray-900">
            {outEntry().player.name} → <strong>{inEntry().player.name}</strong>{" "}
            · ₹0
            <Show when={ROLES[outEntry().role]}>
              <span class="block text-xs text-gray-600 dark:text-gray-400">
                Their {ROLES[outEntry().role]} role isn't carried over.
              </span>
            </Show>
          </p>
        </Show>
        <Show when={error()}>
          <p
            role="alert"
            class="mx-4 mb-2 text-sm text-red-700 dark:text-red-400"
          >
            {error()}
          </p>
        </Show>
        <div class="flex items-start justify-end gap-2 border-t border-gray-200 bg-gray-50 px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
          <button
            type="button"
            onClick={() => dialog.close()}
            class="inline-flex min-h-[44px] items-center rounded-lg px-3 text-sm font-semibold text-gray-700 hover:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            Cancel
          </button>
          <ReasonButton
            label={
              outEntry() && inEntry()
                ? `Swap ${first(outEntry().player.name)} → ${first(
                    inEntry().player.name
                  )}`
                : "Swap"
            }
            busy={busy()}
            busyLabel="Swapping…"
            reason={
              outEntry() && inEntry()
                ? null
                : { kind: "waiting", text: "Pick two players" }
            }
            onClick={confirm}
          />
        </div>
      </div>
    </dialog>
  );
};

export default SwapDialog;
