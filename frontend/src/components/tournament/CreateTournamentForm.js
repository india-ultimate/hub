import { createForm, required } from "@modular-forms/solid";
import { createMutation, useQueryClient } from "@tanstack/solid-query";
import { createSignal, Show } from "solid-js";

import { tournamentTypeChoices } from "../../constants";
import { createTournament } from "../../queries";
import FileInput from "../FileInput";
import Select from "../Select";
import TextInput from "../TextInput";

const CreateTournamentForm = () => {
  const queryClient = useQueryClient();
  const createTournamentMutation = createMutation({
    mutationFn: createTournament,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tournaments"] });
      setStatus("Created Tournament!");
    },
    onError: e => {
      console.log(e);
      setError(e.toString());
    }
  });

  const initialValues = {};
  const [_tournamentForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const handleSubmit = async values => {
    const { logo_light, logo_dark, ...tournamentData } = values;
    const data = { ...tournamentData };

    const formData = new FormData();
    formData.append("tournament_details", JSON.stringify(data));
    formData.append("logo_light", logo_light);
    formData.append("logo_dark", logo_dark);

    setStatus("");
    setError("");

    createTournamentMutation.mutate(formData);
  };

  const minDate = new Date().toISOString().split("T")[0];

  return (
    <div>
      <Form
        class="mt-12 space-y-4 md:space-y-6 lg:space-y-8"
        onSubmit={values => handleSubmit(values)}
      >
        <div class="space-y-2">
          <Field
            name="title"
            validate={required("Please add the tournament name.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="text"
                label="Name of the Tournament"
                placeholder="Tournament Name"
                required
              />
            )}
          </Field>
          <Field
            name="start_date"
            validate={[
              required("Please enter the start date of the tournament.")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="date"
                min={minDate}
                label="Start Date of Tournament"
                placeholder={minDate}
                required
              />
            )}
          </Field>
          <Field
            name="end_date"
            validate={[
              required("Please enter the end date of the tournament.")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="date"
                min={minDate}
                label="End Date of Tournament"
                placeholder={minDate}
                required
              />
            )}
          </Field>
          <Field
            name="team_registration_start_date"
            validate={[
              required("Please enter the team registration start date.")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="date"
                min={minDate}
                label="Registration Start Date"
                placeholder={minDate}
                required
              />
            )}
          </Field>
          <Field
            name="team_registration_end_date"
            validate={[
              required("Please enter the team registration end date.")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="date"
                min={minDate}
                label="Registration End Date"
                placeholder={minDate}
                required
              />
            )}
          </Field>
          <Field
            name="player_registration_start_date"
            validate={[
              required("Please enter the player rostering start date.")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="date"
                min={minDate}
                label="Player Rostering Start Date"
                placeholder={minDate}
                required
              />
            )}
          </Field>
          <Field
            name="player_registration_end_date"
            validate={[required("Please enter the player rostering end date.")]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="date"
                min={minDate}
                label="Player Rostering End Date"
                placeholder={minDate}
                required
              />
            )}
          </Field>
          <Field
            name="location"
            validate={required("Please add the tournament location.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="text"
                label="Tournament Location"
                placeholder="City, State"
                required
              />
            )}
          </Field>
          <Field
            name="type"
            validate={required("Please select the tournament type.")}
          >
            {(field, props) => (
              <Select
                {...props}
                value={field.value}
                error={field.error}
                options={tournamentTypeChoices}
                type="text"
                label="Tournament Type"
                placeholder="Select type"
                required
              />
            )}
          </Field>
          <Field name="logo_light" type="File">
            {(field, fieldProps) => (
              <FileInput
                {...fieldProps}
                accept={"image/*"}
                value={field.value}
                error={field.error}
                label="Upload Logo (Light Version for Dark Background)"
              />
            )}
          </Field>
          <Field name="logo_dark" type="File">
            {(field, fieldProps) => (
              <FileInput
                {...fieldProps}
                accept={"image/*"}
                value={field.value}
                error={field.error}
                label="Upload Logo (Dark Version for Light Background)"
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
    </div>
  );
};

export default CreateTournamentForm;
