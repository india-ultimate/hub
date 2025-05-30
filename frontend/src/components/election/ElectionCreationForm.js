import {
  createForm,
  minLength,
  minRange,
  required,
  toTrimmed
} from "@modular-forms/solid";
import { createMutation, useQueryClient } from "@tanstack/solid-query";
import { createSignal, Show } from "solid-js";

import { createElection } from "../../queries";
import Error from "../alerts/Error";
import Info from "../alerts/Info";
import Select from "../Select";
import TextAreaInput from "../TextAreaInput";
import TextInput from "../TextInput";

const ElectionCreationForm = () => {
  const [_, { Form, Field }] = createForm({
    initialValues: {
      title: "",
      description: "",
      start_date: "",
      end_date: "",
      num_winners: 1,
      voting_method: "IRV"
    },
    validateOn: ["blur", "touched"]
  });

  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const queryClient = useQueryClient();
  const createElectionMutation = createMutation({
    mutationFn: createElection,
    onSuccess: () => {
      setStatus("Election created successfully!");
      queryClient.invalidateQueries({ queryKey: ["elections"] });
    },
    onError: error => {
      setError(error.message || "Failed to create election. Please try again.");
    }
  });

  const votingMethodOptions = [
    { value: "", label: "Select a voting method" },
    { value: "IRV", label: "Instant Runoff Voting - Single Winner" },
    { value: "STV", label: "Single Transferable Vote - Multiple Winners" }
  ];

  const handleSubmit = async values => {
    setStatus("");
    setError("");

    try {
      // Convert dates to ISO strings
      const data = {
        ...values,
        start_date: new Date(values.start_date).toISOString(),
        end_date: new Date(values.end_date).toISOString()
      };

      await createElectionMutation.mutateAsync(data);
    } catch (err) {
      setError(err.message || "Failed to create election");
    }
  };

  return (
    <div class="flex justify-center">
      <div class="w-full max-w-2xl rounded-lg bg-gray-200 p-6 dark:bg-gray-700/50">
        <Show when={status()}>
          <Info text={status()} />
        </Show>
        <Show when={error()}>
          <Error text={error()} />
        </Show>
        <Form onSubmit={handleSubmit}>
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field
              name="title"
              type="string"
              transform={toTrimmed({ on: "input" })}
              validate={[
                required("Title is required"),
                minLength(3, "Title must be at least 3 characters")
              ]}
            >
              {(field, props) => (
                <TextInput
                  {...props}
                  type="text"
                  label="Title"
                  placeholder="Enter election title"
                  value={field.value}
                  error={field.error}
                  required
                  padding
                />
              )}
            </Field>

            <Field
              name="voting_method"
              type="string"
              validate={[required("Voting method is required")]}
            >
              {(field, props) => (
                <Select
                  {...props}
                  label="Voting Method"
                  value={field.value}
                  error={field.error}
                  options={votingMethodOptions}
                  required
                  padding
                  class="px-0 lg:px-0"
                />
              )}
            </Field>

            <Field
              name="start_date"
              type="string"
              validate={[required("Start date is required")]}
            >
              {(field, props) => (
                <TextInput
                  {...props}
                  type="datetime-local"
                  label="Start Date"
                  value={field.value}
                  error={field.error}
                  required
                  padding
                />
              )}
            </Field>

            <Field
              name="end_date"
              type="string"
              validate={[required("End date is required")]}
            >
              {(field, props) => (
                <TextInput
                  {...props}
                  type="datetime-local"
                  label="End Date"
                  value={field.value}
                  error={field.error}
                  required
                  padding
                />
              )}
            </Field>

            <Field
              name="num_winners"
              type="number"
              validate={[
                required("Number of winners is required"),
                minRange(1, "Number of winners must be at least 1")
              ]}
            >
              {(field, props) => (
                <TextInput
                  {...props}
                  type="number"
                  label="Number of Winners"
                  placeholder="1"
                  value={field.value}
                  error={field.error}
                  required
                  padding
                />
              )}
            </Field>
          </div>

          <Field
            name="description"
            type="string"
            transform={toTrimmed({ on: "input" })}
            validate={[required("Description is required")]}
          >
            {(field, props) => (
              <TextAreaInput
                {...props}
                label="Description"
                placeholder="Enter election description"
                value={field.value}
                error={field.error}
                required
                padding
              />
            )}
          </Field>

          <div class="mt-4 flex justify-center">
            <button
              type="submit"
              class="w-fit rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:bg-gray-400 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 disabled:dark:bg-gray-400 sm:w-auto"
              disabled={createElectionMutation.isPending}
            >
              {createElectionMutation.isPending
                ? "Creating..."
                : "Create Election"}
            </button>
          </div>
        </Form>
      </div>
    </div>
  );
};

export default ElectionCreationForm;
