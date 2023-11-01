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
      <table class="w-full text-sm text-left border border-gray-300">
        <thead>
          <tr>
            <For each={columns}>
              {column => <th class="py-2 px-4 bg-gray-200">{column}</th>}
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
                    : "text-white bg-red-800"
                }
              >
                <For each={columns}>
                  {column => {
                    const value = row[column];
                    return (
                      <td class="py-2 px-4">
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
          class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center"
        >
          Submit
        </button>
      </div>
      <div class="mt-4">{status()}</div>
    </Form>
  );
};

export default CheckMemberships;
