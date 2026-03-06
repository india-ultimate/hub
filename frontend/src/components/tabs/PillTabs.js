import { For } from "solid-js";

const PillTabs = props => {
  return (
    <ul class="my-6 flex flex-wrap justify-center text-center text-sm font-medium text-gray-500 dark:text-gray-400">
      <For each={props.tabs}>
        {tab => (
          <li class="me-2">
            <button
              class={
                props.activeTab() === tab.id
                  ? "inline-block rounded-full bg-blue-600 px-4 py-2.5 text-white"
                  : "inline-block rounded-full bg-blue-50 px-4 py-3 text-blue-700 hover:bg-blue-100 hover:text-blue-800 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 dark:hover:text-white"
              }
              onClick={() => props.onTabChange(tab.id)}
            >
              {tab.label}
            </button>
          </li>
        )}
      </For>
    </ul>
  );
};

export default PillTabs;
