import clsx from "clsx";
import { Icon } from "solid-heroicons";
import {
  arrowUturnLeft,
  arrowUturnRight,
  chatBubbleBottomCenterText,
  link,
  listBullet,
  minus,
  photo,
  tableCells,
  videoCamera
} from "solid-heroicons/solid";
import {
  createEffect,
  createMemo,
  createSignal,
  For,
  onCleanup,
  onMount,
  Show
} from "solid-js";

import { Field, focusRing, input, primaryButton } from "../../committees";
import {
  uploadAnnouncementImage,
  uploadAnnouncementVideo
} from "../../queries";
import { uploadError } from "../../uploads";

// `active` is what isActive() is asked, so the button can show it is pressed.
const BUTTONS = [
  { label: "Bold", text: "B", active: ["bold"], run: c => c.toggleBold() },
  {
    label: "Italic",
    text: "I",
    active: ["italic"],
    run: c => c.toggleItalic()
  },
  {
    label: "Underline",
    text: "U",
    active: ["underline"],
    run: c => c.toggleUnderline()
  },
  {
    label: "Heading 2",
    text: "H2",
    active: ["heading", { level: 2 }],
    run: c => c.toggleHeading({ level: 2 })
  },
  {
    label: "Heading 3",
    text: "H3",
    active: ["heading", { level: 3 }],
    run: c => c.toggleHeading({ level: 3 })
  },
  {
    label: "Bulleted list",
    icon: listBullet,
    active: ["bulletList"],
    run: c => c.toggleBulletList()
  },
  {
    label: "Numbered list",
    text: "1.",
    active: ["orderedList"],
    run: c => c.toggleOrderedList()
  },
  {
    label: "Quote",
    icon: chatBubbleBottomCenterText,
    active: ["blockquote"],
    run: c => c.toggleBlockquote()
  },
  { label: "Horizontal rule", icon: minus, run: c => c.setHorizontalRule() },
  {
    label: "Table",
    icon: tableCells,
    run: c => c.insertTable({ rows: 3, cols: 3, withHeaderRow: true })
  },
  { label: "Undo", icon: arrowUturnLeft, run: c => c.undo() },
  { label: "Redo", icon: arrowUturnRight, run: c => c.redo() }
];

const button = pressed =>
  clsx(
    "inline-flex h-11 min-w-[44px] items-center justify-center rounded-lg px-2 text-sm font-bold",
    focusRing,
    pressed
      ? "bg-blue-100 text-blue-800"
      : "text-gray-700 hover:bg-gray-200 dark:text-gray-200 dark:hover:bg-gray-700"
  );

const note =
  "border-x border-gray-300 bg-gray-50 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800";

const SAFE_LINK = /^(https?:\/\/|mailto:)/i;

// Cloudinary's limit for one video in one request.
const MAX_VIDEO_BYTES = 100 * 1024 * 1024;

// What each upload button takes, checks first, sends and puts in the post.
const MEDIA = [
  {
    kind: "image",
    label: "Image",
    icon: photo,
    accept: "image/*",
    problem: uploadError,
    send: uploadAnnouncementImage,
    node: src => ({ type: "image", attrs: { src, alt: "" } })
  },
  {
    kind: "video",
    label: "Video",
    icon: videoCamera,
    accept: "video/mp4,video/webm,video/quicktime",
    problem: file =>
      file.size > MAX_VIDEO_BYTES ? "Videos must be 100 MB or smaller." : "",
    send: uploadAnnouncementVideo,
    node: src => ({ type: "video", attrs: { src } })
  }
];

// A small form under the toolbar: the link on the selection, or none.
const LinkForm = props => {
  const [url, setUrl] = createSignal(
    props.editor.getAttributes("link").href ?? ""
  );
  const [error, setError] = createSignal("");

  const apply = e => {
    e.preventDefault();
    const href = url().trim();
    if (href && !SAFE_LINK.test(href)) {
      return setError("Use a link that starts with https:// or mailto:");
    }
    const chain = props.editor.chain().focus().extendMarkRange("link");
    if (!href) chain.unsetLink();
    else if (
      props.editor.state.selection.empty &&
      !props.editor.isActive("link")
    ) {
      // Nothing selected to link: the address is the text.
      chain.insertContent({
        type: "text",
        text: href,
        marks: [{ type: "link", attrs: { href } }]
      });
    } else chain.setLink({ href });
    chain.run();
    props.close();
  };

  return (
    // Not a <form>: its submit would bubble up and save the post.
    <div
      class={`flex flex-wrap items-start gap-2 ${note}`}
      onKeyDown={e => e.key === "Escape" && props.close()}
    >
      <Field id="link-url" label="Link URL" error={error()} class="grow">
        <input
          id="link-url"
          type="text"
          inputmode="url"
          ref={el => onMount(() => el.focus())}
          placeholder="https://"
          value={url()}
          onInput={e => setUrl(e.currentTarget.value)}
          onKeyDown={e => e.key === "Enter" && apply(e)}
          class={input}
        />
      </Field>
      <button type="button" class={`${primaryButton} sm:mt-6`} onClick={apply}>
        Apply
      </button>
      <button
        type="button"
        class={`${button(false)} font-medium sm:mt-6`}
        onClick={() => {
          props.editor
            .chain()
            .focus()
            .extendMarkRange("link")
            .unsetLink()
            .run();
          props.close();
        }}
      >
        Remove link
      </button>
    </div>
  );
};

