import { useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { documentText } from "solid-heroicons/solid";
import { For, Show, Suspense } from "solid-js";

import { fetchForm, fetchFormResponses } from "../../queries";
import Breadcrumbs from "../Breadcrumbs";

const FormResponses = () => {
  const params = useParams();

  const formQuery = createQuery(
    () => ["form", params.slug],
    () => fetchForm(params.slug),
    { refetchOnWindowFocus: false }
  );

  const responsesQuery = createQuery(
    () => ["form-responses", params.slug],
    () => fetchFormResponses(params.slug),
    { refetchOnWindowFocus: false }
  );

  const renderAnswer = value =>
    Array.isArray(value)
      ? value.join(", ")
      : value === "" || value === undefined
      ? "-"
      : value;

  return (
    <div>
      <Breadcrumbs
        icon={documentText}
        pageList={[
          { url: "/forms", name: "Forms" },
          { name: formQuery.data?.title || "Form" },
          { name: "Responses" }
        ]}
      />
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
        Responses — {formQuery.data?.title}
      </h1>

      <Suspense fallback={<p class="mt-6 text-gray-500">Loading...</p>}>
        <Show
          when={responsesQuery.data?.length}
          fallback={<p class="mt-6 text-gray-500">No responses yet.</p>}
        >
          <div class="mt-6 overflow-x-auto">
            <table class="w-full text-left text-sm text-gray-700 dark:text-gray-300">
              <thead class="bg-gray-100 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-300">
                <tr>
                  <th class="px-4 py-2">Name</th>
                  <th class="px-4 py-2">Email</th>
                  <th class="px-4 py-2">Phone</th>
                  <th class="px-4 py-2">Submitted</th>
                  <For each={formQuery.data?.fields}>
                    {field => <th class="px-4 py-2">{field.label}</th>}
                  </For>
                </tr>
              </thead>
              <tbody>
                <For each={responsesQuery.data}>
                  {resp => (
                    <tr class="border-b dark:border-gray-700">
                      <td class="px-4 py-2">{resp.name}</td>
                      <td class="px-4 py-2">{resp.email}</td>
                      <td class="px-4 py-2">{resp.phone}</td>
                      <td class="px-4 py-2">
                        {new Date(resp.submitted_at).toLocaleString()}
                      </td>
                      <For each={formQuery.data?.fields}>
                        {field => (
                          <td class="px-4 py-2">
                            {renderAnswer(resp.answers[field.key])}
                          </td>
                        )}
                      </For>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
        </Show>
      </Suspense>
    </div>
  );
};

export default FormResponses;
