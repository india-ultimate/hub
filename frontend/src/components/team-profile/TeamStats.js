import { For, Show } from "solid-js";

const COLS = {
  1: "md:grid-cols-1",
  2: "md:grid-cols-2",
  3: "md:grid-cols-3",
  4: "md:grid-cols-4",
  5: "md:grid-cols-5"
};

const GRAY = "bg-gray-50 dark:bg-gray-800";
const TEXT = "text-gray-900 dark:text-white";

const tiles = team => {
  const { record, spirit, tournaments } = team;
  const places = tournaments.map(t => t.placement).filter(Boolean);
  const titles = places.filter(p => p === 1).length;
  const podiums = places.filter(p => p <= 3).length;
  const list = [];
  if (record) {
    const { wins, losses, draws, played } = record;
    list.push({
      id: "record",
      label: draws ? "Won–lost–drawn" : "Won–lost",
      value: `${wins}–${losses}${draws ? `–${draws}` : ""}`,
      bg: GRAY,
      text: TEXT
    });
    list.push({
      id: "win-rate",
      label: "Win rate",
      value: `${Math.round((wins / played) * 100)}%`,
      bg: GRAY,
      text: TEXT
    });
  }
  if (titles)
    list.push({
      id: "titles",
      label: titles === 1 ? "Title" : "Titles",
      value: titles,
      bg: "bg-yellow-50 dark:bg-gray-800",
      text: "text-yellow-700 dark:text-yellow-300"
    });
  if (podiums)
    list.push({
      id: "podiums",
      label: podiums === 1 ? "Podium" : "Podiums",
      value: podiums,
      bg: "bg-blue-50 dark:bg-gray-800",
      text: "text-blue-700 dark:text-blue-300"
    });
  if (spirit != null)
    list.push({
      id: "spirit",
      label: "Spirit avg",
      value: spirit.toFixed(1),
      bg: "bg-green-50 dark:bg-gray-800",
      text: "text-green-700 dark:text-green-300"
    });
  return list;
};

const TeamStats = props => {
  const list = () => tiles(props.team);
  return (
    <Show when={list().length}>
      <div
        class={`mt-5 grid grid-cols-2 gap-2 md:gap-4 ${COLS[list().length]}`}
      >
        <For each={list()}>
          {tile => (
            <div
              data-tile={tile.id}
              class={`rounded-xl p-2 text-center last:odd:col-span-2 md:p-4 md:last:odd:col-span-1 ${tile.bg}`}
            >
              <div class={`text-2xl font-bold md:text-3xl ${tile.text}`}>
                {tile.value}
              </div>
              <div class="text-xs uppercase tracking-wide text-gray-700 dark:text-gray-300">
                {tile.label}
              </div>
            </div>
          )}
        </For>
      </div>
    </Show>
  );
};

export default TeamStats;
