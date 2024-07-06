import { createForm, required } from "@modular-forms/solid";
import { useNavigate } from "@solidjs/router";
import { createMutation, useQueryClient } from "@tanstack/solid-query";
import { userGroup } from "solid-heroicons/solid";
import { createSignal, Show } from "solid-js";

import { stateChoices, teamCategoryChoices } from "../../constants";
import { createTeam } from "../../queries";
import Breadcrumbs from "../Breadcrumbs";
import FileInput from "../FileInput";
import DefaultSelect from "../Select";
import TextInput from "../TextInput";

const Create = () => {
  const navigate = useNavigate();
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const initialValues = {};
  const [_createTeamForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const queryClient = useQueryClient();
  const createTeamMutation = createMutation({
    mutationFn: createTeam,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
      setStatus("Created Team!");
      navigate("/teams", { replace: true });
    },
    onError: e => {
      console.log(e);
      setError(e);
    }
  });

  const handleSubmit = async values => {
    const { image, ...teamData } = values;
    const data = { ...teamData };

    const formData = new FormData();
    formData.append("team_details", JSON.stringify(data));
    formData.append("image", image);

    setStatus("");
    setError("");

    createTeamMutation.mutate(formData);
  };

  return (
    <div>
      <Breadcrumbs
        icon={userGroup}
        pageList={[{ url: "/teams", name: "Teams" }, { name: "New Team" }]}
      />
      <Form class="space-y-2 md:space-y-4 lg:space-y-6" onSubmit={handleSubmit}>
        <Field name="name" validate={required("Please enter the team's name.")}>
          {(field, props) => (
            <TextInput
              {...props}
              value={field.value}
              error={field.error}
              type="text"
              label="Name"
              placeholder="Your team name"
              required
            />
          )}
        </Field>
        <Field name="category" validate={required("Please select a category.")}>
          {(field, props) => (
            <DefaultSelect
              {...props}
              value={field.value}
              options={teamCategoryChoices}
              error={field.error}
              label="Category"
              placeholder="Select your team's category"
              required
            />
          )}
        </Field>
        <Field
          name="state_ut"
          validate={required("Please select a State or UT.")}
        >
          {(field, props) => (
            <DefaultSelect
              {...props}
              value={field.value}
              options={stateChoices}
              error={field.error}
              label="Which State/UT team is based in?"
              placeholder="Select State/UT"
              required
            />
          )}
        </Field>
        <Field name="city" validate={required("Please enter the city name.")}>
          {(field, props) => (
            <TextInput
              {...props}
              value={field.value}
              error={field.error}
              type="text"
              label="Which City team is based in?"
              placeholder="Enter city name"
              required
            />
          )}
        </Field>
        <Field
          name="image"
          type="File"
          validate={required("Please add your team's logo.")}
        >
          {(field, props) => (
            <FileInput
              {...props}
              accept={"image/*"}
              value={field.value}
              error={field.error}
              label="Upload Team Logo (Square Image Only)"
              subLabel="Note: Uploading directly from Google Drive is not supported. Please download to device and upload as a file."
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

export default Create;
