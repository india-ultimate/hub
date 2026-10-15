import { createSignal, Show } from "solid-js";

// A switch for "can post announcements": a checkbox that looks like one.
// `onChange` returns a promise that settles once the page shows the new value.
const PostSwitch = props => {
  const [saving, setSaving] = createSignal(false);
  const [error, setError] = createSignal("");

  const change = async checked => {
    setError("");
    setSaving(true);
    try {
      await props.onChange(checked);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <label class="inline-flex min-h-[44px] cursor-pointer items-center gap-3 text-sm text-gray-900 has-[:disabled]:cursor-not-allowed dark:text-white">
        <input
          type="checkbox"
          role="switch"
          class="peer sr-only"
          checked={props.checked}
          disabled={props.disabled || saving()}
          onChange={e => {
            const { checked } = e.currentTarget;
            // Show what the server has until it confirms the change.
            e.currentTarget.checked = props.checked;
            change(checked);
          }}
        />
        <span
          aria-hidden="true"
          class="relative h-6 w-11 shrink-0 rounded-full bg-gray-400 transition-colors after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-transform peer-checked:bg-blue-700 peer-checked:after:translate-x-5 peer-focus-visible:ring-2 peer-focus-visible:ring-blue-500 peer-focus-visible:ring-offset-2 peer-disabled:opacity-50 motion-reduce:transition-none motion-reduce:after:transition-none"
        />
        <span>{props.label}</span>
      </label>
      <Show when={saving()}>
        <p role="status" class="text-xs text-gray-600 dark:text-gray-400">
          Saving…
        </p>
      </Show>
      <Show when={error()}>
        <p role="alert" class="text-xs text-red-700 dark:text-red-400">
          {error()}
        </p>
      </Show>
    </div>
  );
};

export default PostSwitch;
