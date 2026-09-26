import { Icon } from "solid-heroicons";
import { check, checkCircle, xMark } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import RazorpayPayment from "../RazorpayPayment";

const rupees = paise => (paise / 100).toLocaleString("en-IN");

// The tier offered to most people, and the one a granted tier stands in for.
const RECOMMENDED = "regular";

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
        "border-gray-200 dark:border-gray-700": !props.selected,
        "order-first md:order-none md:-my-3 md:py-9": props.featured
      }}
    >
      <input
        type="radio"
        name="membership-tier"
        class="sr-only"
        value={plan().slug}
        checked={props.selected}
        disabled={disabled()}
        onChange={() => props.onSelect(plan().slug)}
      />
      <Show when={props.featured}>
        <span class="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-blue-600 px-3 py-1 text-xs font-semibold text-white">
          {plan().granted ? "Approved for you" : "Recommended"}
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
 * The tiers as a three-column comparison, cheapest to dearest. Regular sits in
 * the middle and starts selected; a granted tier (Discounted) takes its place
 * and its selection. A grant-only tier the player has no grant for is never
 * shown.
 */
const TierPicker = props => {
  const plans = () => props.plans ?? [];
  const granted = () => plans().find(p => p.requires_grant && p.granted);
  const featuredSlug = () => granted()?.slug ?? RECOMMENDED;

  const lineup = () =>
    plans()
      .filter(p =>
        p.requires_grant ? p.granted : !(granted() && p.slug === RECOMMENDED)
      )
      .sort((a, b) => a.amount - b.amount);

  const [selected, setSelected] = createSignal();

  // Start on the featured tier, or the first one they can buy, and move off
  // a tier that stops being buyable (after a purchase, say).
  createEffect(() => {
    const buyable = lineup().filter(p => p.available_to_player);
    if (buyable.some(p => p.slug === selected())) return;
    setSelected(
      (buyable.find(p => p.slug === featuredSlug()) ?? buyable[0])?.slug
    );
  });

  const selectedPlan = () => lineup().find(p => p.slug === selected());

  return (
    <div>
      <div
        role="radiogroup"
        aria-label="Membership tier"
        class="mt-8 grid gap-6 md:grid-cols-3 md:items-stretch"
      >
        <For each={lineup()}>
          {plan => (
            <TierCard
              plan={plan}
              selected={plan.slug === selected()}
              featured={plan.slug === featuredSlug()}
              held={props.heldSlug === plan.slug}
              onSelect={setSelected}
            />
          )}
        </For>
      </div>

      <Show keyed when={selectedPlan()}>
        {plan => (
          <div class="mt-6 flex flex-col items-start gap-4 rounded-2xl bg-gray-50 p-5 dark:bg-gray-800 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p class="text-sm text-gray-500 dark:text-gray-400">Selected</p>
              <p class="font-semibold text-gray-900 dark:text-white">
                {plan.name} · {props.season?.name}
              </p>
            </div>
            <RazorpayPayment
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
