import { For } from "solid-js";

/** Quiet chrome: a bare select that reads as a label until you touch it. */
const ModelPicker = props => {
  return (
    <>
      <label for="tournament-agent-model" class="sr-only">
        Model
      </label>
      <select
        id="tournament-agent-model"
        class="cursor-pointer rounded-md border-0 bg-transparent px-1.5 py-1 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        style={{ color: "var(--agent-ink-muted)" }}
        value={props.value || ""}
        disabled={props.disabled}
        onChange={e => props.onChange?.(e.target.value)}
      >
        <For each={props.models || []}>
          {m => (
            <option value={m.id}>
              {m.label}
              {m.hint ? ` — ${m.hint}` : ""}
            </option>
          )}
        </For>
      </select>
    </>
  );
};

export default ModelPicker;
