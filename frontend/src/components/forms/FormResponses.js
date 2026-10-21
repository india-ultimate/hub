import { useParams } from "@solidjs/router";
import { createQuery, useQueryClient } from "@tanstack/solid-query";
import { documentText } from "solid-heroicons/solid";
import { createSignal, For, Show, Suspense } from "solid-js";

import {
  downloadFormResponsesCsv,
  fetchForm,
  fetchFormResponses,
  updateForm
} from "../../queries";
import Breadcrumbs from "../Breadcrumbs";

const FormResponses = () => {
  const params = useParams();
  const queryClient = useQueryClient();
  const [actionStatus, setActionStatus] = createSignal("");
  const [busy, setBusy] = createSignal(false);

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

  const toggleAcceptingSubmissions = async () => {
    const form = formQuery.data;
    if (!form || busy()) return;

    setBusy(true);
    setActionStatus("");
    try {
      await updateForm({
        slug: params.slug,
        data: {
          title: form.title,
          description: form.description,
          fields: form.fields,
          payment_amount: form.payment_amount,
          is_active: !form.is_active
        }
      });
      await queryClient.invalidateQueries(["form", params.slug]);
      await queryClient.invalidateQueries(["forms"]);
    } catch (err) {
      setActionStatus(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleDownloadCsv = async () => {
    if (busy()) return;
    setBusy(true);
    setActionStatus("");
    try {
      await downloadFormResponsesCsv(params.slug);
    } catch (err) {
      setActionStatus(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div class="pb-24">
      <Breadcrumbs
        icon={documentText}
        pageList={[
          { url: "/forms", name: "Forms" },
          { name: formQuery.data?.title || "Form" },
          { name: "Responses" }
        ]}
      />
      <Show
        when={!(formQuery.error || responsesQuery.error)}
        fallback={
          <p role="alert" class="mt-3 text-red-600 dark:text-red-400">
            {(formQuery.error || responsesQuery.error).message}
          </p>
        }
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h1 class="min-w-0 break-words text-2xl font-bold text-gray-900 dark:text-white">
            Responses — {formQuery.data?.title}
          </h1>
          <div class="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
            <Show when={formQuery.data}>
              <button
                type="button"
                disabled={busy()}
                onClick={toggleAcceptingSubmissions}
                class="min-h-[44px] rounded-lg border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                {formQuery.data.is_active
                  ? "Stop accepting responses"
                  : "Resume accepting responses"}
              </button>
            </Show>
            <Show when={responsesQuery.data?.length}>
              <button
                type="button"
                disabled={busy()}
                onClick={handleDownloadCsv}
                class="min-h-[44px] rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-gray-400"
              >
                Download CSV
              </button>
            </Show>
          </div>
        </div>

        <Show when={formQuery.data && !formQuery.data.is_active}>
          <p class="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800 dark:bg-gray-800 dark:text-amber-200">
            This form is not accepting new responses.
          </p>
        </Show>

        <Show when={actionStatus()}>
          <p class="mt-3 text-sm text-red-600 dark:text-red-400">
            {actionStatus()}
          </p>
        </Show>

        <Suspense fallback={<p class="mt-6 text-gray-500">Loading...</p>}>
          <Show
            when={responsesQuery.data?.length}
            fallback={<p class="mt-6 text-gray-500">No responses yet.</p>}
          >
            <ul class="mt-6 space-y-3 sm:hidden">
              <For each={responsesQuery.data}>
                {resp => (
                  <li
                    data-testid="response-card"
                    class="break-words rounded-lg border border-gray-200 p-4 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-300"
                  >
                    <p class="font-medium text-gray-900 dark:text-white">
                      {resp.name}
                    </p>
                    <p>{resp.email}</p>
                    <p>{resp.phone}</p>
                    <p class="text-xs text-gray-500 dark:text-gray-400">
                      {new Date(resp.submitted_at).toLocaleString()}
                    </p>
                    <dl class="mt-3 space-y-2 border-t border-gray-200 pt-3 dark:border-gray-700">
                      <For each={formQuery.data?.fields}>
                        {field => (
                          <div>
                            <dt class="font-medium text-gray-900 dark:text-white">
                              {field.label}
                            </dt>
                            <dd>{renderAnswer(resp.answers[field.key])}</dd>
                          </div>
                        )}
                      </For>
                    </dl>
                  </li>
                )}
              </For>
            </ul>
            <div class="mt-6 hidden overflow-x-auto sm:block">
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
      </Show>
    </div>
  );
};

export default FormResponses;
