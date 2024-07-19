import clsx from "clsx";
import { Icon } from "solid-heroicons";

import Modal from "../Modal";

const SubmitScoreModal = props => {
  let modalRef;
  return (
    <>
      <button
        type="button"
        class={clsx(
          "relative mb-2 mr-2 inline-flex items-center justify-center overflow-hidden rounded-lg p-0.5 font-medium",
          "text-xs text-gray-900 focus:outline-none focus:ring-4 dark:text-white",
          props.buttonColor
        )}
        onClick={() => modalRef.showModal()}
      >
        <span class="relative inline-flex items-center rounded-md bg-white px-3 py-2.5 transition-all duration-75 ease-in group-hover:bg-opacity-0 dark:bg-gray-800">
          {props.button.text}
          <Icon path={props.button.icon} class="ml-1.5 w-4" />
        </span>
      </button>

      <Modal
        ref={modalRef}
        title={
          <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
            {props.button.text}
          </h3>
        }
        close={() => {
          modalRef.close();
          props.onClose();
        }}
      >
        {props.children}
      </Modal>
    </>
  );
};

export default SubmitScoreModal;
