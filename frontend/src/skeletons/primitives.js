import { For, Show } from "solid-js";

const bar = "bg-gray-200 dark:bg-gray-700";
const times = n => Array.from({ length: n }, (_, i) => i);

export const Loading = props => (
  <div
    class={`animate-pulse motion-reduce:animate-none ${props.class ?? ""}`}
    role={props.quiet ? undefined : "status"}
    aria-busy={props.quiet ? undefined : "true"}
  >
    <Show when={!props.quiet}>
      <span class="sr-only">{props.label}</span>
    </Show>
    {props.children}
  </div>
);

export const Bar = props => (
  <div aria-hidden="true" class={`rounded ${bar} ${props.class ?? ""}`} />
);

export const Circle = props => (
  <div aria-hidden="true" class={`rounded-full ${bar} ${props.class ?? ""}`} />
);

export const PageHeaderSkeleton = props => (
  <>
    <Show when={props.breadcrumbs}>
      <div class="mb-5 flex items-center space-x-1 md:space-x-3">
        <Bar class="h-[30px] w-32 !rounded-full" />
        <Bar class="h-4 w-24" />
      </div>
    </Show>
    <Show when={props.title !== false}>
      <div class="mb-5 flex justify-center">
        <Bar class="h-8 w-56" />
      </div>
    </Show>
    <Show when={props.subtitle}>
      <div class="flex h-5 justify-center">
        <Bar class="h-4 w-72 max-w-full" />
      </div>
    </Show>
  </>
);

export const CardGridSkeleton = props => (
  <div
    class={`grid grid-cols-1 justify-items-center gap-5 md:grid-cols-2 lg:grid-cols-3 ${
      props.class ?? ""
    }`}
  >
    <For each={times(props.count)}>
      {() => (
        <Bar class={`w-full !rounded-lg ${props.cardClass ?? "h-[174px]"}`} />
      )}
    </For>
  </div>
);

export const TableRowsSkeleton = props => (
  <For each={times(props.rows)}>
    {() => (
      <div class="flex gap-4 py-3">
        <For each={times(props.cols)}>{() => <Bar class="h-4 flex-1" />}</For>
      </div>
    )}
  </For>
);

export const ListSkeleton = props => (
  <For each={times(props.rows)}>
    {() => (
      <div class="my-5 flex items-center space-x-2 px-6">
        <Show when={props.avatar}>
          <Circle class="mr-1 h-10 w-10" />
        </Show>
        <Bar class="h-2.5 w-28 !rounded-full" />
        <Bar class="h-2.5 w-20 !rounded-full" />
      </div>
    )}
  </For>
);

export const PageSkeleton = () => (
  <Loading label="Loading page">
    <PageHeaderSkeleton breadcrumbs subtitle />
    <Bar class="mt-6 h-40 w-full !rounded-xl" />
    <Bar class="mt-5 h-40 w-full !rounded-xl" />
  </Loading>
);
