import {
  createForm,
  getValues,
  required,
  setValue
} from "@modular-forms/solid";
import { createMutation, useQueryClient } from "@tanstack/solid-query";
import { createEffect, createSignal, Show } from "solid-js";

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
  const [tournamentForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const handleSubmit = async values => {
    const { logo_light, logo_dark, ...tournamentData } = values;
    const data = { ...tournamentData };

    // Convert fee fields from rupees to paise (multiply by 100)
    const feeFields = [
      "team_fee",
      "player_fee",
      "partial_team_fee",
      "team_late_penalty",
      "player_late_penalty"
    ];

    feeFields.forEach(field => {
      if (
        data[field] !== undefined &&
        data[field] !== null &&
        data[field] !== ""
      ) {
        const intValue = parseInt(data[field], 10);
        if (!Number.isNaN(intValue)) {
          data[field] = intValue * 100;
        }
      }
    });

    const formData = new FormData();
    formData.append("tournament_details", JSON.stringify(data));
    formData.append("logo_light", logo_light);
    formData.append("logo_dark", logo_dark);

    setStatus("");
    setError("");

    createTournamentMutation.mutate(formData);
  };

  const minDate = new Date().toISOString().split("T")[0];

  // Auto-fill late penalty and partial registration end dates based on
  // the corresponding registration dates
  createEffect(() => {
    const values = getValues(tournamentForm);

    const {
      team_registration_start_date,
      team_registration_end_date,
      player_registration_end_date,
      team_partial_registration_end_date,
      team_late_penalty_end_date,
      player_late_penalty_end_date
    } = values;

    if (team_registration_end_date && !team_late_penalty_end_date) {
      setValue(
        tournamentForm,
        "team_late_penalty_end_date",
        team_registration_end_date,
        {
          shouldTouched: false,
          shouldDirty: false,
          shouldValidate: false
        }
      );
    }

    if (player_registration_end_date && !player_late_penalty_end_date) {
      setValue(
        tournamentForm,
        "player_late_penalty_end_date",
        player_registration_end_date,
        {
          shouldTouched: false,
          shouldDirty: false,
          shouldValidate: false
        }
      );
    }

    if (team_registration_start_date && !team_partial_registration_end_date) {
      setValue(
        tournamentForm,
        "team_partial_registration_end_date",
        team_registration_start_date,
        {
          shouldTouched: false,
          shouldDirty: false,
          shouldValidate: false
        }
      );
    }
  });

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
              required("Please enter the team registration end date."),
              value => {
                const {
                  team_registration_start_date,
                  team_partial_registration_end_date,
                  team_late_penalty_end_date
                } = getValues(tournamentForm);

                if (
                  value &&
                  team_registration_start_date &&
                  value < team_registration_start_date
                ) {
                  return "Team registration end date cannot be before start date.";
                }

                if (
                  value &&
                  team_partial_registration_end_date &&
                  value < team_partial_registration_end_date
                ) {
                  return "Team registration end date cannot be before team partial registration end date.";
                }

                if (
                  value &&
                  team_late_penalty_end_date &&
                  value > team_late_penalty_end_date
                ) {
                  return "Team registration end date cannot be after team late penalty end date.";
                }

                return "";
              }
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
            name="team_partial_registration_end_date"
            validate={[
              required("Please enter the team partial registration end date."),
              value => {
                const {
                  team_registration_start_date,
                  team_registration_end_date
                } = getValues(tournamentForm);

                if (
                  value &&
                  team_registration_start_date &&
                  value < team_registration_start_date
                ) {
                  return "Team partial registration end date cannot be before team registration start date.";
                }

                if (
                  value &&
                  team_registration_end_date &&
                  value > team_registration_end_date
                ) {
                  return "Team partial registration end date cannot be after team registration end date.";
                }

                return "";
              }
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="date"
                min={minDate}
                label="Team Partial Registration End Date"
                placeholder={minDate}
                required
              />
            )}
          </Field>
          <Field
            name="team_late_penalty_end_date"
            validate={[
              required("Please enter the team late penalty end date."),
              value => {
                const {
                  team_registration_end_date,
                  team_partial_registration_end_date,
                  team_registration_start_date
                } = getValues(tournamentForm);

                if (
                  value &&
                  team_registration_end_date &&
                  value < team_registration_end_date
                ) {
                  return "Team late penalty end date cannot be before team registration end date.";
                }

                if (
                  value &&
                  team_partial_registration_end_date &&
                  value < team_partial_registration_end_date
                ) {
                  return "Team late penalty end date cannot be before team partial registration end date.";
                }

                if (
                  value &&
                  team_registration_start_date &&
                  value < team_registration_start_date
                ) {
                  return "Team late penalty end date cannot be before team registration start date.";
                }

                return "";
              }
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="date"
                min={minDate}
                label="Team Late Penalty End Date"
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
            validate={[
              required("Please enter the player rostering end date."),
              value => {
                const { player_registration_start_date } =
                  getValues(tournamentForm);

                if (
                  value &&
                  player_registration_start_date &&
                  value < player_registration_start_date
                ) {
                  return "Player rostering end date cannot be before start date.";
                }

                return "";
              }
            ]}
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
            name="player_late_penalty_end_date"
            validate={[
              required("Please enter the player late penalty end date."),
              value => {
                const {
                  player_registration_start_date,
                  player_registration_end_date
                } = getValues(tournamentForm);

                if (
                  value &&
                  player_registration_end_date &&
                  value < player_registration_end_date
                ) {
                  return "Player late penalty end date cannot be before player rostering end date.";
                }

                if (
                  value &&
                  player_registration_start_date &&
                  value < player_registration_start_date
                ) {
                  return "Player late penalty end date cannot be before player rostering start date.";
                }

                return "";
              }
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="date"
                min={minDate}
                label="Player Late Penalty End Date"
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
          {/* Team fees & penalties */}
          <Field
            name="team_fee"
            validate={[
              required("Please enter the team registration fee."),
              value => {
                if (value !== undefined && value !== null && value !== "") {
                  const numValue = Number(value);
                  if (
                    Number.isNaN(numValue) ||
                    numValue < 0 ||
                    !Number.isInteger(numValue)
                  ) {
                    return "Team fee must be a non-negative integer in rupees.";
                  }
                }
                return "";
              }
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                min="0"
                step="1"
                label="Team Registration Fee (₹)"
                placeholder="0"
                required
              />
            )}
          </Field>
          <Field
            name="partial_team_fee"
            validate={[
              required("Please enter the partial team registration fee."),
              value => {
                if (value !== undefined && value !== null && value !== "") {
                  const numValue = Number(value);
                  if (
                    Number.isNaN(numValue) ||
                    numValue < 0 ||
                    !Number.isInteger(numValue)
                  ) {
                    return "Partial team fee must be a non-negative integer in rupees.";
                  }
                }
                return "";
              }
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                min="0"
                step="1"
                label="Partial Team Registration Fee (₹)"
                placeholder="0"
                required
              />
            )}
          </Field>
          <Field
            name="team_late_penalty"
            validate={[
              required("Please enter the team late penalty fee."),
              value => {
                if (value !== undefined && value !== null && value !== "") {
                  const numValue = Number(value);
                  if (
                    Number.isNaN(numValue) ||
                    numValue < 0 ||
                    !Number.isInteger(numValue)
                  ) {
                    return "Team late penalty must be a non-negative integer in rupees.";
                  }
                }
                return "";
              }
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                min="0"
                step="1"
                label="Team Late Penalty per Day (₹)"
                placeholder="0"
                required
              />
            )}
          </Field>
          {/* Player fees & penalties */}
          <Field
            name="player_fee"
            validate={[
              required("Please enter the player registration fee."),
              value => {
                if (value !== undefined && value !== null && value !== "") {
                  const numValue = Number(value);
                  if (
                    Number.isNaN(numValue) ||
                    numValue < 0 ||
                    !Number.isInteger(numValue)
                  ) {
                    return "Player fee must be a non-negative integer in rupees.";
                  }
                }
                return "";
              }
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                min="0"
                step="1"
                label="Player Registration Fee (₹)"
                placeholder="0"
                required
              />
            )}
          </Field>
          <Field
            name="player_late_penalty"
            validate={[
              required("Please enter the player late penalty fee."),
              value => {
                if (value !== undefined && value !== null && value !== "") {
                  const numValue = Number(value);
                  if (
                    Number.isNaN(numValue) ||
                    numValue < 0 ||
                    !Number.isInteger(numValue)
                  ) {
                    return "Player late penalty must be a non-negative integer in rupees.";
                  }
                }
                return "";
              }
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="number"
                min="0"
                step="1"
                label="Player Late Penalty per Day (₹)"
                placeholder="0"
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
