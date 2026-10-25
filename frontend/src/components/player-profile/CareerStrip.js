import { For, Show } from "solid-js";

import { careerTotals } from "../../playerLinks";

const Tile = props => (
  <div
    data-tile={props.id}
    class={`rounded-xl p-2 text-center md:p-4 ${props.bg}`}
  >
    <div
      class={`text-2xl font-bold md:text-3xl ${props.text ?? "text-gray-900 dark:text-white"}`}
    >
      {props.value}
    </div>
    <div class="text-xs uppercase tracking-wide">{props.label}</div>
  </div>
);

const DESKTOP_COLS = {
  1: "md:grid-cols-1",
  2: "md:grid-cols-2",
  3: "md:grid-cols-3",
  4: "md:grid-cols-4",
  5: "md:grid-cols-5"
};

const CareerStrip = props => {
  const totals = () => careerTotals(props.tournaments);
  const tracked = () => totals().tracked;
  const mvp = () => totals().mvp;
  const msp = () => totals().msp;
  const play = () => [
    ["Goals", totals().goals],
    ["Assists", totals().assists],
    ["Blocks", totals().blocks]
  ];

  const caption = () =>
    `Goals, assists and blocks across ${tracked()} ${tracked() === 1 ? "tournament" : "tournaments"} with stats`;
  const awards = () => (mvp() > 0 ? 1 : 0) + (msp() > 0 ? 1 : 0);
  const awardSpan = () => (awards() === 1 ? "col-span-6" : "col-span-3");
  const columns = () => (tracked() ? 3 : 0) + awards();

  return (
    <Show when={tracked() || mvp() > 0 || msp() > 0}>
      <div
        class={`mt-5 grid grid-cols-6 gap-2 md:gap-4 ${DESKTOP_COLS[columns()]}`}
      >
        <Show when={tracked()}>
          <For each={play()}>
            {([label, value]) => (
              <div class="col-span-2 md:col-span-1">
                <Tile
                  id={label.toLowerCase()}
                  label={label}
                  value={value}
                  bg="bg-gray-50 dark:bg-gray-800"
                />
              </div>
            )}
          </For>
          <p class="col-span-6 text-center text-xs text-gray-500 dark:text-gray-400 md:hidden">
            {caption()}
          </p>
        </Show>
        <Show when={mvp() > 0}>
          <div class={`${awardSpan()} md:col-span-1`}>
            <Tile
              id="mvp"
              label="MVP"
              value={mvp()}
              bg="bg-yellow-50 dark:bg-gray-800"
              text="text-yellow-700 dark:text-yellow-300"
            />
          </div>
        </Show>
        <Show when={msp() > 0}>
          <div class={`${awardSpan()} md:col-span-1`}>
            <Tile
              id="msp"
              label="MSP"
              value={msp()}
              bg="bg-green-50 dark:bg-gray-800"
              text="text-green-700 dark:text-green-300"
            />
          </div>
        </Show>
      </div>
      <Show when={tracked()}>
        <p class="mt-1.5 hidden text-center text-xs text-gray-500 dark:text-gray-400 md:block">
          {caption()}
        </p>
      </Show>
    </Show>
  );
};

export default CareerStrip;
