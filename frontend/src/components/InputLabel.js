import clsx from "clsx";
import { Show } from "solid-js";

/**
 * Input label for a form field.
 */
const InputLabel = props => {
  return (
    <Show when={props.label}>
      <label
        class={clsx(
          "inline-block md:text-lg lg:text-xl",
          !props.margin && "mb-4 lg:mb-5"
        )}
        for={props.name}
      >
        <span class="font-medium">
          {props.label}{" "}
          {props.required && (
            <span class="ml-1 text-red-600 dark:text-red-400">*</span>
          )}
        </span>
        <Show when={props.subLabel}>
          <span
            class={clsx(
              "md:text-md mt-1 block text-sm lg:text-lg",
              !props.margin && "mb-4 lg:mb-5"
            )}
          >
            {props.subLabel}
          </span>
        </Show>
      </label>
    </Show>
  );
};

export default InputLabel;
