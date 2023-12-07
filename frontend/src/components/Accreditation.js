import { createForm, maxRange, minRange, required } from "@modular-forms/solid";
import { useParams } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { inboxStack } from "solid-heroicons/solid";
import { pencilSquare } from "solid-heroicons/solid-mini";
import { createEffect, createSignal, Show } from "solid-js";

import { accreditationChoices } from "../constants";
import { useStore } from "../store";
import { displayDate, getCookie, getPlayer } from "../utils";
import { getLabel } from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import FileInput from "./FileInput";
import Select from "./Select";
import StatusStepper from "./StatusStepper";
import TextInput from "./TextInput";

const AccreditationInformation = props => {
  const url = (
    <a href={props?.accreditation?.certificate} target="_blank">
      View Certificate
    </a>
  );
  return (
    <div class="relative overflow-x-auto">
      <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
        <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
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
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Accreditation Valid?
            </th>
            <td class="px-6 py-4">
              {props?.accreditation?.is_valid ? "Yes" : "No"}
            </td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Accreditation Date
            </th>
            <td class="px-6 py-4">{displayDate(props?.accreditation?.date)}</td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
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
    let data = { ...accreditationData, player_id: player()?.id };
    if (data.wfdf_id === "") {
      data.wfdf_id = null;
    }

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
              class="my-4 block w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
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
                    />
                  )}
                </Field>
                <div
                  class="mx-10 my-0 mb-4 rounded-lg bg-blue-50 p-4 px-8 text-sm text-blue-800 dark:bg-gray-800 dark:text-blue-400 lg:px-10"
                  role="alert"
                >
                  <details>
                    <summary>How to find my WFDF ID?</summary>
                    <ol class="mt-2 list-decimal space-y-1 pl-5 text-sm">
                      <li>
                        Login to your{" "}
                        <a
                          class="text-blue-600 underline hover:no-underline dark:text-blue-500"
                          href="https://rules.wfdf.org"
                        >
                          WFDF account
                        </a>
                      </li>
                      <li>
                        Navigate to the{" "}
                        <a
                          class="text-blue-600 underline hover:no-underline dark:text-blue-500"
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
                  class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
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
