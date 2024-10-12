import {
  createForm,
  getValue,
  required,
  setValues
} from "@modular-forms/solid";
import { useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { createMutation, useQueryClient } from "@tanstack/solid-query";
import { createAsyncOptions, Select } from "@thisbeyond/solid-select";
import { userGroup } from "solid-heroicons/solid";
import { createEffect, createSignal, Show } from "solid-js";

import { stateChoices, teamCategoryChoices } from "../../constants";
import { fetchTeamBySlug, searchUsers, updateTeam } from "../../queries";
import Breadcrumbs from "../Breadcrumbs";
import FileInput from "../FileInput";
import InputError from "../InputError";
import InputLabel from "../InputLabel";
import DefaultSelect from "../Select";
import TextInput from "../TextInput";

const Edit = () => {
  const params = useParams();

  const [teamData, setTeamData] = createSignal();

  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");
  const [selectedValues, setSelectedValues] = createSignal();

  const teamQuery = createQuery(
    () => ["teams", params.slug],
    () => fetchTeamBySlug(params.slug)
  );

  const initialValues = {};
  const [updateTeamForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  createEffect(() => {
    if (teamQuery.status === "success" && teamQuery.data) {
      setTeamData(teamQuery.data);
      setValues(updateTeamForm, teamData());
      setSelectedValues([...teamData().admins]);
    }
  });

  const onChange = selected => {
    console.log(selected);
    setSelectedValues(selected);
  };
  const selectProps = createAsyncOptions(searchUsers);
  const selectFormat = item =>
    item.full_name ? item.full_name + ` (${item.username})` : item.username;

  const queryClient = useQueryClient();
  const updateTeamMutation = createMutation({
    mutationFn: updateTeam,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      setStatus("Updated Team!");
    },
    onError: e => {
      console.log(e);
      setError(e);
    }
  });

  const handleSubmit = async values => {
    const { image, ...teamData } = values;
    const data = { ...teamData };
    data.id = teamQuery.data?.id;

    if (selectedValues() && selectedValues().length > 0) {
      data["admin_ids"] = selectedValues().map(value => value.id);
    }

    const formData = new FormData();
    formData.append("team_details", JSON.stringify(data));
    formData.append("image", image);

    setStatus("");
    setError("");

    updateTeamMutation.mutate(formData);
  };

  return (
    <div>
      <Breadcrumbs
        icon={userGroup}
        pageList={[{ url: "/teams", name: "Teams" }, { name: "Edit Team" }]}
      />
      <div class="mx-2">
        <div class="mb-6 flex w-full flex-row items-center justify-start gap-x-6 rounded-xl border border-gray-300 bg-gray-100 p-4">
          <div>
            <img
              class="h-24 w-24 rounded-full p-1 ring-2 ring-gray-300 dark:ring-blue-500"
              src={teamQuery.data?.image ?? teamQuery.data?.image_url}
              alt="Bordered avatar"
            />
          </div>
          <div class="text-lg font-bold text-gray-700">
            {teamQuery.data?.name}
          </div>
        </div>
      </div>
      <div class="mt-6">
        <Form
          class="space-y-2 md:space-y-4 lg:space-y-6"
          onSubmit={handleSubmit}
        >
          <Field
            name="category"
            validate={required("Please select a category.")}
          >
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
            validate={
              getValue(updateTeamForm, "image")
                ? null
                : required("Please add your team's logo.")
            }
          >
            {(field, props) => (
              <FileInput
                {...props}
                accept={"image/*"}
                value={field.value}
                error={field.error}
                label="Upload Team Logo (Square Image Only)"
                subLabel="Note: Uploading directly from Google Drive is not supported. Please download to device and upload as a file."
                required={getValue(updateTeamForm, "image") ? false : true}
              />
            )}
          </Field>
          <div class="px-8 lg:px-10">
            <InputLabel
              name="admins"
              label="Select the admins"
              subLabel="Search by name or email"
              required={true}
            />
            <Select
              name="admins"
              multiple
              format={selectFormat}
              onChange={onChange}
              initialValue={selectedValues()}
              isOptionDisabled={value =>
                selectedValues()
                  .map(user => user.id)
                  .includes(value.id)
              }
              {...selectProps}
            />
            <InputError name="admins" error={""} />
          </div>

          <div class="flex w-full justify-center">
            <button
              type="submit"
              class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:bg-gray-400 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 md:w-auto"
              disabled={updateTeamMutation.isLoading}
            >
              <Show when={updateTeamMutation.isLoading} fallback="Update">
                Updating...
              </Show>
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
    </div>
  );
};

export default Edit;
