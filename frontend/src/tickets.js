import clsx from "clsx";
import { Show } from "solid-js";

export const STATUSES = {
  OPN: {
    label: "Open",
    badge: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    dot: "bg-blue-600 dark:bg-blue-300"
  },
  PRG: {
    label: "In progress",
    badge: "bg-amber-100 text-amber-900 dark:bg-amber-900 dark:text-amber-100",
    dot: "bg-amber-500"
  },
  RES: {
    label: "Resolved",
    badge: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    dot: "bg-green-600 dark:bg-green-300"
  }
};

export const PRIORITIES = {
  LOW: {
    label: "Low priority",
    badge: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200"
  },
  MED: {
    label: "Medium priority",
    badge: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200"
  },
  HIG: {
    label: "High priority",
    badge:
      "bg-orange-100 text-orange-900 dark:bg-orange-900 dark:text-orange-100"
  },
  URG: {
    label: "Urgent",
    badge: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100"
  }
};

export const CATEGORIES = [
  "Account",
  "Competitions",
  "Subscription",
  "Tournament",
  "Payment",
  "Tech",
  "Other"
];

const badge =
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium";

export const StatusBadge = props => {
  const status = () => STATUSES[props.status];
  return (
    <span class={clsx(badge, status()?.badge ?? "bg-gray-100 text-gray-800")}>
      <span
        class={clsx("h-1.5 w-1.5 rounded-full", status()?.dot ?? "bg-gray-500")}
        aria-hidden="true"
      />
      {status()?.label ?? props.status}
    </span>
  );
};

export const PriorityBadge = props => (
  <span class={clsx(badge, PRIORITIES[props.priority]?.badge)}>
    {PRIORITIES[props.priority]?.label ?? props.priority}
  </span>
);

export const CategoryChip = props => (
  <Show when={props.category}>
    <span
      class={clsx(
        badge,
        "border border-gray-300 text-gray-700 dark:border-gray-600 dark:text-gray-300"
      )}
    >
      {props.category}
    </span>
  </Show>
);

// "3 Oct", or "3 Oct 2025" for another year
export const formatDate = iso => {
  const date = new Date(iso);
  const otherYear = date.getFullYear() !== new Date().getFullYear();
  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    ...(otherYear && { year: "numeric" })
  });
};

export const formatDateTime = iso =>
  new Date(iso).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
