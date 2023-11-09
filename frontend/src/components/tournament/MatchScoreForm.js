import { createForm, required } from "@modular-forms/solid";
import { createSignal, Show } from "solid-js";
import { initFlowbite } from "flowbite";
import TextInput from "../TextInput";
import { createMutation } from "@tanstack/solid-query";
import { submitMatchScore } from "../../queries";

const MatchScoreForm = componentProps => {
  const initialValues = {
    team_1_score: null,
    team_2_score: null
  };

  const [_tournamentForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const submitMatchScoreMutation = createMutation({
    mutationFn: submitMatchScore,
    onSuccess: () => {
      setStatus("Updated Match Score... Thanks!");
      setTimeout(() => initFlowbite(), 10000);
    },
    onError: e => {
      console.log(e);
      setError(e);
    }
  });

  const handleSubmit = async values => {
    setStatus("");
    setError("");

    submitMatchScoreMutation.mutate({
      match_id: componentProps?.match?.id,
      body: values
    });

    setTimeout(() => initFlowbite(), 1000);
  };

  return (
    <Form
      class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
      onSubmit={values => handleSubmit(values)}
    >
      <div class="space-y-8">
        <Field
          name={`team_${componentProps.currTeamNo}_score`}
          validate={required("Please add the team's score.")}
        >
          {(field, props) => (
            <TextInput
              {...props}
              value={field.value}
              error={field.error}
              type="number"
              label={
                componentProps.match[`team_${componentProps.currTeamNo}`].name
              }
              required
            />
          )}
        </Field>
        <Field
          name={`team_${componentProps.oppTeamNo}_score`}
          validate={required("Please add the team's score.")}
        >
          {(field, props) => (
            <TextInput
              {...props}
              value={field.value}
              error={field.error}
              type="number"
              label={
                componentProps.match[`team_${componentProps.oppTeamNo}`].name
              }
              required
            />
          )}
        </Field>
        <button
          type="submit"
          class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
        >
          Submit Score
        </button>
        <Show when={error()}>
          <p class="my-2 text-sm text-red-600 dark:text-red-500">
            <span class="font-medium">Oops!</span> {error()}
          </p>
        </Show>
        <p>{status()}</p>
      </div>
    </Form>
  );
};

export default MatchScoreForm;
