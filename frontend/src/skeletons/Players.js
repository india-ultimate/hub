import { For } from "solid-js";
const Player = () => {
  return (
    <li>
      <div class="flex items-center rounded pl-2 hover:bg-gray-100 dark:hover:bg-gray-600">
        <input
          type="checkbox"
          class="h-4 w-4 rounded border-gray-300 bg-gray-100 text-blue-600 focus:ring-2 focus:ring-blue-500 dark:border-gray-500 dark:bg-gray-600 dark:ring-offset-gray-700 dark:focus:ring-blue-600 dark:focus:ring-offset-gray-700"
        />
        <label class="ml-2 w-full rounded py-2 text-sm font-medium text-gray-900 dark:text-gray-300">
          <div class="w-full pl-3">
            <div class="mb-1.5 text-sm text-gray-500 dark:text-gray-400">
              <div class="mb-2 block h-2.5 w-48 rounded-full bg-gray-200 dark:bg-gray-700" />
            </div>
            <div class="text-xs text-blue-600 dark:text-blue-500">
              <div class="mb-2 block h-1 w-32 rounded-full bg-gray-200 dark:bg-gray-700" />
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
