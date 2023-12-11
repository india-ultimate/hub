import { createForm, required } from "@modular-forms/solid";
import QRious from "qrious";
import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/solid-mini";
import { createEffect } from "solid-js";

import { upiID } from "../constants";
import { useStore } from "../store";
import { fetchUserData, getCookie } from "../utils";
import TextInput from "./TextInput";

const ManualPaymentModal = props => {
  const initialValues = {};

  const [_form, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const [_, { userFetchSuccess, userFetchFailure }] = useStore();

  let modalButton;

  const submitTransactionDetails = values => {
    const player_id = props?.player_id;
    const player_ids = props?.player_ids;
    const year = props.year;
    const event_id = props?.event?.id;
    const data = props.annual
      ? player_ids
        ? { player_ids, year }
        : { player_id, year }
      : { player_id, event_id };
    const transactionID = values["transaction-id"];

    // NOTE: Not sure why this function needs so many eslint-disables, while a
    // similar function in PhonePePayment works just fine... this function is
    // inside an onSubmit handler for modular forms, while the one in
    // PhonePePayment is in an onClick handler. 🤷
    const handleResponse = async response => {
      // eslint-disable-next-line solid/reactivity
      if (response.ok) {
        fetchUserData(userFetchSuccess, userFetchFailure);
        if (props.successCallback) {
          props.successCallback();
        }
        props.setStatus(
          <span class="text-green-500 dark:text-green-400">
            Payment successfully completed! 🎉
          </span>
        );
      } else {
        // eslint-disable-next-line solid/reactivity
        if (response.status === 422) {
          // eslint-disable-next-line solid/reactivity
          const error = await response.json();
          props.setStatus(`Error: ${error.message}`);
        } else {
          // eslint-disable-next-line solid/reactivity
          const body = await response.text();
          props.setStatus(
            // eslint-disable-next-line solid/reactivity
            `Error: ${response.statusText} (${response.status}) — ${body}`
          );
        }
      }
      modalButton.click();
    };

    const handleError = error => {
      props.setStatus(`Error: ${error}`);
      modalButton.click();
    };

    fetch(`/api/manual-transaction/${transactionID}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      body: JSON.stringify(data),
      credentials: "same-origin"
    })
      .then(handleResponse)
      .catch(handleError);
  };

  let qrElement;

  createEffect(() => {
    if (!qrElement) {
      return;
    }
    const amount = props.amount;
    const upiUrl = `upi://pay?pa=${upiID}&am=${amount}&cu=INR`;
    // Create qrcode
    new QRious({
      element: qrElement,
      size: 400,
      value: upiUrl
    });
  });

  return (
    <>
      <button
        ref={modalButton}
        data-modal-target="payment-modal"
        data-modal-toggle="payment-modal"
        class={`my-5 block rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 ${
          props.disabled ? "cursor-not-allowed" : ""
        }`}
        type="button"
        disabled={props.disabled}
      >
        Record Transaction
      </button>
      <div
        id="payment-modal"
        tabindex="-1"
        aria-hidden="true"
        class="fixed left-0 right-0 top-0 z-50 hidden h-[calc(100%-1rem)] max-h-full w-full overflow-y-auto overflow-x-hidden p-4 md:inset-0"
      >
        <div class="relative max-h-full w-full max-w-md">
          <div class="relative rounded-lg bg-white shadow dark:bg-gray-700">
            <button
              type="button"
              class="absolute right-2.5 top-3 ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-transparent text-sm text-gray-400 hover:bg-gray-200 hover:text-gray-900 dark:hover:bg-gray-600 dark:hover:text-white"
              data-modal-hide="payment-modal"
            >
              <Icon path={xMark} style={{ width: "20px" }} />
              <span class="sr-only">Close modal</span>
            </button>
            <div class="px-6 py-6 lg:px-8">
              <h3 class="mb-4 text-xl font-medium text-gray-900 dark:text-white">
                Pay ₹ {props.amount} to India Ultimate
              </h3>
              <img ref={qrElement} />
              <div class="mb-4 space-y-4 text-sm">
                <ul>
                  <li>
                    UPI: <span class="font-bold">{upiID}</span>
                  </li>
                  <li>
                    Amount: <span class="font-bold">₹ {props.amount}</span>
                  </li>
                </ul>
                <details>
                  <summary>Bank account details</summary>
                  <ul class="pl-5">
                    <li>
                      Account Name:{" "}
                      <span class="font-bold">
                        Flying Disc Sports Federation (India)
                      </span>
                    </li>
                    <li>
                      Account Number:{" "}
                      <span class="font-bold">50200061651517</span>{" "}
                    </li>
                    <li>
                      IFSC: <span class="font-bold">HDFC0001869</span>
                    </li>
                    <li>
                      Bank & Branch:{" "}
                      <span class="font-bold">HDFC Bank, DLF-Ramapuram</span>
                    </li>
                  </ul>
                </details>
              </div>
              <ol class="mt-2 list-decimal space-y-1 pl-5 text-sm">
                <li>Pay the membership fee using UPI or a Bank Transaction</li>
                <li>
                  Submit the UPI transaction ID of your transaction. Please make
                  sure that you submit the correct Transaction ID so that your
                  payment can be validated by the India Ultimate Operations
                  team.
                </li>
              </ol>
              <Form
                class="mt-4 space-y-4 md:space-y-4 lg:space-y-6"
                onSubmit={submitTransactionDetails}
              >
                <Field
                  name="transaction-id"
                  validate={required("Please enter the Transaction ID.")}
                >
                  {(field, props) => (
                    <TextInput
                      {...props}
                      value={field.value}
                      error={field.error}
                      type="text"
                      label="UPI Transaction ID"
                      placeholder="1234567890"
                      required
                    />
                  )}
                </Field>
                <button
                  type="submit"
                  class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                >
                  Submit UPI Transaction ID
                </button>
              </Form>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default ManualPaymentModal;
