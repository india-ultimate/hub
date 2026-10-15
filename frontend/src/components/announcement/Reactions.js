import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { faceSmile } from "solid-heroicons/outline";
import { plusSmall } from "solid-heroicons/solid-mini";
import { createEffect, createSignal, For, onCleanup, Show } from "solid-js";

import { REACTIONS } from "../../reactions";

const byKind = Object.fromEntries(REACTIONS.map(r => [r.kind, r]));

const focusRing =
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900";
// 44px tall for fingers; shorter where there's a mouse.
const pill = clsx(
  "inline-flex min-h-[44px] items-center rounded-full motion-safe:transition-transform motion-safe:duration-150",
  focusRing
);
const sizes = {
  regular: "gap-1.5 px-3 text-sm [@media(pointer:fine)]:min-h-[36px]",
  compact: "gap-1 px-2 text-xs [@media(pointer:fine)]:min-h-[28px]"
};
const notReacted =
  "border border-gray-200 bg-white text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700";
const reacted =
  "bg-blue-50 font-semibold text-blue-700 ring-1 ring-blue-600/30 hover:bg-blue-100 dark:bg-blue-900/40 dark:text-blue-200 dark:ring-blue-400/30 dark:hover:bg-blue-900/60";

// The reactions something has, a button to add one, and whatever follows
// them in the row (props.children). Saving is the caller's: props.onToggle.
const Reactions = props => {
  const [open, setOpen] = createSignal(false);
  const [bumped, setBumped] = createSignal(null);
  let wrapper, addButton, popover;

  const size = () => sizes[props.compact ? "compact" : "regular"];
  const isReacted = kind =>
    props.reactions.some(r => r.kind === kind && r.reacted);

  const toggle = kind => {
    props.onToggle(kind, !isReacted(kind));
    setBumped(kind);
    setTimeout(() => setBumped(b => (b === kind ? null : b)), 150);
  };

  const close = () => {
    setOpen(false);
    addButton.focus();
  };

  createEffect(() => {
    if (!open()) return;
    popover?.querySelector("button")?.focus();
    const outside = e => !wrapper.contains(e.target) && close();
    document.addEventListener("pointerdown", outside);
    onCleanup(() => document.removeEventListener("pointerdown", outside));
  });

  const onKeyDown = e => {
    if (!open()) return;
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      return;
    }
    const buttons = [...popover.querySelectorAll("button")];
    const i = buttons.indexOf(document.activeElement);
    const next = {
      ArrowRight: i + 1,
      ArrowDown: i + 1,
      ArrowLeft: i - 1,
      ArrowUp: i - 1,
      Home: 0,
      End: buttons.length - 1
    }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    buttons[(next + buttons.length) % buttons.length].focus();
  };

  const label = r =>
    `${byKind[r.kind]?.label}: ${r.count}${r.reacted ? ", including you" : ""}`;

  return (
    <div>
      <div
        ref={wrapper}
        data-testid={props.testId}
        class="relative flex flex-wrap items-center gap-2 [@media(pointer:fine)]:gap-1.5"
        onKeyDown={onKeyDown}
      >
        <For each={props.reactions.filter(r => byKind[r.kind])}>
          {r => (
            <button
              type="button"
              aria-pressed={r.reacted ? "true" : "false"}
              aria-label={label(r)}
              title={label(r)}
              onClick={() => toggle(r.kind)}
              class={clsx(
                pill,
                size(),
                r.reacted ? reacted : notReacted,
                bumped() === r.kind && "motion-safe:scale-110"
              )}
            >
              <span aria-hidden="true">{byKind[r.kind].emoji}</span>
              <span aria-hidden="true">{r.count}</span>
            </button>
          )}
        </For>
        <button
          ref={addButton}
          type="button"
          aria-label={props.addLabel || "Add a reaction"}
          title={props.addLabel || "Add a reaction"}
          aria-haspopup="true"
          aria-expanded={open() ? "true" : "false"}
          onClick={() => (open() ? close() : setOpen(true))}
          class={clsx(
            pill,
            size(),
            notReacted,
            "text-gray-600 dark:text-gray-300"
          )}
        >
          <span class="relative inline-flex">
            <Icon
              path={faceSmile}
              aria-hidden="true"
              class={props.compact ? "h-4 w-4" : "h-5 w-5"}
            />
            <Icon
              path={plusSmall}
              aria-hidden="true"
              class="absolute -right-1.5 -top-1.5 h-3.5 w-3.5 rounded-full bg-white dark:bg-gray-800"
            />
          </span>
          <Show when={!props.compact && !props.reactions.length}>
            <span aria-hidden="true">React</span>
          </Show>
        </button>
        <Show when={open()}>
          <div
            ref={popover}
            role="group"
            aria-label="Reactions"
            class="absolute left-0 top-full z-10 mt-2 flex max-w-full flex-wrap gap-1 rounded-3xl border border-gray-200 bg-white p-1 shadow-lg dark:border-gray-600 dark:bg-gray-800"
          >
            <For each={REACTIONS}>
              {r => (
                <button
                  type="button"
                  aria-label={r.label}
                  title={r.label}
                  aria-pressed={isReacted(r.kind) ? "true" : "false"}
                  onClick={() => {
                    toggle(r.kind);
                    close();
                  }}
                  class={clsx(
                    "inline-flex h-11 w-11 items-center justify-center rounded-full text-xl motion-safe:transition-transform motion-safe:hover:scale-110",
                    focusRing,
                    isReacted(r.kind)
                      ? "bg-blue-50 dark:bg-blue-900/40"
                      : "hover:bg-gray-100 dark:hover:bg-gray-700"
                  )}
                >
                  <span aria-hidden="true">{r.emoji}</span>
                </button>
              )}
            </For>
          </div>
        </Show>
        {props.children}
      </div>
      <Show when={props.failed}>
        <p role="alert" class="mt-2 text-sm text-red-700 dark:text-red-400">
          Couldn't save your reaction. Try again.
        </p>
      </Show>
    </div>
  );
};

export default Reactions;
