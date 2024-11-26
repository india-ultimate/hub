import { createForm, required } from "@modular-forms/solid";
import { createMutation, useQueryClient } from "@tanstack/solid-query";
import { bookOpen } from "solid-heroicons/solid";
import { createSignal, Show } from "solid-js";

import { matchCardColorToButtonStyles } from "../../../colors";
import { genderRatio } from "../../../constants";
import { createMatchStats } from "../../../queries";
import { getMatchCardColor } from "../../../utils";
import ButtonWithModal from "../../modal/ButtonWithModal";
import Select from "../../Select";

const CreateForm = componentProps => {
  const initialValues = {};
  const [_tournamentForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const createMatchStatsMutation = createMutation({
    mutationFn: createMatchStats,
    onSuccess: () => {
      setStatus("Created Stats");
    },
    onError: e => {
      console.log(e);
      setError(e);
    }
  });

  const handleSubmit = async values => {
    setStatus("");
    setError("");

    createMatchStatsMutation.mutate({
      match_id: componentProps?.match?.id,
      body: values
    });
  };

  return (
    <div>
      <Form
        class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
        onSubmit={values => handleSubmit(values)}
      >
        <div class="space-y-8">
          <Field
            name="initial_possession_team_id"
            validate={required("Please select the team starting on Offense.")}
          >
            {(field, fieldProps) => (
              <Select
                {...fieldProps}
                value={field.value}
                error={field.error}
                options={[
                  {
                    label: componentProps?.match?.team_1?.name,
                    value: componentProps?.match?.team_1?.id
                  },
                  {
                    label: componentProps?.match?.team_2?.name,
                    value: componentProps?.match?.team_2?.id
                  }
                ]}
                type="text"
                label="Team starting on Offense"
                placeholder="Choose a team"
                required
              />
            )}
          </Field>
          <Field
            name="initial_ratio"
            validate={required(
              "Please select the gender ratio of the first point."
            )}
          >
            {(field, fieldProps) => (
              <Select
                {...fieldProps}
                value={field.value}
                error={field.error}
                options={[
                  {
                    label: "4 Female / 3 Male",
                    value: genderRatio.FEMALE
                  },
                  {
                    label: "4 Male / 3 Female",
                    value: genderRatio.MALE
                  }
                ]}
                type="text"
                label="Gender Ratio"
                placeholder="Choose a gender ratio"
                required
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

const CreateStatsButton = props => {
  const queryClient = useQueryClient();
  return (
    <ButtonWithModal
      button={{ text: "Start Stats", icon: bookOpen }}
      buttonColor={
        props.buttonColor
          ? matchCardColorToButtonStyles[props.buttonColor]
          : matchCardColorToButtonStyles[getMatchCardColor(props.match)]
      }
      onClose={() => {
        queryClient.invalidateQueries({
          queryKey: ["matches", props.tournamentSlug]
        });
        queryClient.invalidateQueries({
          queryKey: ["team-matches", props.tournamentSlug]
        });
      }}
    >
      <CreateForm match={props.match} />
    </ButtonWithModal>
  );
};

export default CreateStatsButton;
