import {
  createForm,
  getValue,
  required,
  toTrimmed
} from "@modular-forms/solid";
import { useNavigate } from "@solidjs/router";
import { createMutation } from "@tanstack/solid-query";
import { createSignal, Match, Show, Switch } from "solid-js";

import { updateTeamName } from "../../queries";
import Error from "../alerts/Error";
import Warning from "../alerts/Warning";
import TextInput from "../TextInput";

const EditTeamNameForm = props => {
  const navigate = useNavigate();
  const [error, setError] = createSignal("");

  const [editNameForm, { Form, Field }] = createForm({
    initialValues: {
      name: props.teamName
    },
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const updateTeamNameMutation = createMutation({
    mutationFn: updateTeamName,
    onSuccess: data => navigate(`/team/${data.slug}`, { replace: true }),
    onError: error => setError(error.message)
  });

  function handleSubmit(values) {
    updateTeamNameMutation.mutate({ ...values, id: props.teamId });
  }

  function editedTeamName() {
    // returns undefined if the team name is not edited
    return getValue(editNameForm, "name", {
      shouldDirty: true
    });
  }

  return (
    <>
      <Warning>
        The new team name will be shown in all past and future tournaments
      </Warning>
      <Form class="my-2" onSubmit={handleSubmit} shouldDirty={true}>
        <div class="space-y-4">
          <Field
            name="name"
            type="string"
            transform={toTrimmed({ on: "input" })}
            validate={required("Please enter a team name")}
          >
            {(field, fieldProps) => (
              <TextInput
                {...fieldProps}
                type="text"
                label="Team name"
                placeholder="Team name"
                value={field.value}
                error={field.error}
                required
                padding
              />
            )}
          </Field>
          <button
            type="submit"
            disabled={
              editedTeamName() === undefined || updateTeamNameMutation.isLoading
            }
            class="mb-2 w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white transition-all hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:bg-gray-400 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
          >
            <Switch>
              <Match when={!editedTeamName()}>Submit</Match>
              <Match
                when={editedTeamName() && !updateTeamNameMutation.isLoading}
              >
                Change name to {editedTeamName()}
              </Match>
              <Match
                when={editedTeamName() && updateTeamNameMutation.isLoading}
              >
                Updating...
              </Match>
            </Switch>
          </button>
          <Show when={error()}>
            <Error text={`Oops ! ${error()}`} />
          </Show>
        </div>
      </Form>
    </>
  );
};

export default EditTeamNameForm;
