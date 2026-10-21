import { useNavigate, useParams, useSearchParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import DOMPurify from "dompurify";
import { documentText } from "solid-heroicons/solid";
import {
  createEffect,
  createMemo,
  createSignal,
  For,
  Match,
  on,
  onMount,
  Show,
  Suspense,
  Switch,
  untrack
} from "solid-js";
import { createStore } from "solid-js/store";

import { groupSections, nextSectionIndex } from "../../formSections";
import { inr } from "../../money";
import {
  fetchForm,
  fetchMyFormResponses,
  submitFormResponse
} from "../../queries";
import { openCheckout } from "../../razorpay";
import { useStore } from "../../store";
import { fetchUserData } from "../../utils";
import Breadcrumbs from "../Breadcrumbs";

const FormView = () => {
  const params = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [, { userFetchSuccess, userFetchFailure }] = useStore();

  const [answers, setAnswers] = createStore({});
  const [status, setStatus] = createSignal("");
  const [submitting, setSubmitting] = createSignal(false);
  const [done, setDone] = createSignal(false);
  const [visited, setVisited] = createSignal([0]);
  let heading;

  const formQuery = createQuery(
    () => ["form", params.slug],
    () => fetchForm(params.slug),
    { refetchOnWindowFocus: false }
  );

  const myResponsesQuery = createQuery(
    () => ["form-my-responses", params.slug],
    () => fetchMyFormResponses(params.slug),
    { refetchOnWindowFocus: false }
  );

  const groups = createMemo(() =>
    groupSections(formQuery.data?.sections || [], formQuery.data?.fields || [])
  );
  const current = createMemo(() => {
    const index = groups().findIndex(
      g => g.section.key === searchParams.section
    );
    return visited().includes(index) ? index : visited()[0];
  });
  const next = createMemo(() => nextSectionIndex(groups(), current(), answers));
  const position = () => visited().indexOf(current());

  createEffect(() => {
    if (
      groups().length > 1 &&
      searchParams.section &&
      searchParams.section !== groups()[current()].section.key
    ) {
      setSearchParams(
        { section: groups()[visited()[0]].section.key },
        { replace: true }
      );
    }
  });

  createEffect(
    on(
      current,
      () => {
        window.scrollTo(0, 0);
        heading?.focus();
      },
      { defer: true }
    )
  );

  onMount(() => {
    if (!window.Razorpay) {
      console.warn("Razorpay SDK not loaded");
    }
  });

  const setValue = (key, value) => setAnswers(key, value);

  const toggleCheckbox = (key, option, checked) => {
    const current = Array.isArray(answers[key]) ? answers[key] : [];
    if (checked) {
      setAnswers(key, [...current, option]);
    } else {
      setAnswers(
        key,
        current.filter(v => v !== option)
      );
    }
  };

  const finishSuccess = () => {
    setStatus("Submitted successfully! 🎉");
    setDone(true);
    setSubmitting(false);
    myResponsesQuery.refetch();
  };

  const openRazorpay = order =>
    openCheckout(order, {
      onSuccess: () => {
        fetchUserData(userFetchSuccess, userFetchFailure);
        finishSuccess();
      },
      onFailure: message => {
        setStatus(`Error: ${message}`);
        setSubmitting(false);
      },
      onDismiss: () => setSubmitting(false),
      // The payment may have gone through, so Submit stays off.
      onUnconfirmed: setStatus
    });

  const handleSubmit = async e => {
    e.preventDefault();
    if (next() !== null) {
      setVisited([...visited().slice(0, position() + 1), next()]);
      setSearchParams({ section: groups()[next()].section.key });
      return;
    }
    setStatus("");
    setSubmitting(true);
    try {
      const result = await submitFormResponse({
        slug: params.slug,
        answers
      });
      if (result.status === "payment_required" && result.order) {
        openRazorpay(result.order);
      } else {
        finishSuccess();
      }
    } catch (err) {
      setStatus(`Error: ${err.message}`);
      setSubmitting(false);
    }
  };

  const renderAnswer = value =>
    Array.isArray(value) ? value.join(", ") : value === "" ? "-" : value;

  return (
    <div>
      <Breadcrumbs
        icon={documentText}
        pageList={[
          { url: "/forms", name: "Forms" },
          { name: formQuery.data?.title || "Form" }
        ]}
      />
      <Suspense fallback={<p class="text-gray-500">Loading...</p>}>
        <Show when={formQuery.data} fallback={<p>Form not found.</p>}>
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
            {formQuery.data.title}
          </h1>
          <Show when={formQuery.data.description}>
            <div
              class="prose prose-sm mt-2 max-w-none whitespace-pre-line text-gray-600 dark:prose-invert dark:text-gray-300 [&_a]:text-blue-600 [&_a]:underline dark:[&_a]:text-blue-400"
              // eslint-disable-next-line solid/no-innerhtml
              innerHTML={DOMPurify.sanitize(formQuery.data.description)}
            />
          </Show>

          <Show when={myResponsesQuery.data?.length}>
            <div class="mt-4 rounded-lg bg-blue-50 p-4 text-sm text-blue-800 dark:bg-gray-800 dark:text-blue-300">
              <p>
                You've submitted this form {myResponsesQuery.data.length}{" "}
                time(s).
              </p>
              <details class="mt-2">
                <summary class="cursor-pointer">View your responses</summary>
                <For each={myResponsesQuery.data}>
                  {resp => (
                    <div class="mt-2 border-t border-blue-200 pt-2 dark:border-gray-700">
                      <p class="text-xs text-gray-500">
                        {new Date(resp.submitted_at).toLocaleString()}
                      </p>
                      <For each={formQuery.data.fields}>
                        {field => (
                          <p>
                            <span class="font-medium">{field.label}:</span>{" "}
                            {renderAnswer(resp.answers[field.key])}
                          </p>
                        )}
                      </For>
                    </div>
                  )}
                </For>
              </details>
            </div>
          </Show>

          <Show
            when={formQuery.data.is_active}
            fallback={
              <p class="mt-6 rounded-lg bg-gray-100 p-4 text-sm text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                This form is no longer accepting responses.
              </p>
            }
          >
            <Show
              when={!done()}
              fallback={
                <p class="mt-6 text-green-600 dark:text-green-400">
                  {status()}
                </p>
              }
            >
              <form class="mt-6 space-y-5" onSubmit={handleSubmit}>
                <Show when={groups().length > 1}>
                  <div>
                    <div
                      ref={heading}
                      tabindex="-1"
                      class="focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                    >
                      <p class="text-sm font-medium text-gray-500 dark:text-gray-400">
                        Section {position() + 1}
                      </p>
                      <Show when={groups()[current()].section.title}>
                        <h2 class="text-xl font-semibold text-gray-900 dark:text-white">
                          {groups()[current()].section.title}
                        </h2>
                      </Show>
                    </div>
                    <p class="mt-1 whitespace-pre-line text-sm text-gray-600 dark:text-gray-300">
                      {groups()[current()].section.description}
                    </p>
                  </div>
                </Show>
                <For each={groups()[current()].fields}>
                  {field => (
                    <div>
                      <label
                        class="mb-1 block text-sm font-medium text-gray-900 dark:text-white"
                        for={field.key}
                      >
                        {field.label}
                        <Show when={field.required}>
                          <span class="ml-1 text-red-500">*</span>
                        </Show>
                      </label>
                      <Switch>
                        <Match when={field.type === "textarea"}>
                          <textarea
                            id={field.key}
                            required={field.required}
                            class="w-full rounded-lg border border-gray-300 p-2.5 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                            rows="4"
                            value={answers[field.key] || ""}
                            onInput={e => setValue(field.key, e.target.value)}
                          />
                        </Match>
                        <Match when={field.type === "dropdown"}>
                          <select
                            id={field.key}
                            required={field.required}
                            class="w-full rounded-lg border border-gray-300 p-2.5 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                            onChange={e => setValue(field.key, e.target.value)}
                          >
                            <option value="">Select...</option>
                            <For each={field.options}>
                              {opt => (
                                <option
                                  value={opt}
                                  selected={answers[field.key] === opt}
                                >
                                  {opt}
                                </option>
                              )}
                            </For>
                          </select>
                        </Match>
                        <Match when={field.type === "radio"}>
                          <div class="space-y-1">
                            <For each={field.options}>
                              {opt => (
                                <label class="flex items-center gap-2 text-sm text-gray-900 dark:text-white">
                                  <input
                                    type="radio"
                                    name={field.key}
                                    value={opt}
                                    required={field.required}
                                    checked={answers[field.key] === opt}
                                    onChange={() => setValue(field.key, opt)}
                                  />
                                  {opt}
                                </label>
                              )}
                            </For>
                          </div>
                        </Match>
                        <Match when={field.type === "checkbox"}>
                          <div class="space-y-1">
                            <For each={field.options}>
                              {opt => (
                                <label class="flex items-center gap-2 text-sm text-gray-900 dark:text-white">
                                  <input
                                    type="checkbox"
                                    value={opt}
                                    checked={(
                                      answers[field.key] || []
                                    ).includes(opt)}
                                    onChange={e =>
                                      toggleCheckbox(
                                        field.key,
                                        opt,
                                        e.target.checked
                                      )
                                    }
                                  />
                                  {opt}
                                </label>
                              )}
                            </For>
                          </div>
                        </Match>
                        <Match when={true}>
                          <input
                            id={field.key}
                            type={
                              field.type === "number"
                                ? "number"
                                : field.type === "email"
                                  ? "email"
                                  : field.type === "date"
                                    ? "date"
                                    : "text"
                            }
                            required={field.required}
                            value={untrack(() => answers[field.key]) || ""}
                            class="w-full rounded-lg border border-gray-300 p-2.5 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                            onInput={e => setValue(field.key, e.target.value)}
                          />
                        </Match>
                      </Switch>
                    </div>
                  )}
                </For>

                <Show when={status() && !done()}>
                  <p class="text-sm text-red-500">{status()}</p>
                </Show>

                <div class="flex items-center justify-between gap-3">
                  <Show when={position() > 0} fallback={<span />}>
                    <button
                      type="button"
                      onClick={() => navigate(-1)}
                      class="min-h-[44px] rounded-lg border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-900 hover:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:border-gray-600 dark:text-white dark:hover:bg-gray-700"
                    >
                      Back
                    </button>
                  </Show>
                  <button
                    type="submit"
                    disabled={submitting()}
                    class="min-h-[44px] rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-gray-400"
                  >
                    <Show when={next() === null} fallback="Next">
                      <Show
                        when={formQuery.data.payment_amount}
                        fallback={submitting() ? "Submitting..." : "Submit"}
                      >
                        {submitting()
                          ? "Processing..."
                          : `Pay ${inr(formQuery.data.payment_amount)} & Submit`}
                      </Show>
                    </Show>
                  </button>
                </div>
              </form>
            </Show>
          </Show>
        </Show>
      </Suspense>
    </div>
  );
};

export default FormView;
