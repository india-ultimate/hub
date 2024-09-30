import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { chevronRight } from "solid-heroicons/solid";

import Modal from "../Modal";

const FinalSpiritScores = props => {
  let modalRef;
  return (
    <>
      <button
        class={clsx(
          "group relative inline-flex items-center justify-center overflow-hidden rounded-full p-0.5 text-xs font-medium",
          "text-gray-900 focus:outline-none dark:text-white",
          "transition-all duration-75 ease-in hover:scale-105"
        )}
        onClick={() => modalRef.showModal()}
      >
        <span
          class={clsx(
            "relative inline-flex items-center rounded-full px-2 py-1.5 transition-all duration-75 ease-in group-hover:shadow-lg dark:bg-gray-700",
            props.bgColor
          )}
        >
          <span
            class={clsx(
              "me-2 rounded-full px-2.5 py-0.5 text-white",
              props.badgeColor
            )}
          >
            SoTG
          </span>
          {props.spiritScoreText}
          <Icon path={chevronRight} class="ml-1.5 w-4" />
        </span>
      </button>
      <Modal
        ref={modalRef}
        title={
          <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
            Spirit Scores, MVP & MSP
          </h3>
        }
        close={() => modalRef.close()}
      >
        {props.children}
      </Modal>
    </>
  );
};

export default FinalSpiritScores;
