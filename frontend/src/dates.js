import { parseLocalDate } from "./utils";

export const ordinal = n => {
  const suffixes = { 1: "st", 2: "nd", 3: "rd" };
  return `${n}${n > 10 && n < 20 ? "th" : (suffixes[n % 10] ?? "th")}`;
};

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
