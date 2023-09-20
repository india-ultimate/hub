import { createSignal } from "solid-js";
import { createForm, required } from "@modular-forms/solid";
import TextInput from "./TextInput";
import { getCookie } from "../utils";
import { initFlowbite } from "flowbite";

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
      setStatus(
        `An error occurred while submitting vaccination data: ${error}`
      );
    }
  };

  return (
    <div
      id="validationModal"
      tabindex="-1"
      aria-hidden="true"
      class="fixed top-0 left-0 right-0 z-50 hidden w-full p-4 overflow-x-hidden overflow-y-auto md:inset-0 h-[calc(100%-1rem)] max-h-full"
    >
      <div class="relative w-full max-w-2xl max-h-full">
        <div class="relative bg-white rounded-lg shadow dark:bg-gray-700">
          <div class="flex items-start justify-between p-4 border-b rounded-t dark:border-gray-600">
            <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
              Validate Transaction &mdash; {props.transaction?.transaction_id}
            </h3>
            <button
              type="button"
              class="text-gray-400 bg-transparent hover:bg-gray-200 hover:text-gray-900 rounded-lg text-sm w-8 h-8 ml-auto inline-flex justify-center items-center dark:hover:bg-gray-600 dark:hover:text-white"
              data-modal-hide="validationModal"
            >
              <svg
                class="w-3 h-3"
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
              <div class="flex items-center p-6 space-x-2 border-t border-gray-200 rounded-b dark:border-gray-600">
                <button
                  type="submit"
                  class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                >
                  Accept
                </button>
                <button
                  data-modal-hide="validationModal"
                  ref={closeRef}
                  type="button"
                  class="text-gray-500 bg-white hover:bg-gray-100 focus:ring-4 focus:outline-none focus:ring-blue-300 rounded-lg border border-gray-200 text-sm font-medium px-5 py-2.5 hover:text-gray-900 focus:z-10 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-500 dark:hover:text-white dark:hover:bg-gray-600 dark:focus:ring-gray-600"
                >
                  Cancel
                </button>
              </div>
            </div>
          </Form>
          <div class="flex items-center px-6 pb-6 space-x-2">{status()}</div>
        </div>
      </div>
    </div>
  );
};
export default ValidateTransaction;
