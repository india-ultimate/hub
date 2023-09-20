import { For } from "solid-js";
const Player = () => {
  return (
    <li>
      <div class="flex items-center pl-2 rounded hover:bg-gray-100 dark:hover:bg-gray-600">
        <input
          type="checkbox"
          class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-700 dark:focus:ring-offset-gray-700 focus:ring-2 dark:bg-gray-600 dark:border-gray-500"
        />
        <label class="w-full py-2 ml-2 text-sm font-medium text-gray-900 rounded dark:text-gray-300">
          <div class="w-full pl-3">
            <div class="text-gray-500 text-sm mb-1.5 dark:text-gray-400">
              <div class="h-2.5 bg-gray-200 rounded-full dark:bg-gray-700 w-48 mb-2 block" />
            </div>
            <div class="text-xs text-blue-600 dark:text-blue-500">
              <div class="h-1 bg-gray-200 rounded-full dark:bg-gray-700 w-32 mb-2 block" />
            </div>
          </div>
        </label>
      </div>
    </li>
  );
};

const PlayersSkeleton = props => {
  const array = Array.from({ length: props.n }, (value, index) => index);
  return <For each={array}>{() => <Player />}</For>;
};

export default PlayersSkeleton;
