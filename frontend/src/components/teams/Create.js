import { createForm, getValue, required } from "@modular-forms/solid";
import { A, useNavigate } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { userGroup } from "solid-heroicons/solid";
import { createMemo, createSignal, For, Show } from "solid-js";

import { stateChoices, teamCategoryChoices } from "../../constants";
import { createTeam, fetchTeams } from "../../queries";
import { withinUploadLimits } from "../../uploads";
import Breadcrumbs from "../Breadcrumbs";
import FileInput from "../FileInput";
import DefaultSelect from "../Select";
import TextInput from "../TextInput";

// As server/duplicates/teams/suggest.py matches copies.
const normalizedName = name =>
  (name || "").toLowerCase().replace(/[^a-z0-9]/g, "");

const Create = () => {
  const navigate = useNavigate();
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const initialValues = {};
  const [createTeamForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const teamsQuery = createQuery(() => ["teams"], fetchTeams);
  const sameName = createMemo(() => {
    const key = normalizedName(getValue(createTeamForm, "name"));
    return key
      ? (Array.isArray(teamsQuery.data) ? teamsQuery.data : []).filter(
          team => normalizedName(team.name) === key
        )
      : [];
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
              aria-describedby="name-hint"
              required
            />
          )}
        </Field>
        <p
          id="name-hint"
          class="px-8 text-sm text-gray-600 dark:text-gray-300 lg:px-10"
        >
          Use one team for every division and format: Opens, Mixed, Womens, 5v5,
          beach. Each tournament gets its own roster.
        </p>
        <div aria-live="polite" class="px-8 lg:px-10">
          <Show when={sameName().length > 0}>
            <div
              id="team-name-taken"
              class="rounded-lg border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-900 dark:border-yellow-700 dark:bg-yellow-900 dark:text-yellow-100"
            >
              <p class="font-semibold">
                {sameName().length === 1
                  ? "There's already a team with this name"
                  : "There are already teams with this name"}
              </p>
              <ul class="mt-1 list-disc pl-5">
                <For each={sameName()}>
                  {team => (
                    <li>
                      <A
                        href={`/team/${team.slug}`}
                        class="font-medium underline hover:no-underline"
                      >
                        {team.name.trim()}
                      </A>
                      <Show when={team.city}> · {team.city}</Show>
                    </li>
                  )}
                </For>
              </ul>
              <p class="mt-2">
                {sameName().length === 1
                  ? "If it's yours, ask its admins to add you instead of making a new one. Different team? Go ahead."
                  : "If one is yours, ask its admins to add you instead of making a new one. Different team? Go ahead."}
              </p>
            </div>
          </Show>
        </div>
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
          validate={[
            required("Please add your team's logo."),
            withinUploadLimits
          ]}
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
          class="mr-2 w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:bg-gray-400 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
          disabled={createTeamMutation.isLoading}
        >
          <Show when={createTeamMutation.isLoading} fallback="Submit">
            Creating...
          </Show>
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
