import { Icon } from "solid-heroicons";
import { envelope } from "solid-heroicons/outline";
import { createSignal, Show } from "solid-js";

import { parseLocalDate, todayIST } from "./utils";

export const card =
  "rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800 sm:p-6";
export const focusRing =
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900";
export const primaryButton = `inline-flex min-h-[44px] items-center justify-center rounded-lg bg-blue-700 px-4 text-sm font-medium text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50 ${focusRing}`;
export const secondaryButton = `inline-flex min-h-[44px] items-center justify-center rounded-lg border border-gray-300 bg-white px-4 text-sm font-medium text-gray-900 hover:bg-gray-100 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700 ${focusRing}`;
export const dangerButton = `inline-flex min-h-[44px] items-center justify-center rounded-lg bg-red-700 px-4 text-sm font-semibold text-white hover:bg-red-800 disabled:opacity-50 ${focusRing}`;
export const input =
  "block min-h-[44px] w-full rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white";

export const initials = name =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .map(word => word[0])
    .slice(0, 2)
    .join("");

const monthYear = date =>
  date.toLocaleDateString("en-IN", { month: "short", year: "numeric" });

// "Apr 2023", or "Apr 2023 – Mar 2025". The end date is the first day the
// role no longer holds, so the last month of the term is the day before.
export const termLabel = role => {
  const start = monthYear(parseLocalDate(role.start_date));
  // Open, or ended the day it began (a term never really held).
  if (!role.end_date || role.end_date <= role.start_date) return start;
  const last = parseLocalDate(role.end_date);
  last.setDate(last.getDate() - 1);
  return `${start} – ${monthYear(last)}`;
};

export const sinceLabel = role =>
  `since ${monthYear(parseLocalDate(role.start_date))}`;

// "YYYY-MM-DD" for an <input type="date"> that defaults to today (IST).
export const todayInput = () => {
  const d = todayIST();
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

export const ChairBadge = () => (
  <span class="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-200">
    Chair
  </span>
);

export const EmailLink = props => (
  <a
    href={`mailto:${props.email}`}
    class={`inline-flex min-h-[44px] items-center gap-1.5 break-all rounded text-sm text-blue-700 underline dark:text-blue-300 ${focusRing}`}
  >
    <Icon path={envelope} class="h-4 w-4 shrink-0" aria-hidden="true" />
    {props.email}
  </a>
);

export const NoOneListed = () => (
  <p class="text-sm text-gray-600 dark:text-gray-400">No one listed yet.</p>
);

// A label over a control, with the error under it.
export const Field = props => (
  <div class={props.class}>
    <label
      for={props.id}
      class="mb-1 block text-sm font-medium text-gray-900 dark:text-white"
    >
      {props.label}
    </label>
    {props.children}
    <Show when={props.error}>
      <p role="alert" class="mt-1 text-sm text-red-700 dark:text-red-400">
        {props.error}
      </p>
    </Show>
  </div>
);

// A short "Saved" that goes away by itself: [saved, flash].
export const createSaved = () => {
  const [saved, setSaved] = createSignal(false);
  let timer;
  const flash = () => {
    setSaved(true);
    clearTimeout(timer);
    timer = setTimeout(() => setSaved(false), 2500);
  };
  return [saved, flash];
};
