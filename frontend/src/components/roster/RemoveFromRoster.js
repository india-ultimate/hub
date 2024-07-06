import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/solid";

import Modal from "../Modal";

const RemoveFromRoster = props => {
  let modalRef;

  return (
    <div>
      <button
        class="rounded-md text-red-400 outline outline-2 outline-red-300"
        onClick={() => modalRef.showModal()}
      >
        <Icon path={xMark} class="inline h-6 w-6" />
        <span class="sr-only">Remove from roster</span>
      </button>
      <Modal
        ref={modalRef}
        title={
          <>
            <span class="mr-1 font-normal text-red-600">Removing - </span>
            <span class="font-semibold">{props.playerName}</span>
          </>
        }
        close={() => modalRef.close()}
      >
        <span>Do you want to remove </span>
        <span class="inline font-semibold">{props.playerName}</span> from the
        roster ?
        <div class="mt-4">
          <button
            type="button"
            class="mb-2 me-2 rounded-lg bg-red-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-4 focus:ring-red-300 dark:bg-red-600 dark:hover:bg-red-700 dark:focus:ring-red-900"
            onClick={() => {
              props.removeMutation.mutate({
                registration_id: props.regId,
                body: {
                  event_id: props.eventId,
                  team_id: props.teamId
                }
              });
            }}
          >
            Yes
          </button>
          <button
            type="button"
            class="mb-2 me-2 rounded-lg bg-green-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-green-800 focus:outline-none focus:ring-4 focus:ring-green-300 dark:bg-green-600 dark:hover:bg-green-700 dark:focus:ring-green-800"
            onClick={() => modalRef.close()}
          >
            No
          </button>
        </div>
      </Modal>
    </div>
  );
};

export default RemoveFromRoster;
