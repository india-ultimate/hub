import { mergeAttributes, Node } from "@tiptap/core";

const sourceOf = element =>
  element.getAttribute("src") ||
  element.querySelector("source")?.getAttribute("src");

// A video, played only when asked: `<video src>`, or an old post's
// `<video><source src></video>`. The server sets the same attributes.
export const Video = Node.create({
  name: "video",
  group: "block",
  atom: true,
  draggable: true,
  addAttributes: () => ({
    src: { default: null, parseHTML: sourceOf }
  }),
  // A video with nothing to play is dropped, not kept as an empty player.
  parseHTML: () => [
    { tag: "video", getAttrs: element => (sourceOf(element) ? null : false) }
  ],
  renderHTML: ({ HTMLAttributes }) => [
    "video",
    mergeAttributes(HTMLAttributes, {
      controls: "",
      preload: "metadata",
      playsinline: ""
    })
  ]
});
