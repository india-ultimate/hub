import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/solid-mini";
import { createUniqueId } from "solid-js";

// A native <dialog>: showModal() traps focus, Escape closes it, and focus goes
// back to whatever opened it. On phones it is a sheet from the bottom edge.
// Backdrop clicks close it too, unless `staticBackdrop` (unsaved edits).
const Modal = props => {
  let dialog;
  let pressedBackdrop = false;
  const titleId = createUniqueId();
  const close = () => (props.close ? props.close() : dialog.close());

  return (
    <dialog
      ref={el => {
        dialog = el;
        // Opening focuses the dialog and closing refocuses the trigger, and
        // either can scroll the page behind. Keep it where it was.
        const open = el.showModal.bind(el);
        let top = 0;
        el.showModal = () => {
          top = window.scrollY;
          open();
          window.scrollTo({ top, behavior: "instant" });
        };
        el.addEventListener("close", () =>
          window.scrollTo({ top, behavior: "instant" })
        );
        props.ref?.(el);
      }}
      aria-labelledby={titleId}
      onMouseDown={e => (pressedBackdrop = e.target === dialog)}
      onClick={e => {
        // Pressed and released on the backdrop: not the end of a text selection.
        if (!props.staticBackdrop && pressedBackdrop && e.target === dialog) {
          close();
        }
      }}
      class={clsx(
        "rounded-xl p-0 backdrop:bg-gray-700/90 open:animate-dialog-in motion-reduce:animate-none max-sm:mb-0 max-sm:mt-auto max-sm:w-full max-sm:max-w-full max-sm:rounded-b-none",
        props.wide ? "md:w-11/12 md:max-w-5xl" : "md:w-1/2",
        props.fullWidth ? "w-full" : "w-fit"
      )}
    >
      <div class="flex w-full flex-col items-start gap-2 rounded-xl bg-gray-50 p-4 text-gray-600 dark:bg-gray-600 dark:text-gray-100 max-sm:rounded-b-none">
        <div class="flex w-full items-center justify-between gap-1 text-base sm:text-lg">
          <div id={titleId} class="flex">
            {props.title || ""}
          </div>
          <button
            type="button"
            class="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-transparent text-sm text-gray-500 hover:bg-gray-300 hover:text-gray-900 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-white dark:focus-visible:ring-blue-800"
            onClick={close}
          >
            <Icon path={xMark} class="w-6" />
            <span class="sr-only">Close modal</span>
          </button>
        </div>

        <hr class="mt-1 h-px w-full border-0 bg-gray-300 dark:bg-gray-500" />

        <div
          class={clsx(
            "mt-2 w-full pb-[env(safe-area-inset-bottom)]",
            // Fields that bring their own side padding line up with the title.
            props.flush && "[&_div.lg\\:px-10]:px-0 [&_div.px-8]:px-0"
          )}
        >
          {props.children}
        </div>
      </div>
    </dialog>
  );
};

export default Modal;
