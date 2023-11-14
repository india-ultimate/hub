import { createForm, required } from "@modular-forms/solid";
import { createMutation, createQuery } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { createSignal, Show } from "solid-js";

import { fetchTournamentTeamBySlug, updateMatch } from "../../queries";
import Select from "../Select";
import TextInput from "../TextInput";

const UpdateSpiritScoreForm = props => {
  const rosterQueryTeam1 = createQuery(
    () => [
      "tournament-roster",
      props.match?.tournament?.event?.ultimate_central_slug,
      props.match?.team_1?.ultimate_central_slug
    ],
    () =>
      fetchTournamentTeamBySlug(
        props.match?.tournament?.event?.ultimate_central_slug,
        props.match?.team_1?.ultimate_central_slug
      )
  );
  const rosterQueryTeam2 = createQuery(
    () => [
      "tournament-roster",
      props.match?.tournament?.event?.ultimate_central_slug,
      props.match?.team_2?.ultimate_central_slug
    ],
    () =>
      fetchTournamentTeamBySlug(
        props.match?.tournament?.event?.ultimate_central_slug,
        props.match?.team_2?.ultimate_central_slug
      )
  );

  const initialValues = {
    spirit_score_team_1: {
      rules: 2,
      fouls: 2,
      fair: 2,
      positive: 2,
      communication: 2
    },
    spirit_score_team_2: {
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

  const updateSpiritScoreMutation = createMutation({
    mutationFn: updateMatch,
    onSuccess: () => {
      setStatus("Updated Score!");
    },
    onError: e => {
      console.log(e);
      setError(e);
    }
  });

  const handleSubmit = async values => {
    setStatus("");
    setError("");

    updateSpiritScoreMutation.mutate({
      match_id: props?.match?.id,
      body: values
    });

    setTimeout(() => initFlowbite(), 1000);
  };

  return (
    <div>
      <Form
        class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
        onSubmit={values => handleSubmit(values)}
      >
        <div class="space-y-8">
          <h2 class="text-bold text-center text-2xl text-blue-600 dark:text-blue-500">
            {props?.match?.team_1?.name}
          </h2>
          <Field
            name="spirit_score_team_1.rules"
            validate={required("Please add rules score.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Rules Score"
                required
              />
            )}
          </Field>
          <Field
            name="spirit_score_team_1.fouls"
            validate={required("Please add fouls score.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Fouls Score"
                required
              />
            )}
          </Field>
          <Field
            name="spirit_score_team_1.fair"
            validate={required("Please add fair score.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Fair Score"
                required
              />
            )}
          </Field>
          <Field
            name="spirit_score_team_1.positive"
            validate={required("Please add positive score.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Positive Score"
                required
              />
            )}
          </Field>
          <Field
            name="spirit_score_team_1.communication"
            validate={required("Please add communication score.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Communication Score"
                required
              />
            )}
          </Field>
          <Field name="spirit_score_team_1.mvp_id">
            {(field, fieldProps) => (
              <Select
                {...fieldProps}
                value={field.value}
                error={field.error}
                options={rosterQueryTeam1.data?.map(r => {
                  return {
                    value: r.id.toString(),
                    label: r.first_name + " " + r.last_name
                  };
                })}
                type="text"
                label="MVP"
                placeholder="Choose a Player"
              />
            )}
          </Field>
          <Field name="spirit_score_team_1.msp_id">
            {(field, fieldProps) => (
              <Select
                {...fieldProps}
                value={field.value}
                error={field.error}
                options={rosterQueryTeam1.data?.map(r => {
                  return {
                    value: r.id.toString(),
                    label: r.first_name + " " + r.last_name
                  };
                })}
                type="text"
                label="MSP"
                placeholder="Choose a Player"
              />
            )}
          </Field>

          <h2 class="text-bold text-center text-2xl text-blue-600 dark:text-blue-500">
            {props?.match?.team_2?.name}
          </h2>
          <Field
            name="spirit_score_team_2.rules"
            validate={required("Please add rules score.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Rules Score"
                required
              />
            )}
          </Field>
          <Field
            name="spirit_score_team_2.fouls"
            validate={required("Please add fouls score.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Fouls Score"
                required
              />
            )}
          </Field>
          <Field
            name="spirit_score_team_2.fair"
            validate={required("Please add fair score.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Fair Score"
                required
              />
            )}
          </Field>
          <Field
            name="spirit_score_team_2.positive"
            validate={required("Please add positive score.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Positive Score"
                required
              />
            )}
          </Field>
          <Field
            name="spirit_score_team_2.communication"
            validate={required("Please add communication score.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                label="Communication Score"
                required
              />
            )}
          </Field>
          <Field name="spirit_score_team_2.mvp_id">
            {(field, fieldProps) => (
              <Select
                {...fieldProps}
                value={field.value}
                error={field.error}
                options={rosterQueryTeam2.data?.map(r => {
                  return {
                    value: r.id.toString(),
                    label: r.first_name + " " + r.last_name
                  };
                })}
                type="text"
                label="MVP"
                placeholder="Choose a Player"
              />
            )}
          </Field>
          <Field name="spirit_score_team_2.msp_id">
            {(field, fieldProps) => (
              <Select
                {...fieldProps}
                value={field.value}
                error={field.error}
                options={rosterQueryTeam2.data?.map(r => {
                  return {
                    value: r.id.toString(),
                    label: r.first_name + " " + r.last_name
                  };
                })}
                type="text"
                label="MSP"
                placeholder="Choose a Player"
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

export default UpdateSpiritScoreForm;
