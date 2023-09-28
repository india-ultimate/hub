import { useStore } from "../store";
import { useParams } from "@solidjs/router";
import { createSignal, createEffect, Show } from "solid-js";
import { accreditationChoices } from "../constants";
import { getCookie, getPlayer, displayDate } from "../utils";
import { createForm, required, maxRange, minRange } from "@modular-forms/solid";
import StatusStepper from "./StatusStepper";
import TextInput from "./TextInput";
import Select from "./Select";
import FileInput from "./FileInput";
import { Icon } from "solid-heroicons";
import { pencilSquare } from "solid-heroicons/solid-mini";
import Breadcrumbs from "./Breadcrumbs";
import { inboxStack } from "solid-heroicons/solid";
import { getLabel } from "../utils";

const AccreditationInformation = props => {
  const url = (
    <a href={props?.accreditation?.certificate} target="_blank">
      View Certificate
    </a>
  );
  return (
    <div class="relative overflow-x-auto">
      <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
        <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
          <tr>
            <th scope="col" class="px-6 py-3">
              Accreditation Level
            </th>
            <th scope="col" class="px-6 py-3">
              {getLabel(accreditationChoices, props?.accreditation?.level)}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Accreditation Valid?
            </th>
            <td class="px-6 py-4">
              {props?.accreditation?.is_valid ? "Yes" : "No"}
            </td>
          </tr>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Accreditation Date
            </th>
            <td class="px-6 py-4">{displayDate(props?.accreditation?.date)}</td>
          </tr>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Accreditation Certificate
            </th>
            <td class="px-6 py-4">{url}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

const Accreditation = () => {
  const [store, { setPlayerById }] = useStore();

  const initialValues = {};
  const [_accreditationForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const [edit, setEdit] = createSignal(false);
  const [player, setPlayer] = createSignal();
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const params = useParams();
  createEffect(() => {
    const player = getPlayer(store.data, Number(params.playerId));
    setPlayer(player);
  });

  const maxDate = new Date().toISOString().split("T")[0];

  // handleSubmit function to handle form submission
  const handleSubmit = async values => {
    const { certificate, ...accreditationData } = values;
    const data = { ...accreditationData, player_id: player()?.id };

    const formData = new FormData();
    formData.append("accreditation", JSON.stringify(data));
    formData.append("certificate", certificate);

    setStatus("");
    setError("");

    try {
      const response = await fetch("/api/accreditation", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: formData
      });
      if (response.ok) {
        setStatus("Player accreditation information saved!");
        const data = await response.json();
        setPlayerById({ ...player(), accreditation: data });
        setEdit(false);
      } else {
        const message = await response.json();
        const text = message?.message || JSON.stringify(message);
        setStatus(`${text}`);
      }
    } catch (error) {
      setError(
        `An error occurred while submitting accreditation data: ${error}`
      );
    }
  };

  return (
    <div>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Accreditation" }
        ]}
      />
      <Show
        when={player()}
        fallback={
          <p>
            Accreditation information for player {params.playerId} not
            accessible.
          </p>
        }
      >
        <div>
          <h1 class="text-2xl font-bold text-blue-500">
            Accreditation details for {player()?.full_name}
          </h1>
          <Show when={player()?.accreditation && !edit()}>
            <table>
              <tbody>
                <AccreditationInformation
                  accreditation={player()?.accreditation}
                />
              </tbody>
            </table>
            <button
              class="block my-4 text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
              onClick={() => setEdit(!edit())}
            >
              <Icon
                path={pencilSquare}
                style={{ width: "20px", display: "inline" }}
              />{" "}
              Edit
            </button>
            <StatusStepper player={player()} />
          </Show>
          <Show when={player() && (!player()?.accreditation || edit())}>
            <Form
              class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
              onSubmit={values => handleSubmit(values)}
            >
              <div class="space-y-8">
                <Field
                  name="level"
                  validate={required("Please select your accreditation level.")}
                >
                  {(field, props) => (
                    <Select
                      {...props}
                      value={field.value}
                      error={field.error}
                      options={accreditationChoices}
                      type="text"
                      label="Accreditation level"
                      placeholder="Standard/Advanced?"
                      required
                    />
                  )}
                </Field>
                <Field
                  name="certificate"
                  type="File"
                  validate={required(
                    "Please upload your accreditation certificate."
                  )}
                >
                  {(field, props) => (
                    <FileInput
                      {...props}
                      accept={"image/*,application/pdf"}
                      value={field.value}
                      error={field.error}
                      label="Upload Accreditation Certificate"
                      required
                    />
                  )}
                </Field>
                <Field
                  name="date"
                  validate={[required("Please enter date of accreditation.")]}
                >
                  {(field, props) => (
                    <TextInput
                      {...props}
                      value={field.value}
                      error={field.error}
                      type="date"
                      max={maxDate}
                      label="Date of Accreditation"
                      placeholder={maxDate}
                      required
                    />
                  )}
                </Field>
                <Field
                  name="wfdf_id"
                  validate={[
                    required("Please enter WFDF User ID."),
                    minRange(1, "Enter a valid WFDF ID"),
                    maxRange(99999999, "Enter a valid WFDF ID")
                  ]}
                >
                  {(field, props) => (
                    <TextInput
                      {...props}
                      value={field.value}
                      error={field.error}
                      type="text"
                      label="WFDF User ID"
                      placeholder="99999"
                      required
                    />
                  )}
                </Field>
                <div
                  class="mx-10 my-0 px-8 lg:px-10 p-4 mb-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400"
                  role="alert"
                >
                  <details>
                    <summary>How to find my WFDF ID?</summary>
                    <ol class="pl-5 mt-2 space-y-1 list-decimal text-sm">
                      <li>
                        Login to your{" "}
                        <a
                          class="text-blue-600 underline dark:text-blue-500 hover:no-underline"
                          href="https://rules.wfdf.org"
                        >
                          WFDF account
                        </a>
                      </li>
                      <li>
                        Navigate to the{" "}
                        <a
                          class="text-blue-600 underline dark:text-blue-500 hover:no-underline"
                          href="https://rules.wfdf.org/my-results"
                        >
                          "My Results"
                        </a>{" "}
                        page
                      </li>
                      <li>
                        Click on "My Account" in the top nav-bar and copy the
                        User ID displayed!
                      </li>
                    </ol>
                  </details>
                </div>
                <button
                  type="submit"
                  class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                >
                  Submit
                </button>
              </div>
            </Form>
            <Show when={error()}>
              <p class="my-2 text-sm text-red-600 dark:text-red-500">
                <span class="font-medium">Oops!</span> {error()}
              </p>
            </Show>
            <p>{status()}</p>
          </Show>
        </div>
      </Show>
    </div>
  );
};

export default Accreditation;