// The editor's buttons, the link form and the image upload's progress.
const EditorToolbar = props => {
  const [tick, setTick] = createSignal(0);
  const [linking, setLinking] = createSignal(false);
  const [progress, setProgress] = createSignal(null);
  const [uploading, setUploading] = createSignal(MEDIA[0]);
  const [uploadFailure, setUploadFailure] = createSignal("");

  createEffect(() => {
    const editor = props.editor();
    if (!editor) return;
    const update = () => setTick(t => t + 1);
    editor.on("transaction", update);
    onCleanup(() => editor.off("transaction", update));
  });

  const pressed = active => {
    tick();
    return Boolean(active && props.editor()?.isActive(...active));
  };

  // Where the selected image is, so each image gets its own description field.
  const imagePos = createMemo(() => {
    tick();
    const selection = props.editor()?.state.selection;
    return selection?.node?.type.name === "image" ? selection.from : null;
  });

  const closeLink = () => {
    setLinking(false);
    props.editor().commands.focus();
  };

  const upload = async (file, media) => {
    setUploadFailure("");
    const problem = await media.problem(file);
    if (problem) return setUploadFailure(problem);
    setUploading(media);
    setProgress(0);
    try {
      const src = await media.send(file, setProgress);
      const editor = props.editor();
      const node = media.node(src);
      // After the selection, so a selected image isn't replaced.
      editor
        .chain()
        .focus()
        .insertContentAt(editor.state.selection.to, node)
        .run();
      // Select it, so an image's description can be written.
      editor.state.doc.descendants((child, pos) => {
        if (child.type.name === node.type && child.attrs.src === src) {
          editor.commands.setNodeSelection(pos);
        }
      });
    } catch (error) {
      setUploadFailure(error.message);
    } finally {
      setProgress(null);
    }
  };

  return (
    <Show when={props.editor()}>
      <div class="sticky top-0 z-10">
        <div
          role="toolbar"
          aria-label="Formatting"
          class="flex flex-wrap gap-1 rounded-t-lg border border-gray-300 bg-gray-50 p-1 dark:border-gray-600 dark:bg-gray-800"
        >
          <For each={BUTTONS}>
            {b => (
              <button
                type="button"
                aria-label={b.label}
                title={b.label}
                aria-pressed={pressed(b.active)}
                class={button(pressed(b.active))}
                onClick={() => b.run(props.editor().chain().focus()).run()}
              >
                <Show when={b.icon} fallback={b.text}>
                  <Icon path={b.icon} class="h-5 w-5" aria-hidden="true" />
                </Show>
              </button>
            )}
          </For>
          <button
            type="button"
            aria-label="Link"
            title="Link"
            aria-pressed={pressed(["link"])}
            aria-expanded={linking()}
            class={button(pressed(["link"]))}
            onClick={() => (linking() ? closeLink() : setLinking(true))}
          >
            <Icon path={link} class="h-5 w-5" aria-hidden="true" />
          </button>
          <For each={MEDIA}>
            {media => {
              let fileInput;
              return (
                <>
                  <button
                    type="button"
                    aria-label={media.label}
                    title={media.label}
                    disabled={progress() !== null}
                    class={button(false)}
                    onClick={() => fileInput.click()}
                  >
                    <Icon
                      path={media.icon}
                      class="h-5 w-5"
                      aria-hidden="true"
                    />
                  </button>
                  <input
                    ref={fileInput}
                    id={`${media.kind}-file`}
                    type="file"
                    accept={media.accept}
                    tabindex="-1"
                    aria-label={`Choose ${media.label.toLowerCase()} file`}
                    class="sr-only"
                    onChange={e => {
                      const [file] = e.currentTarget.files;
                      // Cleared once it's sent, so the same file can be chosen again.
                      if (file) {
                        upload(file, media).finally(
                          () => (fileInput.value = "")
                        );
                      }
                    }}
                  />
                </>
              );
            }}
          </For>
        </div>
        <Show when={linking()}>
          <LinkForm editor={props.editor()} close={closeLink} />
        </Show>
        <For each={imagePos() === null ? [] : [imagePos()]}>
          {() => {
            let field;
            // Follows the image's alt (an undo, say), except while it's typed in.
            createEffect(() => {
              tick();
              const alt = props.editor().getAttributes("image").alt ?? "";
              if (field && document.activeElement !== field) field.value = alt;
            });
            return (
              <div class={note}>
                <Field id="image-alt" label="Image description">
                  <input
                    ref={field}
                    id="image-alt"
                    value={props.editor().getAttributes("image").alt ?? ""}
                    onInput={e =>
                      props
                        .editor()
                        .chain()
                        .updateAttributes("image", {
                          alt: e.currentTarget.value
                        })
                        .run()
                    }
                    aria-describedby="image-alt-hint"
                    class={input}
                  />
                </Field>
                <p
                  id="image-alt-hint"
                  class="mt-1 text-xs text-gray-600 dark:text-gray-400"
                >
                  For people who can't see it. Leave empty if it is only
                  decoration.
                </p>
              </div>
            );
          }}
        </For>
        <Show when={progress() !== null}>
          <p role="status" class={note}>
            Uploading {uploading().kind}…{" "}
            {progress().toLocaleString("en-IN", { style: "percent" })}
          </p>
        </Show>
        <Show when={uploadFailure()}>
          <p role="alert" class={`${note} text-red-700 dark:text-red-400`}>
            {uploadFailure()}
          </p>
        </Show>
      </div>
    </Show>
  );
};

export default EditorToolbar;
