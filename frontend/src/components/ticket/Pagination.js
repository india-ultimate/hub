import clsx from "clsx";
import { For, Show } from "solid-js";

// The first, last and current page with its neighbours; null marks a gap.
const pageItems = (current, total) => {
  const pages = [...new Set([1, current - 1, current, current + 1, total])]
    .filter(p => p >= 1 && p <= total)
    .sort((a, b) => a - b);
  return pages.flatMap((p, i) =>
    i > 0 && p - pages[i - 1] > 1 ? [null, p] : [p]
  );
};

const button =
  "inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg px-3 text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transition-none dark:focus-visible:ring-blue-800";
const idle =
  "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700";

const Pagination = props => (
  <Show when={props.pages > 1}>
    <nav aria-label="Pages" class="flex items-center justify-center gap-1 pt-2">
      <button
        type="button"
        class={clsx(button, idle)}
        disabled={props.page <= 1}
        onClick={() => props.onChange(props.page - 1)}
      >
        ‹ Prev
      </button>
      <span class="px-2 text-sm text-gray-600 dark:text-gray-400 sm:hidden">
        Page {props.page} of {props.pages}
      </span>
      <For each={pageItems(props.page, props.pages)}>
        {p =>
          p === null ? (
            <span
              class="hidden px-1 text-gray-500 sm:inline"
              aria-hidden="true"
            >
              …
            </span>
          ) : (
            <button
              type="button"
              id={`page-${p}`}
              aria-current={p === props.page ? "page" : undefined}
              onClick={() => props.onChange(p)}
              class={clsx(
                button,
                "hidden sm:inline-flex",
                p === props.page
                  ? "bg-blue-700 text-white dark:bg-blue-600"
                  : idle
              )}
            >
              {p}
            </button>
          )
        }
      </For>
      <button
        type="button"
        class={clsx(button, idle)}
        disabled={props.page >= props.pages}
        onClick={() => props.onChange(props.page + 1)}
      >
        Next ›
      </button>
    </nav>
  </Show>
);

export default Pagination;
