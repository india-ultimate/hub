import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { createAsyncOptions, Select } from "@thisbeyond/solid-select";
import { Icon } from "solid-heroicons";
import { handRaised } from "solid-heroicons/outline";
import { plus } from "solid-heroicons/solid";
import { createEffect, createSignal, Show } from "solid-js";

import { addToRoster, fetchUser, searchPlayers } from "../../queries";
import InputLabel from "../InputLabel";
import Modal from "../Modal";

const AddToRoster = props => {
  let modalRef;
  let successPopoverRef, errorPopoverRef;
  const [status, setStatus] = createSignal("");
  const [initialValue, setInitialValue] = createSignal(null, { equals: false });

  const queryClient = useQueryClient();
  const userQuery = createQuery(() => ["me"], fetchUser);
  const addToRosterMutation = createMutation({
    mutationFn: addToRoster,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournament-roster"] })
  });

  createEffect(function onMutationComplete() {
    if (addToRosterMutation.isSuccess) {
      setStatus("Successfully added player to the roster");
      successPopoverRef.showPopover();
    }
    if (addToRosterMutation.isError) {
      setStatus("Adding to the roster failed");
      errorPopoverRef.showPopover();
    }
  });

  const [selectedValue, setSelectedValue] = createSignal();

  const handleSubmit = () => {
    addToRosterMutation.mutate({
      event_id: props.eventId,
      team_id: props.teamId,
      body: {
        player_id: selectedValue()?.id
      }
    });
    setInitialValue(null);

    modalRef.close();
  };

  return (
    <div class="mt-4 flex justify-center gap-2">
      <Show
        when={
          !props.roster
            ?.map(reg => reg.player.id)
            .includes(userQuery.data?.player?.id)
        }
      >
        <button
          onClick={() => {
            addToRosterMutation.mutate({
              event_id: props.eventId,
              team_id: props.teamId,
              body: {
                player_id: userQuery.data?.player?.id
              }
            });
          }}
          type="button"
          class="mb-2 me-2 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-blue-700 px-2 py-2.5 text-center text-sm font-medium text-blue-700 hover:bg-blue-800 hover:text-white focus:outline-none dark:border-blue-500  dark:text-blue-500 dark:hover:bg-blue-500 dark:hover:text-white dark:focus:ring-blue-800 md:px-5"
        >
          <Icon path={handRaised} style={{ width: "24px" }} />
          <span class="w-3/4">Add myself to the roster</span>
        </button>
      </Show>
      <button
        onClick={() => modalRef.showModal()}
        type="button"
        class="mb-2 me-2 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-2 py-2.5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 md:px-5"
      >
        <Icon path={plus} style={{ width: "24px" }} />
        <span class="w-3/4">Add a player to the roster</span>
      </button>
      <Modal
        ref={modalRef}
        title={<span class="font-bold">Adding a new player to the roster</span>}
        close={() => modalRef.close()}
      >
        <AddPlayerRegistrationForm
          roster={props.roster}
          setSelectedValue={setSelectedValue}
          handleSubmit={handleSubmit}
          initialValue={initialValue()}
        />
      </Modal>
      <div
        popover
        ref={successPopoverRef}
        role="alert"
        class="mb-4 w-fit rounded-lg bg-green-200 p-4 text-sm text-green-800 dark:bg-gray-800 dark:text-green-400"
      >
        <span class="font-medium">{status()}</span>
      </div>
      <div
        popover
        ref={errorPopoverRef}
        role="alert"
        class="mb-4 w-fit rounded-lg bg-red-200 p-4 text-sm text-red-800 dark:bg-gray-800 dark:text-red-400"
      >
        <span class="font-medium">{status()}</span>
      </div>
    </div>
  );
};

const AddPlayerRegistrationForm = props => {
  const onChange = selected => {
    console.log(selected);
    props.setSelectedValue(selected);
  };
  const selectProps = createAsyncOptions(searchPlayers);
  const selectFormat = item =>
    item.full_name ? item.full_name + ` (${item.email})` : item.email;

  return (
    <div class="h-96 w-full rounded-lg p-6">
      <InputLabel
        name="players"
        label="Select the player"
        subLabel="Search by name or email"
        required={true}
      />
      <Select
        name="players"
        format={selectFormat}
        onChange={onChange}
        isOptionDisabled={value =>
          props.roster?.map(reg => reg.player.id).includes(value.id)
        }
        initialValue={props.initialValue}
        {...selectProps}
      />
      <div class="mt-8 flex w-full justify-center">
        <button
          onClick={() => props.handleSubmit()}
          type="submit"
          class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 md:w-auto"
        >
          Add to roster
        </button>
      </div>
    </div>
  );
};

export default AddToRoster;
