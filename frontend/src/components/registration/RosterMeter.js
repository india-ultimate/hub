import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { check } from "solid-heroicons/solid";
import { Show } from "solid-js";

// ok: true green (a minimum met), false amber (short of one), else plain.
const chip = ok =>
  clsx(
    "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs tabular-nums",
    ok === false
      ? "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
      : ok
      ? "border-green-300 bg-green-50 text-green-800 dark:border-green-700 dark:bg-green-900/30 dark:text-green-300"
      : "border-gray-200 text-gray-700 dark:border-gray-700 dark:text-gray-300"
  );

// One matching's chip. In a series a max of 0 means nobody, so it's shown.
const Matching = props => {
  const met = () => props.count >= props.min;
  return (
    <span class={chip(props.min ? met() : undefined)}>
      {props.label} matching <b>{props.count}</b>
      <Show when={props.min}>
        {" "}
        · min {props.min}
        <Show when={met()}>
          <Icon path={check} class="h-3.5 w-3.5" aria-hidden="true" />
          <span class="sr-only">(met)</span>
        </Show>
      </Show>
      {props.max ? ` · max ${props.max}` : " · none allowed"}
    </span>
  );
};

// Roster totals against the series limits. Without a series there are no
// limits (all zeros), so only the count shows.
const RosterMeter = props => {
  const m = () => props.meter;
  return (
    <div class="flex flex-wrap gap-2" role="group" aria-label="Roster totals">
      <Show
        when={props.hasSeries}
        fallback={
          <span class={chip()}>
            <b>{m().total}</b> {m().total === 1 ? "player" : "players"}
          </span>
        }
      >
        <Show
          when={m().max_total}
          fallback={
            <span class={chip(false)}>Not eligible · 0 players allowed</span>
          }
        >
          <span class={chip()}>
            <b>{m().total}</b> / {m().max_total} players
          </span>
          <Matching
            label="Female"
            count={m().female_matching}
            min={m().min_female}
            max={m().max_female}
          />
          <Matching
            label="Male"
            count={m().male_matching}
            min={m().min_male}
            max={m().max_male}
          />
        </Show>
      </Show>
    </div>
  );
};

export default RosterMeter;
