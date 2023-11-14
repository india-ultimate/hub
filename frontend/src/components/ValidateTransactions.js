import { createForm, required } from "@modular-forms/solid";
import { createSignal } from "solid-js";

import { getCookie } from "../utils";
import FileInput from "./FileInput";
import TransactionList from "./TransactionList";
import ValidateTransaction from "./ValidateTransaction";

const TransactionStats = props => {
  return (
    <ul>
      <li>
        Total transactions in bank statement:{" "}
        <strong>{props.data.total}</strong>
      </li>
      <li>
        Un-validated transactions found in the database:{" "}
        <strong>{props.data.invalid_found}</strong>
      </li>
      <li>
        Transactions validated: <strong>{props.data.validated}</strong>
      </li>
    </ul>
  );
};

const ValidateTransactions = () => {
  const [invalid, setInvalid] = createSignal(true);
  const [status, setStatus] = createSignal("");
  const [ts, setTs] = createSignal(new Date());

  const [transaction, setTransaction] = createSignal();

  const initialValues = {};
  const [_bankStatementForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const handleSubmit = async values => {
    const { bank_statement } = values;

    const formData = new FormData();
    formData.append("bank_statement", bank_statement);
    setStatus("");
    try {
      const response = await fetch("/api/validate-transactions", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: formData
      });
      setTs(new Date());
      if (response.ok) {
        const data = await response.json();
        setStatus(<TransactionStats data={data} />);
      } else {
        const message = await response.json();
        const text = message?.message || JSON.stringify(message);
        setStatus(`${text}`);
      }
    } catch (error) {
      setStatus(
        `An error occurred while processing transactions data: ${error}`
      );
    }
  };

  return (
    <>
      <label class="relative inline-flex cursor-pointer items-center">
        <input
          type="checkbox"
          value=""
          class="peer sr-only"
          checked={invalid()}
          onChange={() => setInvalid(!invalid())}
        />
        <div class="peer h-6 w-11 rounded-full bg-gray-200 after:absolute after:left-[2px] after:top-0.5 after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-blue-600 peer-checked:after:translate-x-full peer-checked:after:border-white peer-focus:ring-4 peer-focus:ring-blue-300 dark:border-gray-600 dark:bg-gray-700 dark:peer-focus:ring-blue-800" />
        <span class="ml-3 text-sm font-medium text-gray-900 dark:text-gray-300">
          Show only transactions yet to be validated
        </span>
      </label>
      <Form
        class="my-6 space-y-6 md:space-y-7 lg:space-y-8"
        onSubmit={values => handleSubmit(values)}
      >
        <div class="space-y-8">
          <Field
            name="bank_statement"
            type="File"
            validate={required("Please upload a bank statement.")}
          >
            {(field, props) => (
              <FileInput
                {...props}
                accept={"application/csv"}
                value={field.value}
                error={field.error}
                label="Upload Bank Statement (CSV)"
                required
              />
            )}
          </Field>
          <button
            type="submit"
            class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
          >
            Submit
          </button>
        </div>
        <p>{status()}</p>
      </Form>
      <TransactionList
        admin={true}
        onlyInvalid={invalid()}
        ts={ts()}
        setTransaction={setTransaction}
      />
      <ValidateTransaction transaction={transaction()} setTs={setTs} />
    </>
  );
};
export default ValidateTransactions;
