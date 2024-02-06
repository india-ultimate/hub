import {
  createForm,
  custom,
  required,
  reset,
  toTrimmed
} from "@modular-forms/solid";
import {
  createEffect,
  createMemo,
  createSignal,
  For,
  onCleanup,
  Show
} from "solid-js";

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

  const initialFieldName = createMemo(() => componentProps.initialValues.name);

  const otherFieldNames = createMemo(() => {
    return componentProps.alreadyPresentFields
      ?.filter(field => field.name !== initialFieldName())
      .map(field => field.name.toLowerCase());
  });

  const uniqueFieldName = name =>
    !otherFieldNames().includes(name.toLowerCase());

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
            validate={[
              required("Please enter a name for the field"),
              custom(uniqueFieldName, "There is another field with this name !")
            ]}
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
            class="w-fit rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:bg-gray-400 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 disabled:dark:bg-gray-400 sm:w-auto"
            disabled={componentProps.disabled}
          >
            <Show when={componentProps.isMutating} fallback="Edit Field">
              Updating...
            </Show>
          </button>
        </Form>
      </div>
    </div>
  );
};

const CreatedFields = props => {
  let modalRef;
  let secondsLeftInterval, modalCloseTimeout;
  const closeDelaySec = 4;

  const [editingField, setEditingField] = createSignal();
  const [editStatus, setEditStatus] = createSignal("");
  const [secsLeftToClose, setSecsLeftToClose] = createSignal(closeDelaySec);

  // Directly using props.fields breaks the dialog's focus
  // when focus comes back to the page,
  const [fields, setFields] = createSignal();
  // Storing the fields in another signal seems to fix this
  createEffect(() => {
    setFields(props.fields);
  });

  /**
   * @param {string} statusMessage
   */
  function setupDelayedModalClose(statusMessage) {
    setEditStatus(statusMessage);

    secondsLeftInterval = setInterval(() => {
      setSecsLeftToClose(prev => prev - 1);
    }, 1 * 1000);

    modalCloseTimeout = setTimeout(handleEditClose, closeDelaySec * 1000);
  }

  function resetModalStatus() {
    setEditStatus("");
    clearInterval(secondsLeftInterval);
    clearTimeout(modalCloseTimeout);
    setSecsLeftToClose(closeDelaySec);
  }

  function handleEditClick(field) {
    setEditingField(field);
    modalRef.showModal();
  }

  function handleEditClose() {
    modalRef.close();
    resetModalStatus();
    setEditingField();
  }

  function handleEditSubmit(editedValues) {
    resetModalStatus();

    if (Object.keys(editedValues).length === 0) {
      return;
    }

    props.updateFieldMutation.mutate({
      field_id: editingField().id,
      body: { ...editedValues, tournament_id: props.tournamentId }
    });
  }

  // the modal is closed with a delay once the mutation completes
  createEffect(function onMutationComplete() {
    if (props.updateFieldMutation.isSuccess) {
      setupDelayedModalClose("✅ Updated");
    }
    if (props.updateFieldMutation.isError) {
      setupDelayedModalClose(`❌ ${props.updateFieldMutation.error.message}`);
    }
  });

  onCleanup(resetModalStatus);

  return (
    <div class="my-4 grid grid-cols-3 gap-4">
      {/* Using the fields signal to avoid the dialog focus issues */}
      <For each={fields()}>
        {field => (
          <div>
            <div class="relative overflow-x-auto rounded-md">
              <div class="flex w-full items-center justify-between bg-gray-300 p-4 text-left text-lg font-semibold text-gray-900 rtl:text-right dark:bg-gray-700 dark:text-white">
                <span>{field.name}</span>
                <button
                  type="button"
                  class="rounded-lg bg-yellow-400 px-4 py-1.5 text-sm font-medium text-white hover:bg-yellow-500 focus:outline-none focus:ring-4 focus:ring-yellow-300 disabled:bg-gray-400 dark:text-gray-800 dark:focus:ring-yellow-500 disabled:dark:bg-gray-400"
                  onClick={() => handleEditClick(field)}
                  disabled={props.editingDisabled}
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
            <span class="mr-1 font-normal">Editing - </span>
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
            isMutating={props.updateFieldMutation.isLoading}
            alreadyPresentFields={fields()}
          />
          <div class="my-2">
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
