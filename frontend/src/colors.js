export const matchCardColors = {
  pool: [
    "blue",
    "green",
    "pink",
    "indigo",
    "purple",
    "lime",
    "red",
    "fuchsia",
    "cyan"
  ],
  cross_pool: ["yellow", "red", "fuchsia", "amber"],
  bracket: [
    ["cyan", "indigo", "sky", "rose"],
    ["cyan", "indigo", "sky", "rose"],
    ["cyan", "indigo", "sky", "rose"],
    ["cyan", "indigo", "sky", "rose"],
    ["cyan", "indigo", "sky", "rose"],
    ["cyan", "indigo", "sky", "rose"],
    ["cyan", "indigo", "sky", "rose"],
    ["cyan", "indigo", "sky", "rose"]
  ],
  position_pool: ["lime", "pink", "emerald", "teal"]
};

export const matchOutcomeColors = Object.freeze({
  win: "green",
  loss: "red",
  draw: "gray"
});

export const matchCardColorToBorderColorMap = {
  blue: "border-blue-400 dark:border-blue-400",
  green: "border-green-400 dark:border-green-400",
  pink: "border-pink-400 dark:border-pink-400",
  purple: "border-purple-400 dark:border-purple-400",
  yellow: "border-yellow-400 dark:border-yellow-400",
  red: "border-red-400 dark:border-red-400",
  fuchsia: "border-fuchsia-400 dark:border-fuchsia-400",
  lime: "border-lime-400 dark:border-lime-400",
  emerald: "border-emerald-400 dark:border-emerald-400",
  cyan: "border-cyan-400 dark:border-cyan-400",
  indigo: "border-indigo-400 dark:border-indigo-400",
  sky: "border-sky-400 dark:border-sky-400",
  gray: "border-gray-400 dark:border-gray-400",
  teal: "border-teal-400 dark:border-teal-400",
  amber: "border-amber-400 dark:border-amber-400",
  rose: "border-rose-400 dark:border-rose-400"
};

export const matchCardColorToRingColorMap = {
  blue: "ring-blue-500 dark:ring-blue-400",
  green: "ring-green-500 dark:ring-green-400",
  pink: "ring-pink-500 dark:ring-pink-400",
  purple: "ring-purple-500 dark:ring-purple-400",
  yellow: "ring-yellow-500 dark:ring-yellow-400",
  red: "ring-red-500 dark:ring-red-400",
  fuchsia: "ring-fuchsia-500 dark:ring-fuchsia-400",
  lime: "ring-lime-500 dark:ring-lime-400",
  emerald: "ring-emerald-500 dark:ring-emerald-400",
  cyan: "ring-cyan-500 dark:ring-cyan-400",
  indigo: "ring-indigo-500 dark:ring-indigo-400",
  sky: "ring-sky-500 dark:ring-sky-400",
  gray: "ring-gray-500 dark:ring-gray-400",
  teal: "border-teal-500 dark:border-teal-500",
  amber: "border-amber-500 dark:border-amber-500",
  rose: "border-rose-500 dark:border-rose-500"
};

export const matchCardColorToButtonStyles = {
  blue: "bg-blue-600 hover:bg-blue-800 dark:bg-blue-500 dark:hover:bg-blue-700 focus:ring-blue-300 dark:focus:ring-blue-800",
  green:
    "bg-green-600 hover:bg-green-800 dark:bg-green-500 dark:hover:bg-green-700 focus:ring-green-300 dark:focus:ring-green-800",
  pink: "bg-pink-600 hover:bg-pink-800 dark:bg-pink-500 dark:hover:bg-pink-700 focus:ring-pink-300 dark:focus:ring-pink-800",
  purple:
    "bg-purple-600 hover:bg-purple-800 dark:bg-purple-500 dark:hover:bg-purple-700 focus:ring-purple-300 dark:focus:ring-purple-800",
  yellow:
    "bg-yellow-600 hover:bg-yellow-800 dark:bg-yellow-500 dark:hover:bg-yellow-700 focus:ring-yellow-300 dark:focus:ring-yellow-800",
  red: "bg-red-600 hover:bg-red-800 dark:bg-red-500 dark:hover:bg-red-700 focus:ring-red-300 dark:focus:ring-red-800",
  fuchsia:
    "bg-fuchsia-600 hover:bg-fuchsia-800 dark:bg-fuchsia-500 dark:hover:bg-fuchsia-700 focus:ring-fuchsia-300 dark:focus:ring-fuchsia-800",
  lime: "bg-lime-600 hover:bg-lime-800 dark:bg-lime-500 dark:hover:bg-lime-700 focus:ring-lime-300 dark:focus:ring-lime-800",
  emerald:
    "bg-emerald-600 hover:bg-emerald-800 dark:bg-emerald-500 dark:hover:bg-emerald-700 focus:ring-emerald-300 dark:focus:ring-emerald-800",
  cyan: "bg-cyan-600 hover:bg-cyan-800 dark:bg-cyan-500 dark:hover:bg-cyan-700 focus:ring-cyan-300 dark:focus:ring-cyan-800",
  indigo:
    "bg-indigo-600 hover:bg-indigo-800 dark:bg-indigo-500 dark:hover:bg-indigo-700 focus:ring-indigo-300 dark:focus:ring-indigo-800",
  sky: "bg-sky-600 hover:bg-sky-800 dark:bg-sky-500 dark:hover:bg-sky-700 focus:ring-sky-300 dark:focus:ring-sky-800",
  teal: "bg-teal-600 hover:bg-teal-800 dark:bg-teal-500 dark:hover:bg-teal-700 focus:ring-teal-300 dark:focus:ring-teal-800",
  rose: "bg-rose-600 hover:bg-rose-800 dark:bg-rose-500 dark:hover:bg-rose-700 focus:ring-rose-300 dark:focus:ring-rose-800",
  amber:
    "bg-amber-600 hover:bg-amber-800 dark:bg-amber-500 dark:hover:bg-amber-700 focus:ring-amber-300 dark:focus:ring-amber-800"
};

/**
 * Announcement type color mappings
 */
export const announcementTypeColors = {
  competitions: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  executive_board:
    "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  project_gamechangers:
    "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  finance:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  ntc: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-300",
  governance:
    "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300",
  safeguarding: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-300",
  college: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-300",
  development:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-300",
  operations:
    "bg-slate-100 text-slate-800 dark:bg-slate-900 dark:text-slate-300"
};

/**
 * Announcement type label mappings
 */
export const announcementTypeLabels = {
  competitions: "Competitions",
  executive_board: "Executive Board",
  project_gamechangers: "Project GameChangers",
  finance: "Finance",
  ntc: "NTC",
  governance: "Governance",
  safeguarding: "Safeguarding",
  college: "College",
  development: "Development",
  operations: "Operations"
};

/**
 * Get the color classes for an announcement type badge
 * @param {string} type - The announcement type
 * @returns {string} - Tailwind CSS classes for the badge
 */
export const getAnnouncementTypeColor = type => {
  return (
    announcementTypeColors[type] ||
    "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300"
  );
};

/**
 * Get the human-readable label for an announcement type
 * @param {string} type - The announcement type
 * @returns {string} - Human-readable label
 */
export const getAnnouncementTypeLabel = type => {
  return announcementTypeLabels[type] || type;
};
