// A return link may only point at a team's registration page; anything
// else is ignored, so it can't bounce people off the site or elsewhere.
export const RETURN_PATTERN =
  /^\/tournament\/([\w-]+)\/team\/([\w-]+)\/registration$/;

export const isSafeReturn = path =>
  typeof path === "string" && RETURN_PATTERN.test(path);

// The event and team a safe return link names, or null.
export const parseReturn = path => {
  const match = typeof path === "string" && path.match(RETURN_PATTERN);
  return match ? { eventSlug: match[1], teamSlug: match[2] } : null;
};
