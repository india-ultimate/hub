import {
  arrowPath,
  checkCircle,
  clock,
  exclamationTriangle,
  lockClosed,
  user,
  xCircle
} from "solid-heroicons/outline";

// One icon and tone per kind of reason, used everywhere on the team
// registration page. It lives outside components/ because solid-hot-loader
// passes on only a module's default export there.
export const KINDS = {
  ready: {
    icon: checkCircle,
    tone: "text-green-700 dark:text-green-400",
    strip: "bg-green-50 dark:bg-green-900/30"
  },
  done: {
    icon: checkCircle,
    tone: "text-blue-700 dark:text-blue-300",
    strip: "bg-blue-50 dark:bg-blue-900/30"
  },
  timing: {
    icon: clock,
    tone: "text-gray-600 dark:text-gray-300",
    strip: "bg-gray-100 dark:bg-gray-800"
  },
  waiting: {
    icon: user,
    tone: "text-gray-600 dark:text-gray-300",
    strip: "bg-gray-100 dark:bg-gray-800"
  },
  limit: {
    icon: lockClosed,
    tone: "text-gray-600 dark:text-gray-300",
    strip: "bg-gray-100 dark:bg-gray-800"
  },
  action: {
    icon: exclamationTriangle,
    tone: "text-amber-800 dark:text-amber-300",
    strip:
      "border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/30"
  },
  progress: {
    icon: arrowPath,
    tone: "text-blue-800 dark:text-blue-300",
    strip:
      "border border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/30"
  },
  blocked: {
    icon: xCircle,
    tone: "text-red-700 dark:text-red-400",
    strip: "bg-gray-100 dark:bg-gray-800"
  }
};

export const kindOf = kind => KINDS[kind] ?? KINDS.timing;

// The secondary button callouts and ReasonButton share. The hover is apart
// so a greyed button can leave it off and not light up.
export const actionBase =
  "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-blue-200 bg-white px-4 text-sm font-semibold text-blue-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-200 motion-reduce:transition-none dark:border-blue-800 dark:bg-gray-800 dark:text-blue-300 dark:focus-visible:ring-blue-800";
export const actionHover = "hover:bg-blue-50 dark:hover:bg-gray-700";

// Paise as whole rupees, Indian grouping: 1000000 -> "₹10,000".
export const inr = paise =>
  `₹${(paise / 100).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
