import { AccordionDownIcon } from "../icons";

// A native disclosure: the browser handles Space/Enter, aria-expanded and
// find-in-page. The chevron turns with CSS, so there is no script to re-run.
const Accordion = props => (
  <details
    class="group border-b border-gray-200 dark:border-gray-700"
    open={props.open}
    name={props.group}
  >
    <summary
      id={`accordion-heading-${props.id}`}
      class="flex min-h-[44px] cursor-pointer list-none items-center justify-between gap-2 rounded-lg py-4 text-left font-medium text-gray-500 hover:text-gray-900 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 group-open:text-gray-900 dark:text-gray-400 dark:hover:text-white dark:focus-visible:ring-blue-800 dark:group-open:text-white [&::-webkit-details-marker]:hidden"
    >
      <span>{props.title}</span>
      <span class="flex items-center gap-2">
        {props.badge}
        <AccordionDownIcon />
      </span>
    </summary>
    <div id={`accordion-body-${props.id}`} class="pb-5 pt-1">
      {props.children}
    </div>
  </details>
);

export default Accordion;
