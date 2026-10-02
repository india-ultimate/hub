import { Show } from "solid-js";

import { inr } from "../../money";
import ReasonButton from "./ReasonButton";

// Who paying now covers and what it costs, said once. Sticky at the
// bottom on phones (the page pads for it, and index.css lifts the
// floating buttons above it), inline at the end of the roster step otherwise.
const PayBar = props => {
  const c = () => props.checkout;
  const n = () => c().ready_ids.length;
  const notes = () =>
    [
      n() > 1 && `${inr(c().per_player + c().penalty_per_player)} each`,
      n() > 0 &&
        c().penalty_per_player &&
        `Includes ${inr(c().penalty_per_player * n())} late fee`,
      c().payee_name && `Paid to ${c().payee_name}`
    ]
      .filter(Boolean)
      .join(" · ");
  return (
    <div
      data-pay-bar
      class="fixed inset-x-0 bottom-0 z-20 flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900 sm:static sm:rounded-xl sm:border sm:border-blue-200 sm:bg-blue-50 sm:dark:border-blue-800 sm:dark:bg-blue-900/20"
    >
      <div class="text-sm" aria-live="polite">
        <p class="font-semibold tabular-nums text-gray-900 dark:text-white">
          {n()} {n() === 1 ? "player" : "players"} ready
        </p>
        <Show when={notes()}>
          <p class="text-xs tabular-nums text-gray-600 dark:text-gray-400">
            {notes()}
          </p>
        </Show>
      </div>
      <ReasonButton
        label={`Pay ${inr(c().amount)}`}
        busy={props.busy}
        busyLabel={props.busyLabel || "Confirming payment…"}
        reason={props.disabledReason}
        onClick={props.onPay}
      />
    </div>
  );
};

export default PayBar;
