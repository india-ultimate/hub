import {
  createForm,
  custom,
  required,
  reset,
  toTrimmed
} from "@modular-forms/solid";

import Checkbox from "../Checkbox";
import TextInput from "../TextInput";

const CreateFieldForm = componentProps => {
  const [fieldsForm, { Form, Field }] = createForm({
    validateOn: "blur",
    revalidateOn: "touched"
  });

  const handleSubmit = async values => {
    componentProps.createFieldMutation.mutate({
      tournament_id: componentProps.tournamentId,
      body: values
    });
    reset(fieldsForm);
  };

  const uniqueFieldName = name => {
    const alreadyPresentFieldNames = componentProps.alreadyPresentFields.map(
      field => field.name.toLowerCase()
    );
    return !alreadyPresentFieldNames.includes(name.toLowerCase());
  };

  return (
    <div>
      <div class="w-fit rounded-lg bg-gray-200 p-6 dark:bg-gray-700/50">
        <Form onSubmit={handleSubmit}>
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
          <Field
            name="address"
            type="string"
            transform={toTrimmed({ on: "input" })}
          >
            {(field, props) => (
              <TextInput
                {...props}
                type="text"
                label="Field Address"
                placeholder="KG Farms"
                value={field.value}
                error={field.error}
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
            class="w-fit rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 disabled:dark:bg-gray-400 sm:w-auto"
            disabled={componentProps.disabled}
          >
            Create Field
          </button>
        </Form>
      </div>
    </div>
  );
};

export default CreateFieldForm;
