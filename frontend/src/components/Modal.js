import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/solid-mini";

const Modal = props => {
  return (
    <dialog
      ref={props.ref}
      class={clsx(
        "rounded-xl p-0 backdrop:bg-gray-700/90 md:w-1/2",
        props.fullWidth ? "w-full" : "w-fit"
      )}
    >
      <div class="flex w-full flex-col items-start gap-2 rounded-xl bg-gray-50 p-4 text-gray-600 dark:bg-gray-600 dark:text-gray-100">
        <div class="flex w-full items-center justify-between gap-1 text-base sm:text-lg">
          <div class="flex">{props.title || ""}</div>
          <button
            type="button"
            class="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-transparent text-sm text-gray-400 hover:bg-gray-300 hover:text-gray-900 dark:hover:bg-gray-700 dark:hover:text-white"
            onClick={() => props.close()}
          >
            <Icon path={xMark} class="w-6" />
            <span class="sr-only">Close modal</span>
          </button>
        </div>

        <hr class="mt-1 h-px w-full border-0 bg-gray-300 dark:bg-gray-500" />

        <div class="mt-2 w-full">{props.children}</div>
      </div>
    </dialog>
  );
};

export default Modal;
