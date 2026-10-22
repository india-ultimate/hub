import { A, useParams } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { checkCircle, lockClosed } from "solid-heroicons/outline";
import {
  createResource,
  createSignal,
  For,
  Match,
  Show,
  Switch
} from "solid-js";

import { Spinner } from "../../icons";
import { inr } from "../../money";
import { openCheckout } from "../../razorpay";
import Error from "../alerts/Error";

const loadOrder = async orderId => {
  const response = await fetch(
    `/api/transactions/razorpay/orders/${encodeURIComponent(orderId)}`,
    { credentials: "same-origin" }
  );
  if (response.ok) return { order: await response.json() };
  if (response.status === 404 || response.status === 409) {
    return {
      problem: (await response.json()).message,
      status: response.status
    };
  }
  return { problem: "We couldn't load this order. Please try again." };
};

// Razorpay gets only its own options, not what the page shows.
const checkoutOptions = order => {
  const { issues_receipt: _issuesReceipt, lines: _lines, ...options } = order;
  return options;
};

const muted = "text-sm text-gray-500 dark:text-gray-400";

const Back = () => (
  <A
    href="/dashboard"
    class="inline-flex min-h-[44px] items-center text-sm font-medium text-blue-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-blue-400"
  >
    Go to your dashboard
  </A>
);

// A long roster folds away, as on the payment account page.
const People = props => {
  const list = () => (
    <For each={props.people}>{person => <p class={muted}>{person}</p>}</For>
  );
  return (
    <Show when={props.people.length > 3} fallback={list()}>
      <details class="mt-1">
        <summary class="cursor-pointer text-sm text-blue-700 dark:text-blue-400">
          {props.people.length} people
        </summary>
        {list()}
      </details>
    </Show>
  );
};

const Line = props => (
  <li class="flex justify-between gap-4 py-4">
    <div class="min-w-0">
      <p class="font-medium text-gray-900 dark:text-white">
        {props.line.particulars}
      </p>
      <People people={props.line.people} />
      <Show when={props.line.quantity > 1 && props.line.rate !== null}>
        <p class="mt-1 font-mono text-xs text-gray-500 dark:text-gray-400">
          {props.line.quantity} × {inr(props.line.rate)}
        </p>
      </Show>
    </div>
    <p class="whitespace-nowrap font-mono tabular-nums text-gray-900 dark:text-white">
      {inr(props.line.amount)}
    </p>
  </li>
);

const PayOrder = () => {
  const params = useParams();
  const [loaded] = createResource(() => params.orderId, loadOrder);
  const [paying, setPaying] = createSignal(false);
  const [paid, setPaid] = createSignal(false);
  const [error, setError] = createSignal("");
  // Once Razorpay has taken the money, never offer Pay again.
  const [taken, setTaken] = createSignal(false);

  const pay = order => {
    setError("");
    setPaying(true);
    if (!window.Razorpay) {
      setPaying(false);
      setError("Razorpay failed to load. Check your connection and retry.");
      return;
    }
    openCheckout(checkoutOptions(order), {
      onPaid: () => setTaken(true),
      onSuccess: () => setPaid(true),
      onFailure: message => {
        setError(message);
        if (!taken()) setPaying(false);
      },
      onUnconfirmed: message => setError(message),
      onDismiss: () => setPaying(false)
    });
  };

  return (
    <div class="mx-auto max-w-lg py-6 sm:py-10">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
        Pay your order
      </h1>
      <Switch>
        <Match when={loaded.loading}>
          <div class="mt-6">
            <Spinner />
          </div>
        </Match>
        <Match when={loaded()?.problem}>
          <div class="mt-5">
            <Error text={loaded().problem} />
            <Show when={loaded().status === 409}>
              <p class="mb-2 text-sm text-gray-600 dark:text-gray-300">
                Nothing more to pay. It's under Transactions on your dashboard.
              </p>
            </Show>
            <Back />
          </div>
        </Match>
        <Match when={paid()}>
          <div
            role="status"
            class="mt-5 rounded-lg border border-gray-200 bg-white p-6 text-center shadow-sm dark:border-gray-700 dark:bg-gray-800"
          >
            <Icon
              path={checkCircle}
              class="mx-auto h-12 w-12 text-green-600 dark:text-green-400"
              aria-hidden="true"
            />
            <p class="mt-3 text-lg font-semibold text-gray-900 dark:text-white">
              Payment received
            </p>
            <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-gray-900 dark:text-white">
              {inr(loaded().order.amount)}
            </p>
            <p class="mt-3 text-sm text-gray-600 dark:text-gray-300">
              <Show
                when={loaded().order.issues_receipt}
                fallback="It's under Transactions on your dashboard."
              >
                Your receipt will be on your dashboard shortly.
              </Show>
            </p>
            <Back />
          </div>
        </Match>
        <Match when={loaded()?.order}>
          {order => (
            <>
              <p class={`mt-1 ${muted}`}>Paying {order().name}</p>
              <section
                aria-labelledby="order-summary"
                class="mt-5 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-800"
              >
                <header class="flex items-baseline justify-between gap-3 border-b border-gray-200 bg-gray-50 px-5 py-3 dark:border-gray-700 dark:bg-gray-700">
                  <h2
                    id="order-summary"
                    class="text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-300"
                  >
                    Order summary
                  </h2>
                  <span class="truncate font-mono text-xs text-gray-500 dark:text-gray-400">
                    {order().order_id}
                  </span>
                </header>
                <ul class="divide-y divide-gray-200 px-5 dark:divide-gray-700">
                  <For each={order().lines}>{line => <Line line={line} />}</For>
                </ul>
                <div class="mx-5 flex items-baseline justify-between border-t-2 border-gray-900 py-4 dark:border-gray-300">
                  <p class="font-semibold text-gray-900 dark:text-white">
                    Total
                  </p>
                  <p class="font-mono text-2xl font-bold tabular-nums text-gray-900 dark:text-white">
                    {inr(order().amount)}
                  </p>
                </div>
                <div class="px-5 pb-5">
                  <Show when={error()}>
                    <Error text={error()} />
                  </Show>
                  <button
                    type="button"
                    disabled={paying() || taken()}
                    aria-busy={paying()}
                    onClick={() => pay(order())}
                    class="flex min-h-[44px] w-full items-center justify-center rounded-lg bg-blue-700 px-5 py-3 text-base font-semibold text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:cursor-not-allowed disabled:bg-blue-300 disabled:text-blue-950 dark:bg-blue-600 dark:hover:bg-blue-700"
                  >
                    <Show
                      when={paying()}
                      fallback={`Pay ${inr(order().amount)}`}
                    >
                      <Spinner height={20} width={20} />
                      <span class="sr-only">Paying</span>
                    </Show>
                  </button>
                  <p class="mt-3 flex items-center justify-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                    <Icon
                      path={lockClosed}
                      class="h-4 w-4"
                      aria-hidden="true"
                    />
                    Paid securely through Razorpay
                  </p>
                </div>
              </section>
              <div class="mt-2 text-center">
                <Back />
              </div>
            </>
          )}
        </Match>
      </Switch>
    </div>
  );
};

export default PayOrder;
