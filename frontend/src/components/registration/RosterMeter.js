import clsx from "clsx";
import { For, Show } from "solid-js";

// One gender's count. A minimum shows only while it's short, a maximum
// only once it's reached; a gender the series allows none of is left out.
const part = (n, letter, label, min, max) => {
  if (max === 0 && n === 0) return null;
  const short = n < min;
  const note = short ? `, need ${min}` : max && n >= max ? ", full" : "";
  return { n, letter, label, note, short };
};

// "3/10 · 2 F · 1 M". Without a series there are no limits, only a count.
const RosterMeter = props => {
  const m = () => props.meter;
  const parts = () =>
    [
      part(
        m().female_matching,
        "F",
        "female-matching",
        m().min_female,
        m().max_female
      ),
      part(m().male_matching, "M", "male-matching", m().min_male, m().max_male)
    ].filter(Boolean);
  return (
    <span
      data-roster-totals
      class="text-sm tabular-nums text-gray-600 dark:text-gray-400"
    >
      <Show
        when={props.hasSeries}
        fallback={`${m().total} ${m().total === 1 ? "player" : "players"}`}
      >
        <Show
          when={m().max_total}
          fallback={
            <span class="text-amber-800 dark:text-amber-300">
              Not eligible · 0 players allowed
            </span>
          }
        >
          {m().total}/{m().max_total}
          <For each={parts()}>
            {p => (
              <>
                {" · "}
                <span
                  class={clsx(
                    p.short &&
                      "font-semibold text-amber-800 dark:text-amber-300"
                  )}
                >
                  {p.n} <abbr title={p.label}>{p.letter}</abbr>
                  {p.note}
                </span>
              </>
            )}
          </For>
        </Show>
      </Show>
    </span>
  );
};

export default RosterMeter;
