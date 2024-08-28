const ErrorPopover = props => (
  <div
    popover
    ref={props.ref}
    role="alert"
    class={
      props.class ??
      "rounded-lg border border-red-400 bg-red-100 px-3 py-3 text-red-800 shadow-xl dark:bg-gray-800 dark:text-red-400"
    }
  >
    {props.children}
  </div>
);

export default ErrorPopover;
