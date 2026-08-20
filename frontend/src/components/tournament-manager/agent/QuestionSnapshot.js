import { For, Show } from "solid-js";

/**
 * Read-only recap of a question after it was answered or skipped.
 *
 * Default export only: solid-hot-loader wraps every .js under components/ and
 * drops named exports (same reason QuestionCard is imported as default).
 */
const QuestionSnapshot = props => {
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

export default QuestionSnapshot;
