import { useNavigate, useParams } from "@solidjs/router";
import { documentText } from "solid-heroicons/solid";
import { createMemo, createSignal, For, onMount, Show } from "solid-js";
import { createStore, produce } from "solid-js/store";

import { groupSections, unreachableSections } from "../../formSections";
import { toPaise, toRupees } from "../../money";
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
const BRANCH_TYPES = ["dropdown", "radio"];

const inputClass =
  "w-full rounded-lg border border-gray-300 p-2.5 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-white";
const labelClass =
  "mb-1 block text-sm font-medium text-gray-900 dark:text-white";
const buttonClass =
  "min-h-[44px] rounded-lg border border-gray-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:text-white";

const optionList = f =>
  f.optionsText
    .split("\n")
    .map(o => o.trim())
    .filter(Boolean);

const branches = f => f.branch && BRANCH_TYPES.includes(f.type);

const gotoOf = f =>
  branches(f)
    ? Object.fromEntries(optionList(f).map(o => [o, f.goto?.[o] || ""]))
    : undefined;

const FormBuilder = () => {
  const params = useParams();
  const navigate = useNavigate();
  const isEdit = () => Boolean(params.slug);

  const [title, setTitle] = createSignal("");
  const [description, setDescription] = createSignal("");
  const [paymentAmount, setPaymentAmount] = createSignal("");
  const [isActive, setIsActive] = createSignal(true);
  const [fields, setFields] = createStore([]);
  const [sections, setSections] = createStore([]);
  const [status, setStatus] = createSignal("");
  const [refusal, setRefusal] = createSignal("");
  const [loaded, setLoaded] = createSignal(!isEdit());
  const [saving, setSaving] = createSignal(false);

  let keyCounter = 0;
  const nextKey = () => `field_${Date.now()}_${keyCounter++}`;

  const newSection = () => ({
    key: nextKey().replace("field_", "section_"),
    title: "",
    description: "",
    next: ""
  });

  const newField = section => ({
    key: nextKey(),
    label: "",
    type: "text",
    required: false,
    optionsText: "",
    section,
    branch: false,
    goto: {}
  });

  const updateField = (key, ...args) => setFields(f => f.key === key, ...args);

  const addField = section =>
    setFields(produce(f => f.push(newField(section))));

  const removeField = key =>
    setFields(
      produce(f =>
        f.splice(
          f.findIndex(x => x.key === key),
          1
        )
      )
    );

  const addSection = () => {
    const section = newSection();
    setSections(produce(s => s.push(section)));
    addField(section.key);
  };

  const hasBranchingSibling = field =>
    fields.some(
      g => g.key !== field.key && g.section === field.section && branches(g)
    );

  const moveField = (key, section) => {
    const field = fields.find(f => f.key === key);
    const moved = { ...JSON.parse(JSON.stringify(field)), section };
    moved.goto = {};
    moved.branch = false;
    setFields(
      produce(f =>
        f.splice(
          f.findIndex(x => x.key === key),
          1
        )
      )
    );
    setFields(produce(f => f.push(moved)));
  };

  const removeSection = key => {
    const index = sections.findIndex(s => s.key === key);
    const previous = sections[index - 1].key;
    setFields(
      produce(list => {
        for (const f of list) {
          if (f.section !== key) continue;
          f.section = previous;
          if (
            f.branch &&
            list.some(g => g !== f && g.section === previous && branches(g))
          ) {
            f.branch = false;
          }
        }
        for (const f of list) {
          for (const option of Object.keys(f.goto || {})) {
            if (f.goto[option] === key) f.goto[option] = "";
          }
        }
      })
    );
    setSections(
      produce(list => {
        list.splice(index, 1);
        for (const s of list) {
          if (s.next === key) s.next = "";
        }
      })
    );
  };

  const sectionName = (section, i) => section.title || `Section ${i + 1}`;

  const validTarget = (target, index) =>
    target === "" ||
    target === "submit" ||
    sections.findIndex(s => s.key === target) > index
      ? target
      : "";

  const groups = createMemo(() =>
    groupSections(
      sections.map(s => ({ key: s.key, next: s.next })),
      fields.map(f => ({ section: f.section, goto: gotoOf(f) }))
    )
  );
  const unreachable = createMemo(() => unreachableSections(groups()));

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
        if (!form.can_manage) {
          setRefusal("Only this form's creator or staff can edit it.");
          return;
        }
        setTitle(form.title);
        setDescription(form.description || "");
        setPaymentAmount(
          form.payment_amount ? String(toRupees(form.payment_amount)) : ""
        );
        setIsActive(form.is_active !== false);
        const loadedSections = form.sections?.length
          ? form.sections
          : [newSection()];
        const first = loadedSections[0];
        setSections(
          loadedSections.map(s => ({
            key: s.key,
            title: s.title || "",
            description: s.description || "",
            next: s.next || ""
          }))
        );
        setFields(
          form.fields.map(f => ({
            key: f.key,
            label: f.label,
            type: f.type,
            required: f.required,
            optionsText: (f.options || []).join("\n"),
            section: f.section || first.key,
            branch: Object.keys(f.goto || {}).length > 0,
            goto: { ...f.goto }
          }))
        );
        setLoaded(true);
        if (editorRef) {
          editorRef.innerHTML = form.description || "";
        }
      } catch (err) {
        setRefusal(err.message);
      }
    } else if (fields.length === 0) {
      const section = newSection();
      setSections([section]);
      addField(section.key);
    }
  });

  const sectionOrder = list => {
    const rank = f => sections.findIndex(s => s.key === f.section);
    return [...list].sort((a, b) => rank(a) - rank(b));
  };

  const handleSubmit = async e => {
    e.preventDefault();
    setStatus("");
    setSaving(true);

    const payload = {
      title: title(),
      description: description(),
      payment_amount: paymentAmount() ? toPaise(paymentAmount()) : null,
      is_active: isActive(),
      sections: sections.map((section, i) => ({
        key: section.key,
        title: section.title,
        description: section.description,
        next: validTarget(section.next, i)
      })),
      fields: sectionOrder(fields).map(f => {
        const index = sections.findIndex(s => s.key === f.section);
        const goto = gotoOf(f);
        return {
          key: f.key,
          label: f.label,
          type: f.type,
          required: f.required,
          options: CHOICE_TYPES.includes(f.type) ? optionList(f) : [],
          section: f.section,
          ...(goto && {
            goto: Object.fromEntries(
              Object.entries(goto).map(([o, t]) => [o, validTarget(t, index)])
            )
          })
        };
      })
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
    <div class="pb-24">
      <Breadcrumbs
        icon={documentText}
        pageList={[
          { url: "/forms", name: "Forms" },
          { name: isEdit() ? "Edit form" : "New form" }
        ]}
      />
      <Show
        when={loaded() && !refusal()}
        fallback={
          <Show
            when={refusal()}
            fallback={<p class="mt-3 text-gray-500">Loading...</p>}
          >
            <p role="alert" class="mt-3 text-red-600 dark:text-red-400">
              {refusal()}
            </p>
          </Show>
        }
      >
        <h1 class="break-words text-2xl font-bold text-gray-900 dark:text-white">
          {isEdit() ? "Edit form" : "New form"}
        </h1>

        <div class="mt-4 rounded-lg bg-blue-50 p-4 text-sm text-blue-800 dark:bg-gray-800 dark:text-blue-300">
          The submitter's name, email, and phone are captured automatically and
          shown to whoever manages this form — you don't need to add fields for
          them.
        </div>

        <form class="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-900 dark:text-white">
              Title <span class="text-red-500">*</span>
            </label>
            <input
              id="form-title"
              required
              value={title()}
              onInput={e => setTitle(e.target.value)}
              class="w-full rounded-lg border border-gray-300 p-2.5 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
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
                class="prose prose-sm min-h-[5rem] max-w-none p-2.5 text-gray-900 dark:prose-invert focus:outline-none dark:text-white [&_a]:text-blue-600 [&_a]:underline"
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
              class="w-full rounded-lg border border-gray-300 p-2.5 text-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
            />
          </div>

          <label class="flex min-h-[44px] items-center gap-2 text-sm text-gray-900 dark:text-white">
            <input
              type="checkbox"
              checked={isActive()}
              onChange={e => setIsActive(e.target.checked)}
            />
            Accepting responses
          </label>

          <div class="space-y-6">
            <h2 class="text-lg font-semibold text-gray-900 dark:text-white">
              Sections
            </h2>
            <For each={sections}>
              {(section, i) => {
                const destinations = () => (
                  <>
                    <option value="">Continue to next section</option>
                    <For each={sections.slice(i() + 1)}>
                      {(later, j) => (
                        <option value={later.key}>
                          {sectionName(later, i() + 1 + j())}
                        </option>
                      )}
                    </For>
                    <option value="submit">Submit form</option>
                  </>
                );
                return (
                  <div
                    data-section={i()}
                    class="rounded-lg border border-gray-200 p-4 dark:border-gray-700"
                  >
                    <div class="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                      <h3 class="text-base font-semibold text-gray-900 dark:text-white">
                        Section {i() + 1}
                      </h3>
                      <Show when={i() > 0}>
                        <button
                          type="button"
                          onClick={() => removeSection(section.key)}
                          class="min-h-[44px] rounded-lg border border-red-300 px-3 text-sm text-red-600 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 dark:border-red-700 dark:text-red-400 dark:hover:bg-gray-800"
                        >
                          Remove section
                        </button>
                      </Show>
                    </div>
                    <label class="mt-2 block">
                      <span class={labelClass}>Section title</span>
                      <input
                        placeholder="Section title"
                        value={section.title}
                        onInput={e => setSections(i(), "title", e.target.value)}
                        class={inputClass}
                      />
                    </label>
                    <label class="mt-2 block">
                      <span class={labelClass}>Section description</span>
                      <textarea
                        placeholder="Section description"
                        value={section.description}
                        onInput={e =>
                          setSections(i(), "description", e.target.value)
                        }
                        rows="2"
                        class={inputClass}
                      />
                    </label>

                    <div class="mt-4 space-y-4">
                      <For each={fields.filter(f => f.section === section.key)}>
                        {field => (
                          <div
                            data-question
                            class="rounded-lg border border-gray-200 p-4 dark:border-gray-700"
                          >
                            <div class="flex flex-col items-stretch gap-3 sm:flex-row sm:flex-wrap sm:items-center">
                              <label class="sm:min-w-[12rem] sm:flex-1">
                                <span class={labelClass}>Question</span>
                                <input
                                  required
                                  placeholder="Question"
                                  value={field.label}
                                  onInput={e =>
                                    updateField(
                                      field.key,
                                      "label",
                                      e.target.value
                                    )
                                  }
                                  class={inputClass}
                                />
                              </label>
                              <select
                                aria-label="Question type"
                                value={field.type}
                                onChange={e => {
                                  updateField(
                                    field.key,
                                    "type",
                                    e.target.value
                                  );
                                  updateField(field.key, "branch", false);
                                }}
                                class={`${inputClass} sm:w-auto`}
                              >
                                <For each={FIELD_TYPES}>
                                  {t => (
                                    <option value={t.value}>{t.label}</option>
                                  )}
                                </For>
                              </select>
                              <label class="flex min-h-[44px] items-center gap-2 text-sm text-gray-900 dark:text-white">
                                <input
                                  type="checkbox"
                                  checked={field.required}
                                  onChange={e =>
                                    updateField(
                                      field.key,
                                      "required",
                                      e.target.checked
                                    )
                                  }
                                />
                                Required
                              </label>
                              <button
                                type="button"
                                onClick={() => removeField(field.key)}
                                class="min-h-[44px] self-start rounded-lg px-0 text-sm text-red-600 hover:underline focus:outline-none focus:ring-2 focus:ring-red-500 dark:text-red-400 sm:px-3"
                              >
                                Remove
                              </button>
                            </div>
                            <Show when={sections.length > 1}>
                              <label class="mt-3 block text-sm text-gray-900 dark:text-white">
                                <span class={labelClass}>Section</span>
                                <select
                                  value={field.section}
                                  onChange={e =>
                                    moveField(field.key, e.target.value)
                                  }
                                  class={`${inputClass} sm:w-auto`}
                                >
                                  <For each={sections}>
                                    {(s, j) => (
                                      <option value={s.key}>
                                        {sectionName(s, j())}
                                      </option>
                                    )}
                                  </For>
                                </select>
                              </label>
                            </Show>
                            <Show when={CHOICE_TYPES.includes(field.type)}>
                              <label class="mt-3 block">
                                <span class={labelClass}>Options</span>
                                <textarea
                                  placeholder="Options (one per line)"
                                  value={field.optionsText}
                                  onInput={e =>
                                    updateField(
                                      field.key,
                                      "optionsText",
                                      e.target.value
                                    )
                                  }
                                  rows="3"
                                  class={inputClass}
                                />
                              </label>
                            </Show>
                            <Show when={BRANCH_TYPES.includes(field.type)}>
                              <label class="mt-3 flex min-h-[44px] items-center gap-2 text-sm text-gray-900 dark:text-white">
                                <input
                                  type="checkbox"
                                  checked={field.branch}
                                  disabled={
                                    !field.branch && hasBranchingSibling(field)
                                  }
                                  onChange={e =>
                                    updateField(
                                      field.key,
                                      "branch",
                                      e.target.checked
                                    )
                                  }
                                />
                                Go to section based on answer
                              </label>
                              <Show
                                when={
                                  !field.branch && hasBranchingSibling(field)
                                }
                              >
                                <p class="text-sm text-gray-600 dark:text-gray-400">
                                  Another question in this section already
                                  decides where to go
                                </p>
                              </Show>
                              <Show when={field.branch}>
                                <div class="mt-2 space-y-2 border-l-2 border-gray-200 pl-3 dark:border-gray-700">
                                  <For each={optionList(field)}>
                                    {option => (
                                      <label class="flex flex-col gap-1 text-sm text-gray-900 dark:text-white sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
                                        <span class="break-words sm:min-w-[6rem]">
                                          {option}
                                        </span>
                                        <select
                                          data-option={option}
                                          value={field.goto?.[option] || ""}
                                          onChange={e =>
                                            updateField(
                                              field.key,
                                              "goto",
                                              option,
                                              e.target.value
                                            )
                                          }
                                          class={`${inputClass} sm:w-auto`}
                                        >
                                          {destinations()}
                                        </select>
                                      </label>
                                    )}
                                  </For>
                                </div>
                              </Show>
                            </Show>
                          </div>
                        )}
                      </For>
                      <button
                        type="button"
                        onClick={() => addField(section.key)}
                        class={buttonClass}
                      >
                        + Add question
                      </button>
                    </div>

                    <Show when={i() < sections.length - 1}>
                      <label class="mt-4 block text-sm text-gray-900 dark:text-white">
                        <span class={labelClass}>After this section</span>
                        <select
                          data-next
                          value={section.next}
                          onChange={e =>
                            setSections(i(), "next", e.target.value)
                          }
                          class={`${inputClass} sm:w-auto`}
                        >
                          {destinations()}
                        </select>
                      </label>
                    </Show>
                    <Show when={unreachable().has(i())}>
                      <p class="mt-3 rounded-lg bg-amber-50 p-2 text-sm text-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
                        No answer leads to this section yet.
                      </p>
                    </Show>
                  </div>
                );
              }}
            </For>
            <button type="button" onClick={addSection} class={buttonClass}>
              + Add section
            </button>
          </div>

          <Show when={status()}>
            <p class="text-sm text-red-600 dark:text-red-400">{status()}</p>
          </Show>

          <button
            type="submit"
            disabled={saving()}
            class="min-h-[44px] rounded-lg bg-blue-600 px-5 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-gray-400"
          >
            {saving() ? "Saving..." : isEdit() ? "Save changes" : "Create form"}
          </button>
        </form>
      </Show>
    </div>
  );
};

export default FormBuilder;
