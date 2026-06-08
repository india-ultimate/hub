import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import DOMPurify from "dompurify";
import { documentText } from "solid-heroicons/solid";
import { For, Show, Suspense } from "solid-js";

import { fetchForms } from "../../queries";
import { useStore } from "../../store";
import Breadcrumbs from "../Breadcrumbs";

// The description is rich HTML; show a plain-text snippet in the list.
const toPlainText = html => {
  const tmp = document.createElement("div");
  tmp.innerHTML = DOMPurify.sanitize(html || "");
  return tmp.textContent || "";
};

const FormsList = () => {
  const [store] = useStore();
  const query = createQuery(() => ["forms"], fetchForms, {
    refetchOnWindowFocus: false
  });

  return (
    <div>
      <Breadcrumbs
        icon={documentText}
        pageList={[{ url: "/dashboard", name: "Dashboard" }, { name: "Forms" }]}
      />
      <div class="flex items-center justify-between">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Forms</h1>
        <Show when={store.data.is_staff}>
          <A
            href="/forms/new"
            class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            New form
          </A>
        </Show>
      </div>

      <Suspense fallback={<p class="mt-6 text-gray-500">Loading forms...</p>}>
        <Show
          when={query.data?.length}
          fallback={<p class="mt-6 text-gray-500">No forms available.</p>}
        >
          <ul class="mt-6 space-y-3">
            <For each={query.data}>
              {form => (
                <li class="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
                  <div class="flex items-center justify-between">
                    <div>
                      <A
                        href={`/forms/${form.slug}`}
                        class="text-lg font-medium text-blue-600 hover:underline dark:text-blue-400"
                      >
                        {form.title}
                      </A>
                      <Show when={form.payment_amount}>
                        <span class="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                          ₹{form.payment_amount / 100}
                        </span>
                      </Show>
                      <Show when={!form.is_active}>
                        <span class="ml-2 rounded bg-gray-200 px-2 py-0.5 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-200">
                          Inactive
                        </span>
                      </Show>
                      <Show when={form.description}>
                        <p class="mt-1 line-clamp-2 text-sm text-gray-500">
                          {toPlainText(form.description)}
                        </p>
                      </Show>
                    </div>
                    <Show when={store.data.is_staff}>
                      <div class="flex gap-3 text-sm">
                        <A
                          href={`/forms/${form.slug}/edit`}
                          class="text-gray-600 hover:underline dark:text-gray-300"
                        >
                          Edit
                        </A>
                        <A
                          href={`/forms/${form.slug}/responses`}
                          class="text-gray-600 hover:underline dark:text-gray-300"
                        >
                          Responses
                        </A>
                      </div>
                    </Show>
                  </div>
                </li>
              )}
            </For>
          </ul>
        </Show>
      </Suspense>
    </div>
  );
};

export default FormsList;
