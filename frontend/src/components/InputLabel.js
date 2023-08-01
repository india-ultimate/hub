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
          "inline-block font-medium md:text-lg lg:text-xl",
          !props.margin && "mb-4 lg:mb-5"
        )}
        for={props.name}
      >
        {props.label}{" "}
        {props.required && (
          <span class="ml-1 text-red-600 dark:text-red-400">*</span>
        )}
      </label>
    </Show>
  );
};

export default InputLabel;
