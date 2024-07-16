import clsx from "clsx";
import { Icon } from "solid-heroicons";

import Modal from "../Modal";
import MatchScoreForm from "../tournament/MatchScoreForm";

const SubmitScore = props => {
  let modalRef;
  return (
    <>
      <button
        type="button"
        class={clsx(
          "relative mb-2 mr-2 inline-flex items-center justify-center overflow-hidden rounded-lg p-0.5 font-medium",
          "text-xs text-gray-900 hover:text-white focus:outline-none focus:ring-4 dark:text-white",
          props.buttonColor
        )}
        onClick={() => modalRef.showModal()}
      >
        <span class="relative inline-flex items-center rounded-md bg-white px-3 py-2.5 transition-all duration-75 ease-in group-hover:bg-opacity-0 dark:bg-gray-800">
          {props.buttonText}
          <Icon path={props.buttonIcon} class="ml-1.5 w-4" />
        </span>
      </button>

      <Modal
        ref={modalRef}
        title={
          <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
            {props.buttonText}
          </h3>
        }
        close={() => {
          modalRef.close();
          props.refreshMatchesOnClose();
        }}
      >
        <div class="rounded-lg bg-white p-4 shadow dark:bg-gray-700">
          <MatchScoreForm
            match={props.match}
            currTeamNo={props.currTeamNo}
            oppTeamNo={props.oppTeamNo}
          />
        </div>
      </Modal>
    </>
  );
};

export default SubmitScore;
