import { createForm, required } from "@modular-forms/solid";
import { createMutation, createQuery } from "@tanstack/solid-query";
import { createSignal, Show } from "solid-js";

import {
  createMatchStatsEvent,
  fetchTournamentTeamBySlug
} from "../../../queries";
import Error from "../../alerts/Error";
import Info from "../../alerts/Info";
import Select from "../../Select";

const BlockForm = props => {
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const rosterQuery = createQuery(
    () => ["tournament-roster", props.tournament?.slug, props.team?.slug],
    () =>
      fetchTournamentTeamBySlug(
        props.tournament?.event?.slug,
        props.team?.slug,
        props.tournament?.use_uc_registrations
      ),
    {
      get enabled() {
        return props.tournament?.use_uc_registrations !== undefined;
      }
    }
  );

  const initialValues = {
    block_by_id: null
  };

  const [_tournamentForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const createMatchStatsEventMutation = createMutation({
    mutationFn: createMatchStatsEvent,
    onSuccess: () => {
      setStatus("Saved! You can now close this.");
    },
    onError: e => {
      console.log(e);
      setError(e);
    }
  });

  const handleSubmit = async values => {
    setStatus("");
    setError("");

    createMatchStatsEventMutation.mutate({
      match_id: props.match?.id,
      body: {
        type: "BL",
        team_id: props.team?.id,
        ...values
      }
    });
  };

  return (
    <Form
      class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
      onSubmit={values => handleSubmit(values)}
    >
      <div class="space-y-8">
        <Field
          name="block_by_id"
          validate={required("Please add the player who blocked.")}
        >
          {(field, fieldProps) => (
            <Select
              {...fieldProps}
              value={field.value}
              error={field.error}
              options={rosterQuery.data?.map(r => {
                return {
                  value: props.tournament?.use_uc_registrations
                    ? r.person.id.toString()
                    : r.player.id.toString(),
                  label: props.tournament?.use_uc_registrations
                    ? r.person.first_name + " " + r.person.last_name
                    : r.player.full_name
                };
              })}
              required
              type="text"
              label="Block By"
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
          <Error text={`Oops ! ${error()}`} />
        </Show>
        <Show when={status()}>
          <Info text={status()} />
        </Show>
      </div>
    </Form>
  );
};

export default BlockForm;
