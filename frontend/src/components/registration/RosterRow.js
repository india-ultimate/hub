import { A } from "@solidjs/router";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { Show } from "solid-js";

import { kindOf } from "../../reasonKinds";

// Rows the admin can't pay for yet. They get a grey background and muted
// name rather than opacity, which would take the text below AA contrast.
const GREYED = new Set(["waiting", "blocked", "limit", "timing", "progress"]);
const ROLES = {
  CAP: "Captain",
  SCAP: "Spirit captain",
  COACH: "Coach",
  ACOACH: "Assistant coach",
  MNGR: "Manager"
};

const link =
  "inline-flex min-h-[44px] flex-none items-center px-2 text-xs font-semibold text-blue-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-blue-400 dark:focus-visible:ring-blue-500";

// One player, what they're waiting on, and the one thing to do about it.
const RosterRow = props => {
  const s = () => props.entry.state;
  const player = () => props.entry.player;
  const kind = () => kindOf(s().kind);
  const greyed = () => GREYED.has(s().kind);
  const initials = () =>
    (player().name || "?")
      .split(" ")
      .filter(Boolean)
      .map(w => w[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();
  const label = () => (
    <>
      {s().action.label}
      <span class="sr-only"> — {player().name}</span>
    </>
  );
  return (
    <li
      class={clsx(
        "flex items-center gap-3 border-b border-gray-100 px-2 py-2 dark:border-gray-800",
        greyed() && "bg-gray-50 dark:bg-gray-800/50"
      )}
    >
      <span
        class="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-800 dark:bg-blue-900 dark:text-blue-200"
        aria-hidden="true"
      >
        {initials()}
      </span>
      <div class="min-w-0 flex-1">
        <p
          class={clsx(
            "flex flex-wrap items-center gap-x-2 font-medium",
            greyed()
              ? "text-gray-600 dark:text-gray-400"
              : "text-gray-900 dark:text-white"
          )}
        >
          <span class="truncate">{player().name}</span>
          <Show when={ROLES[props.entry.role]}>
            <span class="rounded bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-700 dark:bg-gray-700 dark:text-gray-300">
              {ROLES[props.entry.role]}
            </span>
          </Show>
        </p>
        <p
          class={clsx("flex items-center gap-1 text-xs", kind().tone)}
          aria-live="polite"
        >
          <Icon
            path={kind().icon}
            class="h-3.5 w-3.5 flex-none"
            aria-hidden="true"
          />
          <span>{s().text}</span>
        </p>
        {/* Tells apart two people with the same name. */}
        <p class="text-xs text-gray-600 dark:text-gray-400">
          {[player().city, player().iu_id && `IU ${player().iu_id}`]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>
      <Show when={s().action && !props.readOnly}>
        <Show
          when={s().action.href}
          fallback={
            <button
              type="button"
              class={link}
              onClick={() => props.onOp?.(s().action.op, player().id)}
            >
              {label()}
            </button>
          }
        >
          <A href={s().action.href} class={link}>
            {label()}
          </A>
        </Show>
      </Show>
    </li>
  );
};

export default RosterRow;
