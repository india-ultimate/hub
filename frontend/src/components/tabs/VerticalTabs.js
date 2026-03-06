import { For } from "solid-js";

const VerticalTabs = props => {
  return (
    <div class="md:flex">
      <ul class="flex-column mb-4 space-y-4 text-sm font-medium text-gray-500 dark:text-gray-400 md:mb-0 md:me-4 md:min-w-[20%]">
        <For each={props.tabs}>
          {tab => (
            <li>
              <button
                class={
                  props.activeTab() === tab.id
                    ? "inline-flex w-full items-center rounded-full bg-blue-600 px-4 py-2.5 text-white"
                    : "inline-flex w-full items-center rounded-full bg-blue-50 px-4 py-3 text-blue-700 hover:bg-blue-100 hover:text-blue-800 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 dark:hover:text-white"
                }
                onClick={() => props.onTabChange(tab.id)}
              >
                {tab.label}
              </button>
            </li>
          )}
        </For>
      </ul>
      <div class="w-full">{props.children}</div>
    </div>
  );
};

export default VerticalTabs;
