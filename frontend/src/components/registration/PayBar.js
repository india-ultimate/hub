import ReasonButton from "./ReasonButton";

const inr = paise =>
  `₹${(paise / 100).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

// Who paying now covers and what it costs. Sticky at the bottom on phones
// (the page pads for it), inline at the end of the roster step otherwise.
const PayBar = props => {
  const c = () => props.checkout;
  return (
    <div class="fixed inset-x-0 bottom-0 z-20 flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900 sm:static sm:rounded-xl sm:border sm:border-blue-200 sm:bg-blue-50 sm:dark:border-blue-800 sm:dark:bg-blue-900/20">
      <div class="text-sm" aria-live="polite">
        <p class="font-semibold tabular-nums text-gray-900 dark:text-white">
          {c().ready_ids.length} ready · {inr(c().amount)}
          <span class="font-normal text-gray-600 dark:text-gray-400">
            {" "}
            ({inr(c().per_player + c().penalty_per_player)} each)
          </span>
        </p>
        <p class="text-xs tabular-nums text-gray-600 dark:text-gray-400">
          Paid to {c().payee_name}
          {c().penalty_per_player
            ? ` · includes a late fee of ${inr(
                c().penalty_per_player
              )} per player`
            : ""}
        </p>
      </div>
      <ReasonButton
        label={`Pay ${inr(c().amount)}`}
        busy={props.busy}
        busyLabel="Confirming payment…"
        reason={props.disabledReason}
        onClick={props.onPay}
      />
    </div>
  );
};

export default PayBar;
