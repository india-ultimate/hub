import { Icon } from "solid-heroicons";
import { chevronRight } from "solid-heroicons/solid";
import { For, Show } from "solid-js";

const Breadcrumbs = props => {
  return (
    <nav class="flex mb-5" aria-label="Breadcrumb">
      <ol class="inline-flex items-center space-x-1 md:space-x-3">
        <For each={props.pageList}>
          {(page, i) => (
            <Show
              when={i() > 0}
              fallback={
                <li class="inline-flex items-center">
                  <a
                    href={page.url}
                    class="inline-flex items-center text-sm font-medium text-gray-900 bg-white border border-gray-300 hover:bg-gray-100 rounded-full px-3 py-1 text-center dark:bg-gray-800 dark:text-white dark:border-gray-600 dark:hover:bg-gray-700 dark:hover:border-gray-600"
                  >
                    <Icon class="w-3 h-3 mr-2.5" path={props.icon} />
                    {page.name}
                  </a>
                </li>
              }
            >
              <li>
                <div class="flex items-center">
                  <Icon
                    class="w-3 h-3 text-gray-400 mx-1"
                    path={chevronRight}
                  />
                  <Show
                    when={page.url}
                    fallback={
                      <span class="ml-1 text-sm font-medium text-gray-500 md:ml-2 dark:text-gray-400">
                        {page.name}
                      </span>
                    }
                  >
                    <a
                      href={page.url}
                      class="ml-1 text-sm font-medium text-gray-900 bg-white border border-gray-300 hover:bg-gray-100 rounded-full px-3 py-1 text-center dark:bg-gray-800 dark:text-white dark:border-gray-600 dark:hover:bg-gray-700 dark:hover:border-gray-600"
                    >
                      {page.name}
                    </a>
                  </Show>
                </div>
              </li>
            </Show>
          )}
        </For>
      </ol>
    </nav>
  );
};

export default Breadcrumbs;
