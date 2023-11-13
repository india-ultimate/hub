import { createSignal, For } from "solid-js";
import { createForm, required } from "@modular-forms/solid";
import FileInput from "./FileInput";
import { getCookie } from "../utils";

const MembershipStatusTable = props => {
  if (!props.data || props.data.length === 0) {
    return <p>No data found in the CSV</p>;
  }

  const columns = Object.keys(props.data[0]);

  return (
    <div class="relative overflow-x-auto">
      <table class="w-full border border-gray-300 text-left text-sm">
        <thead>
          <tr>
            <For each={columns}>
              {column => <th class="bg-gray-200 px-4 py-2">{column}</th>}
            </For>
          </tr>
        </thead>
        <tbody>
          <For each={props.data}>
            {row => (
              <tr
                class={
                  row.membership_status
                    ? "bg-green-200 dark:bg-green-700"
                    : "bg-red-800 text-white"
                }
              >
                <For each={columns}>
                  {column => {
                    const value = row[column];
                    return (
                      <td class="px-4 py-2">
                        {typeof value === "boolean"
                          ? value
                            ? "Y"
                            : "N"
                          : value}
                      </td>
                    );
                  }}
                </For>
              </tr>
            )}
          </For>
        </tbody>
      </table>
    </div>
  );
};

const CheckMemberships = () => {
  const [status, setStatus] = createSignal("");
  const initialValues = {};
  const [_csvForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const handleSubmit = async values => {
    const { info_csv } = values;
    const formData = new FormData();
    formData.append("info_csv", info_csv);
    try {
      const response = await fetch("/api/check-memberships", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: formData
      });
      if (response.ok) {
        const data = await response.json();
        setStatus(<MembershipStatusTable data={data} />);
      } else {
        const message = await response.json();
        const text = message?.message || JSON.stringify(message);
        setStatus(`${text}`);
      }
    } catch (error) {
      setStatus(`An error occurred while processing membership data: ${error}`);
    }
  };

  return (
    <Form
      class="my-6 space-y-6 md:space-y-7 lg:space-y-8"
      onSubmit={values => handleSubmit(values)}
    >
      <div
        class="mb-4 rounded-lg bg-blue-50 p-4 text-sm text-blue-800 dark:bg-gray-800 dark:text-blue-400"
        role="alert"
      >
        Upload any CSV file which has 'Email' as one of the columns
      </div>

      <div class="space-y-8">
        <Field
          name="info_csv"
          type="File"
          validate={required("Please upload a CSV file.")}
        >
          {(field, props) => (
            <FileInput
              {...props}
              accept=".csv"
              value={field.value}
              error={field.error}
              label="Upload CSV File"
              required
            />
          )}
        </Field>
        <button
          type="submit"
          class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 sm:w-auto"
        >
          Submit
        </button>
      </div>
      <div class="mt-4">{status()}</div>
    </Form>
  );
};

export default CheckMemberships;
