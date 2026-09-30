import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { check } from "solid-heroicons/solid";
import { children, Show } from "solid-js";

// One numbered step. Done steps collapse to their title line; the current
// one is outlined in blue; locked ones still show their contents.
const Step = props => {
  const done = () => props.step.state === "done";
  const current = () => props.step.state === "current";
  const titleId = () => `step-${props.step.key}`;
  // Resolved once: reading props.children in Show's condition would build
  // a second, never-attached copy of the contents whose effects still run.
  const content = children(() => props.children);
  return (
    <section
      aria-labelledby={titleId()}
      class={clsx(
        "mb-2 rounded-xl border bg-white dark:bg-gray-900",
        current()
          ? "border-blue-700 ring-1 ring-inset ring-blue-700 dark:border-blue-500 dark:ring-blue-500"
          : "border-gray-200 dark:border-gray-700"
      )}
    >
      <div class="flex items-center gap-3 px-3 py-3">
        <span
          class={clsx(
            "flex h-7 w-7 flex-none items-center justify-center rounded-full text-sm font-bold tabular-nums text-white",
            done()
              ? "bg-green-700 dark:bg-green-600"
              : current()
              ? "bg-blue-700 dark:bg-blue-600"
              : "bg-gray-400 dark:bg-gray-600"
          )}
          aria-hidden="true"
        >
          <Show when={done()} fallback={props.index}>
            <Icon path={check} class="h-4 w-4" aria-hidden="true" />
          </Show>
        </span>
        <div class="min-w-0 flex-1">
          <h2
            id={titleId()}
            class="font-semibold text-gray-900 dark:text-white"
          >
            <span class="sr-only">Step {props.index}: </span>
            {props.step.title}
            <span class="sr-only">
              {" "}
              —{" "}
              {done() ? "done" : current() ? "to do now" : "not available yet"}
            </span>
          </h2>
          <Show when={props.step.detail}>
            <p class="text-xs text-gray-600 dark:text-gray-400">
              {props.step.detail}
            </p>
          </Show>
        </div>
      </div>
      <Show when={content() && !done()}>
        <div class="space-y-3 px-3 pb-3 sm:pl-[3.25rem]">{content()}</div>
      </Show>
    </section>
  );
};

export default Step;
