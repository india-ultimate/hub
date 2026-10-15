import { getCookie } from "./utils";

// The reactions an announcement or a comment can get, in the server's Reaction.Kind order.
// The server stores the kind; the emoji and label live here.
export const REACTIONS = [
  { kind: "like", emoji: "👍", label: "Like" },
  { kind: "love", emoji: "❤️", label: "Love" },
  { kind: "celebrate", emoji: "🎉", label: "Celebrate" },
  { kind: "applause", emoji: "👏", label: "Applause" },
  { kind: "thanks", emoji: "🙏", label: "Thank you" },
  { kind: "disc", emoji: "🥏", label: "Let's play" },
  { kind: "dislike", emoji: "👎", label: "Dislike" }
];

// Turn one of the user's reactions on or off at `url` (…/reactions/{kind});
// the server answers with the new counts.
export const saveReaction = async (url, on) => {
  const response = await fetch(url, {
    method: on ? "PUT" : "DELETE",
    headers: { "X-CSRFToken": getCookie("csrftoken") }
  });
  if (!response.ok) throw new Error("Couldn't save your reaction");
  return response.json();
};

// The counts as they will be after this toggle: kinds with a count, in order.
export const toggled = (list, kind, on) =>
  REACTIONS.map(({ kind: k }) => {
    const current = list.find(r => r.kind === k) || {
      kind: k,
      count: 0,
      reacted: false
    };
    return k === kind
      ? { kind, count: current.count + (on ? 1 : -1), reacted: on }
      : current;
  }).filter(r => r.count > 0);
