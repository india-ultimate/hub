import { For } from "solid-js";

const PlayersList = props => {
  return (
    <>
      <p class="p-2 text-xs">Payment for {props.players.length} players</p>
      <ul class="w-48 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white">
        <For each={props.players}>
          {player_name => (
            <li class="w-full rounded-t-lg border-b border-gray-200 px-4 py-2 dark:border-gray-600">
              {player_name}
            </li>
          )}
        </For>
      </ul>
    </>
  );
};

export default PlayersList;
