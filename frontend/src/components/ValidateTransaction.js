import { createForm, required } from "@modular-forms/solid";
import { createSignal } from "solid-js";

import { getCookie } from "../utils";
import Modal from "./Modal";
import TextInput from "./TextInput";

const ValidateTransaction = props => {
  const [status, setStatus] = createSignal("");

  const initialValues = {};
  const [_validationForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  let dialog;

  const handleSubmit = async values => {
    const data = {
      ...values,
      transaction_id: props.transaction.transaction_id
    };
    try {
      const response = await fetch("/api/transactions/validate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify(data),
        credentials: "same-origin"
      });
      if (response.ok) {
        setStatus("Successfully validated transaction! 🎉");
        props.setTs(new Date());
        setTimeout(() => {
          dialog.close();
          setStatus("");
        }, 500);
      } else {
        const message = await response.json();
        const text = message?.message || JSON.stringify(message);
        setStatus(`${text}`);
      }
    } catch (error) {
      setStatus(`An error occurred while validating transaction: ${error}`);
    }
  };

  return (
    <Modal
      ref={el => {
        dialog = el;
        props.ref?.(el);
      }}
      fullWidth
      flush
      title={
        <span class="font-semibold">
          Validate Transaction &mdash; {props.transaction?.transaction_id}
        </span>
      }
    >
      <Form class="space-y-4" onSubmit={values => handleSubmit(values)}>
        <Field
          name="validation_comment"
          validate={required("Enter a comment for validation.")}
        >
          {(field, props) => (
            <TextInput
              {...props}
              value={field.value}
              error={field.error}
              type="text"
              label="Type comment for validation"
              required
            />
          )}
        </Field>
        <div class="flex items-center gap-2">
          <button
            type="submit"
            class="min-h-[44px] rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          >
            Accept
          </button>
          <button
            type="button"
            onClick={() => dialog.close()}
            class="min-h-[44px] rounded-lg border border-gray-200 bg-white px-5 py-2.5 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-900 focus:z-10 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:border-gray-500 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-600"
          >
            Cancel
          </button>
        </div>
        <p role="status" class="text-sm">
          {status()}
        </p>
      </Form>
    </Modal>
  );
};
export default ValidateTransaction;
