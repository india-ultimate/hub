import { createForm, required } from "@modular-forms/solid";
import { initFlowbite } from "flowbite";
import { createSignal } from "solid-js";

import { getCookie } from "../utils";
import TextInput from "./TextInput";

const ValidateTransaction = props => {
  const [status, setStatus] = createSignal("");

  const initialValues = {};
  const [_validationForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  let closeRef;

  const handleSubmit = async values => {
    const data = {
      ...values,
      transaction_id: props.transaction.transaction_id
    };
    try {
      const response = await fetch("/api/validate-transaction", {
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
          closeRef.click();
          setStatus("");
          initFlowbite();
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
    <div
      id="validationModal"
      tabindex="-1"
      aria-hidden="true"
      class="fixed left-0 right-0 top-0 z-50 hidden h-[calc(100%-1rem)] max-h-full w-full overflow-y-auto overflow-x-hidden p-4 md:inset-0"
    >
      <div class="relative max-h-full w-full max-w-2xl">
        <div class="relative rounded-lg bg-white shadow dark:bg-gray-700">
          <div class="flex items-start justify-between rounded-t border-b p-4 dark:border-gray-600">
            <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
              Validate Transaction &mdash; {props.transaction?.transaction_id}
            </h3>
            <button
              type="button"
              class="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-transparent text-sm text-gray-400 hover:bg-gray-200 hover:text-gray-900 dark:hover:bg-gray-600 dark:hover:text-white"
              data-modal-hide="validationModal"
            >
              <svg
                class="h-3 w-3"
                aria-hidden="true"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 14 14"
              >
                <path
                  stroke="currentColor"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="m1 1 6 6m0 0 6 6M7 7l6-6M7 7l-6 6"
                />
              </svg>
              <span class="sr-only">Close modal</span>
            </button>
          </div>
          <Form
            class="my-6 space-y-6 md:space-y-7 lg:space-y-8"
            onSubmit={values => handleSubmit(values)}
          >
            <div class="space-y-8">
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
              <div class="flex items-center space-x-2 rounded-b border-t border-gray-200 p-6 dark:border-gray-600">
                <button
                  type="submit"
                  class="rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                >
                  Accept
                </button>
                <button
                  data-modal-hide="validationModal"
                  ref={closeRef}
                  type="button"
                  class="rounded-lg border border-gray-200 bg-white px-5 py-2.5 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-900 focus:z-10 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:border-gray-500 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-600"
                >
                  Cancel
                </button>
              </div>
            </div>
          </Form>
          <div class="flex items-center space-x-2 px-6 pb-6">{status()}</div>
        </div>
      </div>
    </div>
  );
};
export default ValidateTransaction;
