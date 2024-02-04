import { createForm, required, reset, toTrimmed } from "@modular-forms/solid";
import { createEffect, createSignal, For, onCleanup, Show } from "solid-js";

import Checkbox from "../Checkbox";
import Modal from "../Modal";
import TextInput from "../TextInput";

const EditFieldForm = componentProps => {
  const [fieldsForm, { Form, Field }] = createForm({
    validateOn: "blur",
    revalidateOn: "touched"
  });

  createEffect(() => {
    reset(fieldsForm, {
      initialValues: componentProps.initialValues
    });
  });

  return (
    <div>
      <div class="w-fit rounded-lg bg-gray-200 p-6 dark:bg-gray-700/50">
        <Form
          onSubmit={values => componentProps.handleSubmit(values)}
          shouldDirty={true}
        >
          <Field
            name="name"
            type="string"
            transform={toTrimmed({ on: "input" })}
            validate={required("Please enter a name for the field")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                type="text"
                label="Field name"
                placeholder="Field 1"
                value={field.value}
                error={field.error}
                required
                padding
              />
            )}
          </Field>
          <Field name="is_broadcasted" type="boolean">
            {(field, props) => (
              <Checkbox
                {...props}
                type="checkbox"
                label="Will this field be broadcasted ?"
                checked={field.value}
                value={field.value}
                padding
                class="my-2"
              />
            )}
          </Field>
          <button
            type="submit"
            value="default"
            class="w-fit rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 disabled:dark:bg-gray-400 sm:w-auto"
            disabled={componentProps.disabled}
          >
            Edit Field
          </button>
        </Form>
      </div>
    </div>
  );
};

const CreatedFields = props => {
  let modalRef;
  let secondsLeftInterval, modalCloseTimeout;

  const [editingField, setEditingField] = createSignal();
  const [editStatus, setEditStatus] = createSignal("");
  const [secsLeftToClose, setSecsLeftToClose] = createSignal(4);

  function handleEditClick(field) {
    setEditingField(field);
    modalRef.showModal();
  }

  function resetModalStatus() {
    setEditStatus("");
    clearInterval(secondsLeftInterval);
    clearTimeout(modalCloseTimeout);
    setSecsLeftToClose(4);
  }

  function handleEditClose() {
    modalRef.close();
    resetModalStatus();
    setEditingField();
  }

  async function handleEditSubmit(editedValues) {
    resetModalStatus();

    if (Object.keys(editedValues).length === 0) {
      return;
    }

    props.updateFieldMutation.mutate({
      field_id: editingField().id,
      body: { ...editedValues, tournament_id: props.tournamentId }
    });

    secondsLeftInterval = setInterval(() => {
      setSecsLeftToClose(prev => prev - 1);
    }, 1 * 1000);

    modalCloseTimeout = setTimeout(handleEditClose, 4 * 1000);
  }

  createEffect(function setStatusMessage() {
    if (props.updateFieldMutation.isSuccess) {
      setEditStatus("Update done ✅");
    }
    if (props.updateFieldMutation.isError) {
      setEditStatus(props.updateFieldMutation.error.message);
    }
  });

  onCleanup(resetModalStatus);

  return (
    <div class="my-4 grid grid-cols-3 gap-4">
      <For each={props.fields}>
        {field => (
          <div>
            <div class="relative overflow-x-auto rounded-md">
              <div class="flex w-full items-center justify-between bg-gray-300 p-4 text-left text-lg font-semibold text-gray-900 rtl:text-right dark:bg-gray-700 dark:text-white">
                <span>{field.name}</span>
                <button
                  type="button"
                  class="rounded-lg bg-yellow-400 px-4 py-1.5 text-sm font-medium text-white hover:bg-yellow-500 focus:outline-none focus:ring-4 focus:ring-yellow-300 dark:text-gray-800 dark:focus:ring-yellow-500"
                  onClick={() => handleEditClick(field)}
                >
                  Edit
                </button>
              </div>
              <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                <tbody>
                  <tr class="bg-gray-200 dark:border-gray-700 dark:bg-gray-800">
                    <th
                      scope="row"
                      class="px-4 py-4 font-medium text-gray-900 dark:text-white"
                    >
                      Broadcasted ?
                    </th>
                    <td class="px-6 py-4">
                      {field.is_broadcasted ? "Yes" : "No"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}
      </For>
      <Modal
        ref={modalRef}
        close={handleEditClose}
        title={
          <>
            <span class="font-light">Editing - </span>
            <span class="font-semibold">{editingField()?.name}</span>
          </>
        }
      >
        <>
          <EditFieldForm
            initialValues={{
              name: editingField()?.name,
              is_broadcasted: editingField()?.is_broadcasted
            }}
            handleSubmit={handleEditSubmit}
            disabled={props.editingDisabled}
          />
          <div class="m-2">
            <p>{editStatus()}</p>
            <Show when={editStatus()}>
              <p class="italic">
                Auto closing in {secsLeftToClose()} seconds...
              </p>
            </Show>
          </div>
        </>
      </Modal>
    </div>
  );
};

export default CreatedFields;
