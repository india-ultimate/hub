import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { chevronRight } from "solid-heroicons/solid";
import { For, Show } from "solid-js";

const Breadcrumbs = props => {
  return (
    <nav class="mb-5 flex" aria-label="Breadcrumb">
      <ol class="inline-flex items-center space-x-1 md:space-x-3">
        <For each={props.pageList}>
          {(page, i) => (
            <Show
              when={i() > 0}
              fallback={
                <li class="inline-flex items-center">
                  <A
                    href={page.url}
                    class="inline-flex items-center rounded-full border border-gray-300 bg-white px-3 py-1 text-center text-sm font-medium text-gray-900 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:border-gray-600 dark:hover:bg-gray-700"
                  >
                    <Icon class="mr-2.5 h-3 w-3" path={props.icon} />
                    {page.name}
                  </A>
                </li>
              }
            >
              <li>
                <div class="flex items-center">
                  <Icon
                    class="mx-1 h-3 w-3 text-gray-400"
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
                    <A
                      href={page.url}
                      class="ml-1 rounded-full border border-gray-300 bg-white px-3 py-1 text-center text-sm font-medium text-gray-900 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:border-gray-600 dark:hover:bg-gray-700"
                    >
                      {page.name}
                    </A>
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
