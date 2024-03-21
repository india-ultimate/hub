import { createForm, required } from "@modular-forms/solid";
import { useParams } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { inboxStack, pencilSquare } from "solid-heroicons/solid";
import { createEffect, createSignal, Show } from "solid-js";

import { Spinner } from "../icons";
import { useStore } from "../store";
import { getCookie, getPlayer } from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import CollegeIDInformation from "./CollegeIDInformation";
import FileInput from "./FileInput";
import StatusStepper from "./StatusStepper";
import TextInput from "./TextInput";

const CollegeID = () => {
  const [store, { setPlayerById }] = useStore();

  const initialValues = {};
  const [_accreditationForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const [edit, setEdit] = createSignal(false);
  const [loading, setLoading] = createSignal(false);
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
    setLoading(true);
    const { card_front, card_back, ...collegeIdData } = values;
    let data = { ...collegeIdData, player_id: player()?.id };

    const formData = new FormData();
    formData.append("college_id", JSON.stringify(data));
    formData.append("card_front", card_front);
    formData.append("card_back", card_back);

    setStatus("");
    setError("");

    try {
      const response = await fetch("/api/college-id", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: formData
      });
      if (response.ok) {
        setStatus("Player College ID saved!");
        const data = await response.json();
        setPlayerById({ ...player(), college_id: data });
        setEdit(false);
      } else {
        const message = await response.text();
        setStatus(`${message}`);
      }
    } catch (error) {
      setError(`An error occurred while submitting College ID Card: ${error}`);
    }
    setLoading(false);
  };

  return (
    <div>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "College ID" }
        ]}
      />
      <Show
        when={player()}
        fallback={
          <p>
            College ID information for player {params.playerId} not accessible.
          </p>
        }
      >
        <div>
          <h1 class="text-2xl font-bold text-blue-500">
            College ID details for {player()?.full_name}
          </h1>
          <Show when={player()?.college_id && !edit()}>
            <CollegeIDInformation college_id={player()?.college_id} />
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
          <Show when={player() && (!player()?.college_id || edit())}>
            <Form
              class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
              onSubmit={values => handleSubmit(values)}
            >
              <div class="space-y-8">
                <Field
                  name="card_front"
                  type="File"
                  validate={required(
                    "Please upload your College ID Card's Front Side."
                  )}
                >
                  {(field, props) => (
                    <FileInput
                      {...props}
                      accept={"image/*"}
                      value={field.value}
                      error={field.error}
                      label="Upload College ID Card's Front Side"
                      subLabel="Note: Uploading directly from Google Drive is not supported. Please download to device and upload as a file."
                      required
                    />
                  )}
                </Field>
                <Field
                  name="card_back"
                  type="File"
                  validate={required(
                    "Please upload your College ID Card's Back Side."
                  )}
                >
                  {(field, props) => (
                    <FileInput
                      {...props}
                      accept={"image/*"}
                      value={field.value}
                      error={field.error}
                      label="Upload College ID Card's Back Side"
                      subLabel="Note: Uploading directly from Google Drive is not supported. Please download to device and upload as a file."
                      required
                    />
                  )}
                </Field>
                <Field
                  name="expiry"
                  validate={[
                    required("Please enter expiry date of College ID Card.")
                  ]}
                >
                  {(field, props) => (
                    <TextInput
                      {...props}
                      value={field.value}
                      error={field.error}
                      type="date"
                      label="Expiry Date of College ID Card"
                      required
                    />
                  )}
                </Field>
                <button
                  type="submit"
                  disabled={loading()}
                  class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
                >
                  <Show when={loading()} fallback={"Submit"}>
                    <Spinner />
                  </Show>
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

export default CollegeID;
