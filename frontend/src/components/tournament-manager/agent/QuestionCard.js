import { createSignal, For, Show } from "solid-js";

/**
 * The agent's clarifying question, rendered on the AI surface. Single/multi
 * select options as a quiet bordered list, a free-text "other" on every
 * question, and Submit / Skip actions.
 */
const QuestionCard = props => {
  const q = () => props.question;
  const [selected, setSelected] = createSignal([]);
  const [other, setOther] = createSignal("");

  const toggle = id => {
    if (q().selection_mode === "single") {
      setSelected([id]);
      return;
    }
    const cur = selected();
    if (cur.includes(id)) {
      setSelected(cur.filter(x => x !== id));
    } else {
      setSelected([...cur, id]);
    }
  };

  const canSubmit = () => selected().length > 0 || !!other().trim();

  return (
    <div
      class="mt-3 rounded-lg border p-4"
      style={{
        "border-color": "rgb(217 119 6 / 0.4)",
        "background-color": "var(--agent-raised)"
      }}
      role="group"
      aria-label="Clarifying question"
    >
      <div class="mb-2 flex items-center gap-2">
        <svg
          class="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-500"
          aria-hidden="true"
          xmlns="http://www.w3.org/2000/svg"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5ZM9.5 4a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM12 15H8a1 1 0 0 1 0-2h1v-3H8a1 1 0 0 1 0-2h2a1 1 0 0 1 1 1v4h1a1 1 0 0 1 0 2Z" />
        </svg>
        <span class="text-[11px] font-medium uppercase tracking-wide text-amber-700 dark:text-amber-500">
          Clarifying question
        </span>
      </div>
      <p
        class="mb-1 text-sm font-semibold"
        style={{ color: "var(--agent-ink)" }}
      >
        {q().prompt}
      </p>
      <Show when={q().context}>
        <p class="mb-3 text-xs" style={{ color: "var(--agent-ink-muted)" }}>
          {q().context}
        </p>
      </Show>

      <div class="mb-3 mt-2 space-y-1.5">
        <For each={q().options || []}>
          {opt => (
            <label
              for={`agent-q-${q().id}-${opt.id}`}
              class="flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 transition-colors duration-150 hover:bg-black/[0.03] dark:hover:bg-white/[0.05]"
              style={{
                "border-color": selected().includes(opt.id)
                  ? "var(--agent-accent)"
                  : "var(--agent-line)"
              }}
            >
              <input
                id={`agent-q-${q().id}-${opt.id}`}
                type={q().selection_mode === "single" ? "radio" : "checkbox"}
                name={`agent-q-${q().id}`}
                value={opt.id}
                checked={selected().includes(opt.id)}
                onChange={() => toggle(opt.id)}
                disabled={props.disabled}
                class="mt-0.5 h-4 w-4 shrink-0"
                style={{ "accent-color": "var(--agent-accent)" }}
              />
              <span class="min-w-0">
                <span
                  class="block text-sm font-medium"
                  style={{ color: "var(--agent-ink)" }}
                >
                  {opt.label}
                </span>
                <Show when={opt.description}>
                  <span
                    class="mt-0.5 block text-xs"
                    style={{ color: "var(--agent-ink-muted)" }}
                  >
                    {opt.description}
                  </span>
                </Show>
              </span>
            </label>
          )}
        </For>
      </div>

      <div class="mb-3">
        <label
          for={`agent-q-other-${q().id}`}
          class="mb-1.5 block text-xs font-medium"
          style={{ color: "var(--agent-ink-muted)" }}
        >
          Or type your own answer
        </label>
        <input
          id={`agent-q-other-${q().id}`}
          type="text"
          class="block w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 disabled:opacity-50"
          style={{
            "border-color": "var(--agent-line-strong)",
            "background-color": "var(--agent-canvas)",
            color: "var(--agent-ink)"
          }}
          placeholder="Type another option…"
          value={other()}
          onInput={e => setOther(e.target.value)}
          disabled={props.disabled}
        />
      </div>

      <div class="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          class="cursor-pointer rounded-md bg-amber-700 px-4 py-1.5 text-xs font-medium text-white transition-colors duration-150 hover:bg-amber-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-amber-600 dark:hover:bg-amber-700"
          disabled={props.disabled || !canSubmit()}
          onClick={() =>
            props.onSubmit?.({
              selected_ids: selected(),
              other_text: other().trim() || null,
              skip: false
            })
          }
        >
          Submit
        </button>
        <button
          type="button"
          class="cursor-pointer rounded-md border px-4 py-1.5 text-xs font-medium transition-colors duration-150 hover:bg-black/[0.04] focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-white/[0.06]"
          style={{
            "border-color": "var(--agent-line-strong)",
            color: "var(--agent-ink-muted)"
          }}
          disabled={props.disabled}
          onClick={() => props.onSubmit?.({ selected_ids: [], skip: true })}
        >
          Skip
        </button>
      </div>
    </div>
  );
};

/** Read-only recap of a question after it was answered or skipped. */
export const QuestionSnapshot = props => {
  const q = () => props.question || {};
  const answer = () => q().answer || {};
  const selected = () => new Set((answer().selected_ids || []).map(String));
  const skipped = () => !!(answer().skipped || answer().cancelled);

  return (
    <div
      class="mt-3 rounded-lg border p-4"
      style={{
        "border-color": "var(--agent-line)",
        "background-color": "var(--agent-raised)"
      }}
    >
      <div class="mb-2 flex items-center gap-2">
        <span
          class="text-[11px] font-medium uppercase tracking-wide"
          style={{ color: "var(--agent-ink-muted)" }}
        >
          Question
        </span>
        <Show when={skipped()}>
          <span class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-gray-600 dark:bg-gray-800 dark:text-gray-400">
            Skipped
          </span>
        </Show>
      </div>
      <p
        class="mb-1 text-sm font-semibold"
        style={{ color: "var(--agent-ink)" }}
      >
        {q().prompt}
      </p>
      <Show when={q().context}>
        <p class="mb-2 text-xs" style={{ color: "var(--agent-ink-muted)" }}>
          {q().context}
        </p>
      </Show>
      <ul class="mt-2 space-y-1">
        <For each={q().options || []}>
          {opt => (
            <li
              class="flex items-start gap-2 text-sm"
              style={{
                color: selected().has(String(opt.id))
                  ? "var(--agent-ink)"
                  : "var(--agent-ink-muted)"
              }}
            >
              <span class="mt-0.5 w-3 shrink-0 text-center text-[11px]">
                {selected().has(String(opt.id)) ? "✓" : "•"}
              </span>
              <span>
                {opt.label}
                <Show when={opt.description}>
                  <span class="ml-1 opacity-70">— {opt.description}</span>
                </Show>
              </span>
            </li>
          )}
        </For>
      </ul>
      <Show when={answer().other_text}>
        <p class="mt-2 text-sm" style={{ color: "var(--agent-ink)" }}>
          Own answer: {answer().other_text}
        </p>
      </Show>
    </div>
  );
};

export default QuestionCard;
