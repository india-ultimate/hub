import { createForm, custom, maxLength, required } from "@modular-forms/solid";
import { createMutation, createQuery } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { createSignal, Show } from "solid-js";

import {
  fetchTournamentTeamBySlug,
  submitMatchSpiritScore
} from "../../queries";
import Select from "../Select";
import TextInput from "../TextInput";

const MatchSpiritScoreForm = componentProps => {
  const initialValues = {
    opponent: {
      rules: 2,
      fouls: 2,
      fair: 2,
      positive: 2,
      communication: 2
    },
    self: {
      rules: 2,
      fouls: 2,
      fair: 2,
      positive: 2,
      communication: 2
    }
  };

  const [_tournamentForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const oppRosterQuery = createQuery(
    () => [
      "tournament-roster",
      componentProps.tournamentSlug,
      componentProps.match[`team_${componentProps.oppTeamNo}`].slug
    ],
    () =>
      fetchTournamentTeamBySlug(
        componentProps.tournamentSlug,
        componentProps.match[`team_${componentProps.oppTeamNo}`].slug
      )
  );

  const submitSpiritScoreMutation = createMutation({
    mutationFn: submitMatchSpiritScore,
    onSuccess: () => {
      setStatus("Updated Spirit Score!");
    },
    onError: e => {
      console.log(e);
      setError(e);
    }
  });

  const handleSubmit = async values => {
    setStatus("");
    setError("");

    submitSpiritScoreMutation.mutate({
      match_id: componentProps?.match?.id,
      team_id: componentProps?.match[`team_${componentProps.curTeamNo}`].id,
      body: values
    });

    setTimeout(() => initFlowbite(), 1000);
  };

  const isValidScore = score => {
    return score >= 0 && score <= 4;
  };

  return (
    <div>
      <Form
        class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
        onSubmit={values => handleSubmit(values)}
      >
        <div class="space-y-8">
          <h2 class="text-bold text-center text-2xl text-blue-600 dark:text-blue-500">
            {componentProps.match[`team_${componentProps.oppTeamNo}`].name}
          </h2>
          <Field
            name="opponent.rules"
            validate={[
              required("Please add Rules Knowledge and Use score."),
              custom(isValidScore, "Please enter a score between 0 to 4")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Rules Knowledge and Use"
                required
              />
            )}
          </Field>
          <Field
            name="opponent.fouls"
            validate={[
              required("Please add Fouls and Body Contact score."),
              custom(isValidScore, "Please enter a score between 0 to 4")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Fouls and Body Contact"
                required
              />
            )}
          </Field>
          <Field
            name="opponent.fair"
            validate={[
              required("Please add Fair-Mindedness score."),
              custom(isValidScore, "Please enter a score between 0 to 4")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Fair-Mindedness"
                required
              />
            )}
          </Field>
          <Field
            name="opponent.positive"
            validate={[
              required("Please add Positive Attitude and Self-Control score."),
              custom(isValidScore, "Please enter a score between 0 to 4")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Positive Attitude and Self-Control"
                required
              />
            )}
          </Field>
          <Field
            name="opponent.communication"
            validate={[
              required("Please add Communication score."),
              custom(isValidScore, "Please enter a score between 0 to 4")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Communication"
                required
              />
            )}
          </Field>
          <Field name="opponent.mvp_id">
            {(field, fieldProps) => (
              <Select
                {...fieldProps}
                value={field.value}
                error={field.error}
                options={oppRosterQuery.data?.map(r => {
                  return {
                    value: r.person.id.toString(),
                    label: r.person.first_name + " " + r.person.last_name
                  };
                })}
                type="text"
                label="MVP"
                placeholder="Choose a Player"
              />
            )}
          </Field>
          <Field name="opponent.msp_id">
            {(field, fieldProps) => (
              <Select
                {...fieldProps}
                value={field.value}
                error={field.error}
                options={oppRosterQuery.data?.map(r => {
                  return {
                    value: r.person.id.toString(),
                    label: r.person.first_name + " " + r.person.last_name
                  };
                })}
                type="text"
                label="MSP"
                placeholder="Choose a Player"
              />
            )}
          </Field>

          <h2 class="text-bold text-center text-2xl text-blue-600 dark:text-blue-500">
            Self Score
            <br />(
            {componentProps.match[`team_${componentProps.curTeamNo}`].name})
          </h2>
          <Field
            name="self.rules"
            validate={[
              required("Please add Rules Knowledge and Use (self) score."),
              custom(isValidScore, "Please enter a score between 0 to 4")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Rules Knowledge and Use (self)"
                required
              />
            )}
          </Field>
          <Field
            name="self.fouls"
            validate={[
              required("Please add Fouls and Body Contact (self) score."),
              custom(isValidScore, "Please enter a score between 0 to 4")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Fouls and Body Contact (self)"
                required
              />
            )}
          </Field>
          <Field
            name="self.fair"
            validate={[
              required("Please add Fair-Mindedness (self) score."),
              custom(isValidScore, "Please enter a score between 0 to 4")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Fair-Mindedness (self)"
                required
              />
            )}
          </Field>
          <Field
            name="self.positive"
            validate={[
              required(
                "Please add Positive Attitude and Self-Control (self) score."
              ),
              custom(isValidScore, "Please enter a score between 0 to 4")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Positive Attitude and Self-Control (self)"
                required
              />
            )}
          </Field>
          <Field
            name="self.communication"
            validate={[
              required("Please add Communication (self) score."),
              custom(isValidScore, "Please enter a score between 0 to 4")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Communication (self)"
                required
              />
            )}
          </Field>
          <Field
            name="self.comments"
            validate={maxLength(400, "Maximum length is 400 characters")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                label="Comments(if any)"
              />
            )}
          </Field>
          <button
            type="submit"
            class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
          >
            Submit
          </button>
          <Show when={error()}>
            <p class="my-2 text-sm text-red-600 dark:text-red-500">
              <span class="font-medium">Oops!</span> {error()}
            </p>
          </Show>
          <p>{status()}</p>
        </div>
      </Form>
    </div>
  );
};

export default MatchSpiritScoreForm;
