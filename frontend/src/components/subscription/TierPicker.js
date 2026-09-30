import { Icon } from "solid-heroicons";
import { check, checkCircle, xMark } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import RazorpayPayment from "../RazorpayPayment";

const rupees = paise => (paise / 100).toLocaleString("en-IN");

// The tier selected to start with, and the one a granted tier stands in for.
const DEFAULT_TIER = "regular";

// A feature line starting with "-" is something the tier does not include.
const Feature = props => {
  const excluded = () => props.text.startsWith("-");
  return (
    <li
      class="flex gap-2"
      classList={{
        "text-gray-500 dark:text-gray-400": excluded(),
        "text-gray-700 dark:text-gray-300": !excluded()
      }}
    >
      <Icon
        path={excluded() ? xMark : check}
        class={`mt-0.5 h-4 w-4 shrink-0 ${
          excluded() ? "text-gray-400" : "text-blue-600 dark:text-blue-400"
        }`}
        aria-hidden="true"
      />
      <span>
        {excluded() ? props.text.replace(/^-\s*/, "") : props.text}
        <Show when={excluded()}>
          <span class="sr-only"> (not included)</span>
        </Show>
      </span>
    </li>
  );
};

const TierCard = props => {
  const plan = () => props.plan;
  const disabled = () => !plan().available_to_player;
  return (
    <label
      class="relative flex flex-col rounded-2xl border bg-white p-6 transition-shadow duration-200 focus-within:ring-2 focus-within:ring-blue-500 dark:bg-gray-800"
      classList={{
        "cursor-pointer hover:shadow-lg": !disabled(),
        "cursor-not-allowed opacity-60": disabled(),
        "border-blue-600 ring-2 ring-blue-600 shadow-lg": props.selected,
        "border-gray-200 dark:border-gray-700": !props.selected
      }}
    >
      <input
        type="radio"
        name="subscription-tier"
        class="sr-only"
        value={plan().slug}
        checked={props.selected}
        disabled={disabled()}
        onChange={() => props.onSelect(plan().slug)}
      />
      {/* Only the selection is highlighted; no tier is pushed over another. */}
      <Show when={props.selected || plan().granted}>
        <span
          class="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold"
          classList={{
            "bg-blue-600 text-white": props.selected,
            "bg-blue-100 text-blue-800 dark:bg-gray-700 dark:text-blue-300":
              !props.selected
          }}
        >
          {plan().granted ? "Approved for you" : "Selected"}
        </span>
      </Show>

      <div class="flex items-start justify-between gap-2">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
          {plan().name}
        </h3>
        <Icon
          path={checkCircle}
          class={`h-6 w-6 shrink-0 transition-colors duration-200 ${
            props.selected
              ? "text-blue-600"
              : "text-gray-200 dark:text-gray-600"
          }`}
          aria-hidden="true"
        />
      </div>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        {plan().description}
      </p>

      <p class="mt-5 flex items-baseline gap-1">
        <span class="text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
          ₹{rupees(plan().amount)}
        </span>
        <span class="text-sm text-gray-500 dark:text-gray-400">/ season</span>
      </p>
      <Show when={plan().upgrade_amount}>
        <p class="mt-1 text-sm font-medium text-blue-700 dark:text-blue-400">
          Upgrade for ₹{rupees(plan().upgrade_amount)}
        </p>
      </Show>

      <ul class="mt-6 space-y-3 text-sm">
        <For each={plan().features}>{text => <Feature text={text} />}</For>
      </ul>

      <Show when={disabled()}>
        <p class="mt-auto pt-6 text-sm font-medium text-gray-500 dark:text-gray-400">
          {props.held
            ? "Your current tier"
            : "Not available for you this season"}
        </p>
      </Show>
    </label>
  );
};

/**
 * The tiers as a three-column comparison, dearest first so Patron is seen
 * first. Regular starts selected; a granted tier (Discounted) takes its place
 * and its selection. A grant-only tier the player has no grant for is never
 * shown.
 */
const TierPicker = props => {
  const plans = () => props.plans ?? [];
  const granted = () => plans().find(p => p.requires_grant && p.granted);
  const defaultSlug = () => granted()?.slug ?? DEFAULT_TIER;

  const lineup = () =>
    plans()
      .filter(p =>
        p.requires_grant ? p.granted : !(granted() && p.slug === DEFAULT_TIER)
      )
      .sort((a, b) => b.amount - a.amount);

  const [selected, setSelected] = createSignal();

  // Start on the tier a link asked for, else the default tier, else the
  // first one they can buy, and move off a tier that stops being buyable
  // (after a purchase, say).
  createEffect(() => {
    const buyable = lineup().filter(p => p.available_to_player);
    if (buyable.some(p => p.slug === selected())) return;
    setSelected(
      (
        buyable.find(p => p.slug === props.tier) ??
        buyable.find(p => p.slug === defaultSlug()) ??
        buyable[0]
      )?.slug
    );
  });

  const selectedPlan = () => lineup().find(p => p.slug === selected());

  return (
    <div>
      <div
        role="radiogroup"
        aria-label="Subscription tier"
        class="mt-8 grid gap-6 md:grid-cols-3 md:items-stretch"
      >
        <For each={lineup()}>
          {plan => (
            <TierCard
              plan={plan}
              selected={plan.slug === selected()}
              held={props.heldSlug === plan.slug}
              onSelect={setSelected}
            />
          )}
        </For>
      </div>

      <Show keyed when={selectedPlan()}>
        {plan => (
          <div class="mt-8 flex flex-col items-center gap-3 text-center">
            <p class="text-sm text-gray-500 dark:text-gray-400">
              <span class="font-semibold text-gray-900 dark:text-white">
                {plan.name}
              </span>{" "}
              for {props.season?.name}
            </p>
            <RazorpayPayment
              large
              disabled={props.disabled}
              season={props.season}
              items={[{ player_id: props.playerId, plan_type: plan.slug }]}
              buttonText={
                plan.upgrade_amount
                  ? `Upgrade from ${plan.upgrade_from} — pay ₹ ${rupees(
                      plan.upgrade_amount
                    )}`
                  : `Pay ₹ ${rupees(plan.amount)}`
              }
              setStatus={props.setStatus}
              successCallback={props.onPaid}
            />
          </div>
        )}
      </Show>
    </div>
  );
};

export default TierPicker;
