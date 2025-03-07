import { createForm } from "@modular-forms/solid";
import { Icon } from "solid-heroicons";
import { pencil } from "solid-heroicons/solid";

import { playerRoles } from "../../constants";
import Checkbox from "../Checkbox";
import Modal from "../Modal";
import Select from "../Select";

const EditPlayerRegistrationForm = componentProps => {
  const [_, { Form, Field }] = createForm({
    validateOn: "blur",
    revalidateOn: "touched",
    initialValues: componentProps.initialValues
  });

  return (
    <div class="w-full rounded-lg bg-gray-200 p-6">
      <Form
        onSubmit={values => componentProps.handleSubmit(values)}
        shouldDirty={true}
      >
        <Field name="role">
          {(field, props) => (
            <Select
              {...props}
              value={field.value}
              error={field.error}
              options={playerRoles}
              label="Role"
              placeholder="Select role..."
            />
          )}
        </Field>
        <Field name="is_playing" type="boolean">
          {(field, props) => (
            <Checkbox
              {...props}
              type="checkbox"
              label="Will this person play in the tournament ?"
              checked={field.value}
              value={field.value}
              class="my-2"
            />
          )}
        </Field>
        <div class="px-8 lg:px-10">
          <button
            type="submit"
            class="w-fit rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:bg-gray-400 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 disabled:dark:bg-gray-400 sm:w-auto"
            disabled={componentProps.disabled}
          >
            Edit registration
          </button>
        </div>
      </Form>
    </div>
  );
};

const EditRosteredPlayer = props => {
  let modalRef;

  const handleEditSubmit = editedValues => {
    if (Object.keys(editedValues).length === 0) {
      return;
    }

    props.updateRegistrationMutation.mutate({
      registration_id: props.registration.id,
      team_id: props.teamId,
      event_id: props.eventId,
      body: {
        ...editedValues
      }
    });

    modalRef.close();
  };

  return (
    <div>
      <button
        class="rounded-md p-1 text-yellow-400 outline outline-2 outline-yellow-400"
        onClick={() => modalRef.showModal()}
      >
        <Icon path={pencil} class="inline h-4 w-4" />
        <span class="sr-only">Edit registration</span>
      </button>
      <Modal
        ref={modalRef}
        title={
          <>
            <span class="mr-1 font-normal text-yellow-700">Editing - </span>
            <span class="font-semibold">{props.playerName}</span>
          </>
        }
        close={() => modalRef.close()}
      >
        <EditPlayerRegistrationForm
          handleSubmit={handleEditSubmit}
          initialValues={{
            is_playing: props.registration?.is_playing
          }}
        />
      </Modal>
    </div>
  );
};

export default EditRosteredPlayer;
