import { For } from "solid-js";

const PlayersList = props => {
  return (
    <ul class="w-48 text-sm font-medium text-gray-900 bg-white border border-gray-200 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white">
      <For each={props.players}>
        {player_name => (
          <li class="w-full px-4 py-2 border-b border-gray-200 rounded-t-lg dark:border-gray-600">
            {player_name}
          </li>
        )}
      </For>
    </ul>
  );
};

export default PlayersList;
