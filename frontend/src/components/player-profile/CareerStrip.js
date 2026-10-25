import { For, Show } from "solid-js";

const sum = (list, pick) => list.reduce((total, t) => total + pick(t), 0);

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
    <div class="text-[11px] uppercase tracking-wide md:text-xs">
      {props.label}
    </div>
  </div>
);

const CareerStrip = props => {
  const tracked = () => props.tournaments.filter(t => t.stats);
  const mvp = () => sum(props.tournaments, t => t.mvp);
  const msp = () => sum(props.tournaments, t => t.msp);
  const play = () => [
    ["Goals", sum(tracked(), t => t.stats.goals)],
    ["Assists", sum(tracked(), t => t.stats.assists)],
    ["Blocks", sum(tracked(), t => t.stats.blocks)]
  ];

  return (
    <Show when={tracked().length || mvp() > 0 || msp() > 0}>
      <div class="mt-5 grid grid-cols-6 gap-2 md:grid-cols-5 md:gap-4">
        <Show when={tracked().length}>
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
        </Show>
        <Show when={mvp() > 0}>
          <div class="col-span-3 md:col-span-1">
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
          <div class="col-span-3 md:col-span-1">
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
      <Show when={tracked().length}>
        <p class="mt-1.5 text-center text-xs text-gray-500 dark:text-gray-400">
          Goals, assists and blocks across {tracked().length}{" "}
          {tracked().length === 1 ? "tournament" : "tournaments"} with stats
        </p>
      </Show>
    </Show>
  );
};

export default CareerStrip;
