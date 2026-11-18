import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { arrowDownTray, arrowTopRightOnSquare } from "solid-heroicons/outline";
import { documentText } from "solid-heroicons/solid";
import { createSignal, onCleanup, Show } from "solid-js";

import {
  download,
  fileName,
  isImage,
  isPdf,
  previewsInline
} from "../../attachments";

const ring =
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2";
const theirRing = clsx(
  ring,
  "focus-visible:ring-blue-500 dark:focus-visible:ring-offset-gray-800"
);
const myRing = clsx(
  ring,
  "focus-visible:ring-white focus-visible:ring-offset-blue-700 dark:focus-visible:ring-offset-blue-600"
);
const barButton =
  "inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1.5 rounded-lg px-3 text-sm font-medium text-white hover:bg-white/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-white";
const loading = "absolute text-sm text-white/80";

// An image or PDF attachment that opens full screen; other files only download.
const AttachmentPreview = props => {
  let dialog, opener, down;
  const [open, setOpen] = createSignal(false);
  const [loaded, setLoaded] = createSignal(false);
  const [broken, setBroken] = createSignal(false);
  const name = () => fileName(props.url);
  const pdf = () => isPdf(props.url);
  const [inline, setInline] = createSignal(previewsInline());
  const ringClass = () => (props.mine ? myRing : theirRing);

  const unlockScroll = () => document.body.classList.remove("overflow-hidden");
  onCleanup(() => open() && unlockScroll());

  const show = () => {
    setInline(previewsInline());
    if (pdf() && !inline()) {
      window.open(props.url, "_blank", "noopener");
      return;
    }
    setLoaded(false);
    setBroken(false);
    setOpen(true);
    document.body.classList.add("overflow-hidden");
    dialog.showModal();
  };

  return (
    <div class="mt-2 flex flex-col items-start gap-1">
      <Show when={isImage(props.url) || pdf()}>
        <button
          ref={opener}
          id={`attachment-open-${props.id}`}
          type="button"
          aria-label={
            pdf() && !inline()
              ? `Open ${name()} in a new tab`
              : `View ${name()} full screen`
          }
          onClick={show}
          class={clsx(
            "rounded-lg",
            ringClass(),
            pdf()
              ? [
                  "inline-flex min-h-[44px] max-w-full items-center gap-2 border border-current px-3 text-sm font-medium",
                  props.mine ? "hover:bg-white/10" : "hover:bg-black/5"
                ]
              : "cursor-zoom-in transition-opacity hover:opacity-90 motion-reduce:transition-none"
          )}
        >
          <Show
            when={pdf()}
            fallback={
              <img
                src={props.url}
                alt={props.alt}
                loading="lazy"
                class="max-h-48 max-w-full rounded-lg object-contain"
              />
            }
          >
            <Icon
              path={documentText}
              class="h-5 w-5 shrink-0"
              aria-hidden="true"
            />
            <span class="truncate">{name()}</span>
            <Show when={!inline()}>
              <Icon
                path={arrowTopRightOnSquare}
                class="h-4 w-4 shrink-0"
                aria-hidden="true"
              />
            </Show>
          </Show>
        </button>
      </Show>
      <button
        type="button"
        onClick={() => download(props.url)}
        class={clsx(
          "inline-flex min-h-[44px] items-center gap-1.5 rounded text-sm font-medium underline",
          ringClass(),
          props.mine ? "text-white" : "text-blue-700 dark:text-blue-300"
        )}
      >
        <Icon path={arrowDownTray} class="h-4 w-4" aria-hidden="true" />
        Download {name()}
      </button>
      <dialog
        ref={dialog}
        id={`attachment-dialog-${props.id}`}
        aria-labelledby={`attachment-title-${props.id}`}
        onClose={() => {
          setOpen(false);
          unlockScroll();
          opener?.focus();
        }}
        class="m-0 h-dvh max-h-none w-screen max-w-none bg-black/90 p-0 text-white backdrop:bg-black"
      >
        <Show when={open()}>
          <div class="flex h-full flex-col">
            <div class="flex items-center gap-1 px-2 py-2">
              <h2
                id={`attachment-title-${props.id}`}
                class="min-w-0 flex-1 truncate px-2 text-sm font-medium"
              >
                {name()}
              </h2>
              <button
                type="button"
                onClick={() => download(props.url)}
                aria-label={`Download ${name()}`}
                class={barButton}
              >
                <Icon path={arrowDownTray} class="h-5 w-5" aria-hidden="true" />
                <span class="hidden sm:inline">Download</span>
              </button>
              <a
                href={props.url}
                target="_blank"
                rel="noopener"
                referrerpolicy="no-referrer"
                aria-label="Open in new tab"
                class={barButton}
              >
                <Icon
                  path={arrowTopRightOnSquare}
                  class="h-5 w-5"
                  aria-hidden="true"
                />
                <span class="hidden sm:inline">Open in new tab</span>
              </a>
              <button
                id={`attachment-close-${props.id}`}
                type="button"
                autofocus
                aria-label="Close preview"
                onClick={() => dialog.close()}
                class={clsx(barButton, "text-lg")}
              >
                ✕
              </button>
            </div>
            <div
              class="relative flex min-h-0 flex-1 items-center justify-center overscroll-contain"
              onPointerDown={e => (down = e.target)}
              onClick={e =>
                e.target === e.currentTarget &&
                down === e.currentTarget &&
                dialog.close()
              }
            >
              <Show when={!loaded() && !broken()}>
                <p role="status" class={loading}>
                  Loading…
                </p>
              </Show>
              <Show
                when={pdf()}
                fallback={
                  <Show
                    when={!broken()}
                    fallback={
                      <p role="alert" class="text-white/80">
                        Couldn&apos;t load this image.
                      </p>
                    }
                  >
                    <img
                      src={props.url}
                      alt={props.alt}
                      onLoad={() => setLoaded(true)}
                      onError={() => setBroken(true)}
                      class="relative max-h-full max-w-full object-contain"
                    />
                  </Show>
                }
              >
                <iframe
                  title={name()}
                  src={props.url}
                  referrerpolicy="no-referrer"
                  onLoad={() => setLoaded(true)}
                  class={clsx(
                    "relative h-full w-full",
                    loaded() ? "bg-white" : "bg-transparent"
                  )}
                />
              </Show>
            </div>
          </div>
        </Show>
      </dialog>
    </div>
  );
};

export default AttachmentPreview;
