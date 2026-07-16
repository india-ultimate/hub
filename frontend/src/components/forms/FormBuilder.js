import { useNavigate, useParams } from "@solidjs/router";
import { documentText } from "solid-heroicons/solid";
import { createSignal, For, onMount, Show } from "solid-js";
import { createStore, produce } from "solid-js/store";

import { createForm, fetchForm, updateForm } from "../../queries";
import Breadcrumbs from "../Breadcrumbs";

const FIELD_TYPES = [
  { value: "text", label: "Short text" },
  { value: "textarea", label: "Long text" },
  { value: "number", label: "Number" },
  { value: "email", label: "Email" },
  { value: "dropdown", label: "Dropdown" },
  { value: "checkbox", label: "Checkboxes (multi-select)" },
  { value: "radio", label: "Single choice" },
  { value: "date", label: "Date" }
];

const CHOICE_TYPES = ["dropdown", "checkbox", "radio"];

const FormBuilder = () => {
  const params = useParams();
  const navigate = useNavigate();
  const isEdit = () => Boolean(params.slug);

  const [title, setTitle] = createSignal("");
  const [description, setDescription] = createSignal("");
  const [paymentAmount, setPaymentAmount] = createSignal("");
  const [isActive, setIsActive] = createSignal(true);
  const [fields, setFields] = createStore([]);
  const [status, setStatus] = createSignal("");
  const [saving, setSaving] = createSignal(false);

  let keyCounter = 0;
  const nextKey = () => `field_${Date.now()}_${keyCounter++}`;

  const addField = () =>
    setFields(
      produce(f =>
        f.push({
          key: nextKey(),
          label: "",
          type: "text",
          required: false,
          optionsText: ""
        })
      )
    );

  const removeField = i => setFields(produce(f => f.splice(i, 1)));

  // Rich-text editor for the description (Bold / Italic / Underline / Link).
  let editorRef;
  const syncDescription = () => setDescription(editorRef?.innerHTML || "");
  const exec = (command, value) => {
    document.execCommand(command, false, value);
    editorRef?.focus();
    syncDescription();
  };
  const addLink = () => {
    const url = window.prompt("Enter the link URL (include https://)");
    if (url) {
      exec("createLink", url);
    }
  };

  // Prefill when editing an existing form.
  onMount(async () => {
    if (isEdit()) {
      try {
        const form = await fetchForm(params.slug);
        setTitle(form.title);
        setDescription(form.description || "");
        if (editorRef) {
          editorRef.innerHTML = form.description || "";
        }
        setPaymentAmount(
          form.payment_amount ? String(form.payment_amount / 100) : ""
        );
        setIsActive(form.is_active !== false);
        setFields(
          form.fields.map(f => ({
            key: f.key,
            label: f.label,
            type: f.type,
            required: f.required,
            optionsText: (f.options || []).join("\n")
          }))
        );
      } catch (err) {
        setStatus(`Error: ${err.message}`);
      }
    } else if (fields.length === 0) {
      addField();
    }
  });

  const handleSubmit = async e => {
    e.preventDefault();
    setStatus("");
    setSaving(true);

    const payload = {
      title: title(),
      description: description(),
      payment_amount: paymentAmount()
        ? Math.round(Number(paymentAmount()) * 100)
        : null,
      is_active: isActive(),
      fields: fields.map(f => ({
        key: f.key,
        label: f.label,
        type: f.type,
        required: f.required,
        options: CHOICE_TYPES.includes(f.type)
          ? f.optionsText
              .split("\n")
              .map(o => o.trim())
              .filter(Boolean)
          : []
      }))
    };

    try {
      const result = isEdit()
        ? await updateForm({ slug: params.slug, data: payload })
        : await createForm(payload);
      navigate(`/forms/${result.slug}`);
    } catch (err) {
      setStatus(`Error: ${err.message}`);
      setSaving(false);
    }
  };

  return (
    <div>
      <Breadcrumbs
        icon={documentText}
        pageList={[
          { url: "/forms", name: "Forms" },
          { name: isEdit() ? "Edit form" : "New form" }
        ]}
      />
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
        {isEdit() ? "Edit form" : "New form"}
      </h1>

      <div class="mt-4 rounded-lg bg-blue-50 p-4 text-sm text-blue-800 dark:bg-gray-800 dark:text-blue-300">
        The submitter's name, email, and phone are captured automatically and
        shown to staff with each response — you don't need to add fields for
        them.
      </div>

      <form class="mt-6 space-y-5" onSubmit={handleSubmit}>
        <div>
          <label class="mb-1 block text-sm font-medium text-gray-900 dark:text-white">
            Title <span class="text-red-500">*</span>
          </label>
          <input
            required
            value={title()}
            onInput={e => setTitle(e.target.value)}
            class="w-full rounded-lg border border-gray-300 p-2.5 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-gray-900 dark:text-white">
            Description
          </label>
          <div class="overflow-hidden rounded-lg border border-gray-300 dark:border-gray-600">
            <div class="flex gap-1 border-b border-gray-300 bg-gray-50 p-1 dark:border-gray-600 dark:bg-gray-800">
              <button
                type="button"
                title="Bold"
                onClick={() => exec("bold")}
                class="h-8 w-8 rounded font-bold hover:bg-gray-200 dark:text-white dark:hover:bg-gray-700"
              >
                B
              </button>
              <button
                type="button"
                title="Italic"
                onClick={() => exec("italic")}
                class="h-8 w-8 rounded italic hover:bg-gray-200 dark:text-white dark:hover:bg-gray-700"
              >
                I
              </button>
              <button
                type="button"
                title="Underline"
                onClick={() => exec("underline")}
                class="h-8 w-8 rounded underline hover:bg-gray-200 dark:text-white dark:hover:bg-gray-700"
              >
                U
              </button>
              <button
                type="button"
                title="Add link"
                onClick={addLink}
                class="h-8 w-8 rounded text-blue-600 hover:bg-gray-200 dark:text-blue-400 dark:hover:bg-gray-700"
              >
                🔗
              </button>
            </div>
            <div
              ref={el => (editorRef = el)}
              contentEditable={true}
              onInput={syncDescription}
              class="prose prose-sm min-h-[5rem] max-w-none p-2.5 dark:prose-invert focus:outline-none dark:text-white [&_a]:text-blue-600 [&_a]:underline"
            />
          </div>
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-gray-900 dark:text-white">
            Payment amount (₹) — leave blank for a free form
          </label>
          <input
            type="number"
            min="0"
            step="1"
            value={paymentAmount()}
            onInput={e => setPaymentAmount(e.target.value)}
            class="w-full rounded-lg border border-gray-300 p-2.5 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
          />
        </div>

        <label class="flex items-center gap-2 text-sm text-gray-900 dark:text-white">
          <input
            type="checkbox"
            checked={isActive()}
            onChange={e => setIsActive(e.target.checked)}
          />
          Accepting responses
        </label>

        <div class="space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-white">
            Fields
          </h2>
          <For each={fields}>
            {(field, i) => (
              <div class="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
                <div class="flex flex-wrap gap-3">
                  <input
                    required
                    placeholder="Field label"
                    value={field.label}
                    onInput={e => setFields(i(), "label", e.target.value)}
                    class="flex-1 rounded-lg border border-gray-300 p-2 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                  />
                  <select
                    value={field.type}
                    onChange={e => setFields(i(), "type", e.target.value)}
                    class="rounded-lg border border-gray-300 p-2 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                  >
                    <For each={FIELD_TYPES}>
                      {t => <option value={t.value}>{t.label}</option>}
                    </For>
                  </select>
                  <label class="flex items-center gap-2 text-sm text-gray-900 dark:text-white">
                    <input
                      type="checkbox"
                      checked={field.required}
                      onChange={e =>
                        setFields(i(), "required", e.target.checked)
                      }
                    />
                    Required
                  </label>
                  <button
                    type="button"
                    onClick={() => removeField(i())}
                    class="text-sm text-red-600 hover:underline"
                  >
                    Remove
                  </button>
                </div>
                <Show when={CHOICE_TYPES.includes(field.type)}>
                  <textarea
                    placeholder="Options (one per line)"
                    value={field.optionsText}
                    onInput={e => setFields(i(), "optionsText", e.target.value)}
                    rows="3"
                    class="mt-3 w-full rounded-lg border border-gray-300 p-2 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                  />
                </Show>
              </div>
            )}
          </For>
          <button
            type="button"
            onClick={addField}
            class="rounded-lg border border-gray-300 px-4 py-2 text-sm dark:border-gray-600 dark:text-white"
          >
            + Add field
          </button>
        </div>

        <Show when={status()}>
          <p class="text-sm text-red-500">{status()}</p>
        </Show>

        <button
          type="submit"
          disabled={saving()}
          class="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
        >
          {saving() ? "Saving..." : isEdit() ? "Save changes" : "Create form"}
        </button>
      </form>
    </div>
  );
};

export default FormBuilder;
