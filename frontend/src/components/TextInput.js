import clsx from "clsx";
import { createMemo, splitProps } from "solid-js";

import InputError from "./InputError";
import InputLabel from "./InputLabel";

/**
 * Text input field that users can type into. Various decorations can be
 * displayed in or around the field to communicate the entry requirements.
 */
const TextInput = props => {
  // Split input element props
  const [, inputProps] = splitProps(props, [
    "class",
    "value",
    "label",
    "error",
    "padding"
  ]);

  // Create memoized value
  const getValue = createMemo(
    prevValue =>
      props.value === undefined
        ? ""
        : !Number.isNaN(props.value)
        ? props.value
        : prevValue,
    ""
  );

  return (
    <div class={clsx(!props.padding && "px-8 lg:px-10", props.class)}>
      <InputLabel
        name={props.name}
        label={props.label}
        required={props.required}
      />
      <input
        {...inputProps}
        class={clsx(
          "h-14 w-full rounded-2xl border-2 bg-white px-5 outline-none placeholder:text-slate-300 dark:bg-gray-900 dark:placeholder:text-slate-700 md:h-16 md:text-lg lg:h-[70px] lg:px-6 lg:text-xl",
          props.error
            ? "border-red-600/50 dark:border-red-400/50"
            : "border-slate-200 hover:border-slate-300 focus:border-sky-600/50 dark:border-slate-800 dark:hover:border-slate-700 dark:focus:border-sky-400/50"
        )}
        id={props.name}
        value={getValue()}
        aria-invalid={!!props.error}
        aria-errormessage={`${props.name}-error`}
      />
      <InputError name={props.name} error={props.error} />
    </div>
  );
};

export default TextInput;
