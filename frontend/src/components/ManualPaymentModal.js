import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/solid-mini";
import { getCookie, fetchUserData } from "../utils";
import TextInput from "./TextInput";
import { createForm, required } from "@modular-forms/solid";
import { createEffect } from "solid-js";
import QRious from "qrious";
import { useStore } from "../store";
import { upiID } from "../constants";

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

    fetch(`/api/manual-transaction/${transactionID}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      body: JSON.stringify(data),
      credentials: "same-origin"
    })
      .then(async response => {
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
          if (response.status === 422) {
            const error = await response.json();
            props.setStatus(`Error: ${error.message}`);
          } else {
            const body = await response.text();
            props.setStatus(
              `Error: ${response.statusText} (${response.status}) — ${body}`
            );
          }
        }
        modalButton.click();
      })
      .catch(error => {
        props.setStatus(`Error: ${error}`);
        modalButton.click();
      });
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
                onSubmit={values => submitTransactionDetails(values)}
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
