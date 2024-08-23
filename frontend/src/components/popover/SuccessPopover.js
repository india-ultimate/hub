const SuccessPopover = props => (
  <div
    popover
    ref={props.ref}
    role="alert"
    class={
      props.class ??
      "rounded-lg border-2 border-green-400 bg-green-200 px-3 py-4 text-green-800 shadow-xl dark:bg-gray-800 dark:text-green-400"
    }
  >
    {props.children}
  </div>
);

export default SuccessPopover;
