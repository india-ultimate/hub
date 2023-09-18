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
        class={`block text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 my-5 ${
          props.disabled ? "cursor-not-allowed" : ""
        }`}
        type="button"
        disabled={props.disabled}
      >
        Pay
      </button>
      <div
        id="payment-modal"
        tabindex="-1"
        aria-hidden="true"
        class="fixed top-0 left-0 right-0 z-50 hidden w-full p-4 overflow-x-hidden overflow-y-auto md:inset-0 h-[calc(100%-1rem)] max-h-full"
      >
        <div class="relative w-full max-w-md max-h-full">
          <div class="relative bg-white rounded-lg shadow dark:bg-gray-700">
            <button
              type="button"
              class="absolute top-3 right-2.5 text-gray-400 bg-transparent hover:bg-gray-200 hover:text-gray-900 rounded-lg text-sm w-8 h-8 ml-auto inline-flex justify-center items-center dark:hover:bg-gray-600 dark:hover:text-white"
              data-modal-hide="payment-modal"
            >
              <Icon path={xMark} style={{ width: "20px" }} />
              <span class="sr-only">Close modal</span>
            </button>
            <div class="px-6 py-6 lg:px-8">
              <h3 class="mb-4 text-xl font-medium text-gray-900 dark:text-white">
                Pay ₹ {props.amount} to UPAI
              </h3>
              <img ref={qrElement} />
              <div class="text-sm mb-4 space-y-4">
                <p>UPI: {upiID}</p>
                <details>
                  <summary>Bank account details</summary>
                  <ul class="pl-5">
                    <li>Account Name: Flying Disc Sports Federation (India)</li>
                    <li>Account Number: 50200061651517 </li>
                    <li>Bank & Branch: HDFC, Bank DLF-Ramapuram</li>
                    <li>IFSC: HDFC0001869</li>
                  </ul>
                </details>
              </div>
              <ol class="pl-5 mt-2 space-y-1 list-decimal text-sm">
                <li>Pay the membership fee using UPI or a Bank Transaction</li>
                <li>
                  Submit the transaction ID of your transaction. Please make
                  sure that you submit the correct Transaction ID so that your
                  payment can be validated by the UPAI Operations team.
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
                      label="Transaction ID"
                      placeholder="1234567890"
                      required
                    />
                  )}
                </Field>
                <button
                  type="submit"
                  class="w-full text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                >
                  Submit Transaction ID
                </button>
              </Form>
              <div
                class="p-4 my-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300"
                role="alert"
              >
                <details>
                  <summary>Why you no use payment gateway?</summary>
                  <p class="mt-4">
                    We've been in the process of setting up a payment gateway
                    using a service provider like Razorpay/PhonePe/etc, but
                    still have a few banking related issues to sort out. We'll
                    soon have a smoother payment experience! Thank you for your
                    patience.
                  </p>
                </details>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default ManualPaymentModal;
