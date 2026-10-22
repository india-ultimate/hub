import { createForm, required } from "@modular-forms/solid";
import { useParams } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { inboxStack } from "solid-heroicons/solid";
import { pencilSquare } from "solid-heroicons/solid-mini";
import { createEffect, createSignal, Show } from "solid-js";

import { useStore } from "../../store";
import { withinUploadLimits } from "../../uploads";
import { getCookie, getPlayer } from "../../utils";
import Breadcrumbs from "../Breadcrumbs";
import FileInput from "../FileInput";
import StatusStepper from "../StatusStepper";
import AccreditationInformation from "./AccreditationInformation";

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

  // handleSubmit function to handle form submission
  const handleSubmit = async values => {
    const { certificate } = values;
    const data = { player_id: player()?.id };

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
                  name="certificate"
                  type="File"
                  validate={[
                    required("Please upload your accreditation certificate."),
                    withinUploadLimits
                  ]}
                >
                  {(field, props) => (
                    <FileInput
                      {...props}
                      accept={"application/pdf"}
                      value={field.value}
                      error={field.error}
                      label="Upload Accreditation Certificate (PDF)"
                      subLabel="Upload the PDF you downloaded from WFDF Academy. We read the level, dates and Certificate Code from it, and the name on it must match the player's. Certificates from the old rules.wfdf.sport site can't be added. Uploading directly from Google Drive is not supported, so download it to your device first."
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
