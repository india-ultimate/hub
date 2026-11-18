import clsx from "clsx";

const PendingBar = props => (
  <div
    role="status"
    class={clsx(
      "animate-pulse rounded bg-gray-200 motion-reduce:animate-none dark:bg-gray-700",
      !/(^| )h-/.test(props.class ?? "") && "h-10",
      props.class
    )}
  >
    <span class="sr-only">{props.label}</span>
  </div>
);

export default PendingBar;
