// The post's typography: the page that reads it and the editor that writes it.
export const postProse =
  "prose-sm max-w-none dark:prose-invert md:prose lg:prose-lg prose-a:text-blue-600 hover:prose-a:text-blue-700 [&_img]:!h-auto [&_img]:object-contain [&_li]:!list-item [&_ol]:!list-decimal [&_ol]:!pl-6 [&_table]:!my-2 [&_table]:!mb-4 [&_table]:border [&_table]:border-gray-200 dark:[&_table]:border-gray-700 [&_td]:border [&_td]:border-gray-200 [&_td]:!px-2 [&_td]:!py-1 [&_td]:!text-xs dark:[&_td]:border-gray-700 sm:[&_td]:!px-4 sm:[&_td]:!py-2 sm:[&_td]:!text-sm [&_th]:border [&_th]:border-gray-200 [&_th]:!px-2 [&_th]:!py-1 [&_th]:!text-xs dark:[&_th]:border-gray-700 sm:[&_th]:!px-4 sm:[&_th]:!py-2 sm:[&_th]:!text-sm [&_ul]:!list-disc [&_ul]:!pl-6";

// What the editor drops from a post written in the admin's old editor.
const UNSUPPORTED = /<video|<iframe|<style|<font|style=/i;
export const hasUnsupportedFormatting = html => UNSUPPORTED.test(html);

// The server's validation messages name the field they are about.
const FIELD_PATTERNS = [
  ["title", /title/i],
  ["content", /content|empty/i],
  ["action_url", /url|link/i],
  ["action_text", /action|button|label/i]
];
export const errorField = message =>
  FIELD_PATTERNS.find(([, pattern]) => pattern.test(message))?.[0] ?? "form";
