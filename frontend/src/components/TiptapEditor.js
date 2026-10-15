import { Editor } from "@tiptap/core";
import Image from "@tiptap/extension-image";
import {
  Table,
  TableCell,
  TableHeader,
  TableRow
} from "@tiptap/extension-table";
import StarterKit from "@tiptap/starter-kit";
import { onCleanup, onMount } from "solid-js";

import { postProse } from "../announcements";
import { Video } from "../tiptapVideo";

// A TipTap editor in a div: made on mount, destroyed on cleanup. `onReady`
// gets the editor; `onChange` gets the HTML after each edit.
const TiptapEditor = props => {
  let element;

  onMount(() => {
    const editor = new Editor({
      element,
      content: props.content,
      extensions: [
        // StarterKit brings underline and links too.
        StarterKit.configure({ link: { openOnClick: false } }),
        Image,
        Video,
        Table,
        TableRow,
        TableHeader,
        TableCell
      ],
      editorProps: {
        attributes: {
          id: props.id,
          role: "textbox",
          "aria-multiline": "true",
          "aria-labelledby": props.labelledBy,
          class: `${postProse} min-h-[16rem] p-4 focus:outline-none`
        }
      },
      onUpdate: () => props.onChange(editor.getHTML())
    });
    props.onReady(editor);
    onCleanup(() => editor.destroy());
  });

  return (
    <div
      ref={element}
      class="rounded-b-lg border border-gray-300 bg-white focus-within:ring-2 focus-within:ring-blue-500 dark:border-gray-600"
    />
  );
};

export default TiptapEditor;
