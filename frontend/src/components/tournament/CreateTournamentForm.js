import { createForm, required } from "@modular-forms/solid";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { createEffect, createSignal, Show } from "solid-js";

import { createTournament, fetchEvents } from "../../queries";
import FileInput from "../FileInput";
import Select from "../Select";

const CreateTournamentForm = () => {
  const queryClient = useQueryClient();
  const eventsQuery = createQuery(() => ["events"], fetchEvents);
  const createTournamentMutation = createMutation({
    mutationFn: createTournament,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tournaments"] });
      setStatus("Created Tournament!");
    },
    onError: e => {
      console.log(e);
      setError(e);
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
  const [eventOptions, setEventOptions] = createSignal([]);

  createEffect(() => {
    setEventOptions(
      eventsQuery.data?.map(e => {
        return { value: e.id.toString(), label: e.title };
      })
    );
    console.log(eventOptions());
  });

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

  return (
    <div>
      <Form
        class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
        onSubmit={values => handleSubmit(values)}
      >
        <div class="space-y-8">
          <Field
            name="event_id"
            validate={required(
              "Please select the event to create tournament for."
            )}
          >
            {(field, fieldProps) => (
              <Select
                {...fieldProps}
                value={field.value}
                error={field.error}
                options={eventOptions()}
                type="text"
                label="Event Name"
                placeholder="Choose an Event"
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
    </div>
  );
};

export default CreateTournamentForm;
