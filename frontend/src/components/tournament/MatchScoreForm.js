import { createForm, required } from "@modular-forms/solid";
import { createMutation } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { createSignal, Show } from "solid-js";

import { submitMatchScore } from "../../queries";
import Error from "../alerts/Error";
import Info from "../alerts/Info";
import TextInput from "../TextInput";

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
          class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
        >
          Submit Score
        </button>
        <Show when={error()}>
          <Error text={`Oops ! ${error()}`} />
        </Show>
        <Show when={status()}>
          <Info text={status()} />
        </Show>
      </div>
    </Form>
  );
};

export default MatchScoreForm;
