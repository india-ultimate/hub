import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { Show } from "solid-js";

import Modal from "../Modal";

const ButtonWithModal = props => {
  let modalRef;
  return (
    <>
      <button
        type="button"
        class={clsx(
          "group relative mb-2 mr-2 inline-flex items-center justify-center overflow-hidden rounded-lg p-0.5 font-medium",
          "text-xs text-gray-900 focus:outline-none focus:ring-4 disabled:bg-gray-400 dark:text-white",
          props.buttonColor || "bg-blue-600"
        )}
        onClick={() => modalRef.showModal()}
        disabled={props.disabled}
      >
        <span
          class={clsx(
            "relative inline-flex items-center rounded-md px-3 py-2.5 transition-all duration-75 ease-in",
            "bg-white group-hover:bg-opacity-0 group-disabled:bg-gray-300 dark:bg-gray-800"
          )}
        >
          {props.button?.text || ""}
          <Show when={props.button?.icon}>
            <Icon path={props.button?.icon} class="ml-1.5 w-4" />
          </Show>
        </span>
      </button>

      <Modal
        ref={modalRef}
        title={
          <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
            {props.button?.text || ""}
          </h3>
        }
        close={() => {
          modalRef.close();
          props.onClose();
        }}
        fullWidth={true}
      >
        {props.children}
      </Modal>
    </>
  );
};

export default ButtonWithModal;
