import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { chevronRight } from "solid-heroicons/solid";
import { For, Show } from "solid-js";

const Breadcrumbs = props => {
  return (
    <nav class="mb-5 flex" aria-label="Breadcrumb">
      <ol class="inline-flex min-w-0 items-center space-x-1 md:space-x-3">
        <For each={props.pageList}>
          {(page, i) => (
            <Show
              when={i() > 0}
              fallback={
                <li class="inline-flex shrink-0 items-center">
                  <A
                    href={page.url}
                    class="inline-flex items-center whitespace-nowrap rounded-full border border-gray-300 bg-white px-3 py-1 text-center text-sm font-medium text-gray-900 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:border-gray-600 dark:hover:bg-gray-700"
                  >
                    <Icon class="mr-2.5 h-3 w-3" path={props.icon} />
                    {page.name}
                  </A>
                </li>
              }
            >
              <li class="min-w-0 last:shrink-0">
                <div class="flex min-w-0 items-center">
                  <Icon
                    class="mx-1 h-3 w-3 shrink-0 text-gray-400"
                    path={chevronRight}
                  />
                  <Show
                    when={page.url}
                    fallback={
                      <span
                        title={page.name}
                        class="ml-1 block max-w-[10rem] truncate text-sm font-medium text-gray-500 dark:text-gray-400 sm:max-w-xs md:ml-2"
                      >
                        {page.name}
                      </span>
                    }
                  >
                    <A
                      href={page.url}
                      title={page.name}
                      class="ml-1 block max-w-[10rem] truncate rounded-full border border-gray-300 bg-white px-3 py-1 text-center text-sm font-medium text-gray-900 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:border-gray-600 dark:hover:bg-gray-700 sm:max-w-xs"
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
