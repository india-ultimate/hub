import { createForm, getValue, required } from "@modular-forms/solid";
import { useParams } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { inboxStack } from "solid-heroicons/solid";
import { pencilSquare } from "solid-heroicons/solid-mini";
import { createEffect, createSignal, Match, Show, Switch } from "solid-js";

import { vaccinationChoices } from "../constants";
import { useStore } from "../store";
import { getCookie, getPlayer } from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import Checkbox from "./Checkbox";
import FileInput from "./FileInput";
import Select from "./Select";
import StatusStepper from "./StatusStepper";
import TextInput from "./TextInput";
import VaccinationInformation from "./VaccinationInformation";

const Vaccination = () => {
  const [store, { setPlayerById }] = useStore();

  const initialValues = { is_vaccinated: true };
  const [vaccinationForm, { Form, Field }] = createForm({
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
    const { certificate, ...vaccinationData } = values;
    const data = { ...vaccinationData, player_id: player()?.id };

    const formData = new FormData();
    formData.append("vaccination", JSON.stringify(data));
    formData.append("certificate", certificate);

    setStatus("");
    setError("");

    try {
      const response = await fetch("/api/vaccination", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: formData
      });
      if (response.ok) {
        setStatus("Player vaccination information saved!");
        const data = await response.json();
        setPlayerById({ ...player(), vaccination: data });
        setEdit(false);
      } else {
        const message = await response.json();
        const text = message?.message || JSON.stringify(message);
        setStatus(`${text}`);
      }
    } catch (error) {
      setError(`An error occurred while submitting vaccination data: ${error}`);
    }
  };

  return (
    <div>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Vaccination" }
        ]}
      />
      <Show
        when={player()}
        fallback={
          <p>
            Vaccination information for player {params.playerId} not accessible.
          </p>
        }
      >
        <div>
          <h1 class="text-2xl font-bold text-blue-500">
            Vaccination details for {player()?.full_name}
          </h1>
          <Show when={player()?.vaccination && !edit()}>
            <table>
              <tbody>
                <VaccinationInformation vaccination={player()?.vaccination} />
              </tbody>
            </table>
            <button
              class="my-4 block w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 sm:w-auto dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
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
          <Show when={player() && (!player()?.vaccination || edit())}>
            <Form
              class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
              onSubmit={values => handleSubmit(values)}
            >
              <div class="space-y-8">
                <Field name="is_vaccinated" type="boolean">
                  {(field, props) => (
                    <Checkbox
                      {...props}
                      checked={field.value}
                      value={field.value}
                      error={field.error}
                      label="Are you vaccinated?"
                    />
                  )}
                </Field>
                <Switch>
                  <Match when={getValue(vaccinationForm, "is_vaccinated")}>
                    <Field
                      name="name"
                      validate={required("Please select your vaccination.")}
                    >
                      {(field, props) => (
                        <Select
                          {...props}
                          value={field.value}
                          error={field.error}
                          options={vaccinationChoices}
                          type="text"
                          label="Name of the vaccination"
                          placeholder="Vaccination Name?"
                          required
                        />
                      )}
                    </Field>
                    <Field
                      name="certificate"
                      type="File"
                      validate={required(
                        "Please add your vaccination certificate."
                      )}
                    >
                      {(field, props) => (
                        <FileInput
                          {...props}
                          accept={"image/*,application/pdf"}
                          value={field.value}
                          error={field.error}
                          label="Upload Certificate"
                          required
                        />
                      )}
                    </Field>
                  </Match>
                  <Match when={!getValue(vaccinationForm, "is_vaccinated")}>
                    <Field
                      name="explain_not_vaccinated"
                      validate={required(
                        "Please add an explanation for not being vaccinated."
                      )}
                    >
                      {(field, props) => (
                        <TextInput
                          {...props}
                          value={field.value}
                          error={field.error}
                          type="text"
                          label="Reason for not being vaccinated"
                          placeholder="I have a medical condition..."
                          required
                        />
                      )}
                    </Field>
                  </Match>
                </Switch>
                <button
                  type="submit"
                  class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 sm:w-auto dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
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

export default Vaccination;
