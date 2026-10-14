// The reactions an announcement can get, in the server's Reaction.Kind order.
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
