import { parseLocalDate } from "./utils";

export const ordinal = n => {
  const suffixes = { 1: "st", 2: "nd", 3: "rd" };
  return `${n}${n > 10 && n < 20 ? "th" : (suffixes[n % 10] ?? "th")}`;
};

// A "YYYY-MM-DD" day shown as that same day, wherever the viewer is: read
// as local midnight, so never format it with timeZone "UTC".
export const formatDay = (day, locale, options) =>
  parseLocalDate(day).toLocaleDateString(locale, options);

export const formatDates = (start, end) => {
  const from = parseLocalDate(start);
  const to = parseLocalDate(end);
  const month = d => d.toLocaleDateString("en-IN", { month: "short" });
  if (from.getTime() === to.getTime())
    return `${from.getDate()} ${month(from)}`;
  if (from.getMonth() === to.getMonth())
    return `${from.getDate()}–${to.getDate()} ${month(to)}`;
  return `${from.getDate()} ${month(from)} – ${to.getDate()} ${month(to)}`;
};
