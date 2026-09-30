import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import {
  chatBubbleOvalLeftEllipsis,
  lockClosed
} from "solid-heroicons/outline";
import { Show } from "solid-js";

import { CategoryChip, formatDate, StatusBadge } from "../../tickets";
import UpvoteButton from "./UpvoteButton";

/**
 * One ticket in the list. The title's link stretches over the whole row, and
 * the vote pill sits above it, so the row opens the ticket and the pill votes.
 */
const TicketRow = props => (
  <li class="relative flex gap-4 px-4 py-4 transition-colors duration-150 focus-within:bg-gray-50 hover:bg-gray-50 motion-reduce:transition-none dark:focus-within:bg-gray-700/50 dark:hover:bg-gray-700/50 sm:px-6">
    <div class="relative z-10 shrink-0">
      <UpvoteButton ticket={props.ticket} userId={props.userId} />
    </div>
    <div class="min-w-0 flex-1">
      <A
        href={`/tickets/${props.ticket.id}`}
        class="break-words text-base font-semibold text-gray-900 after:absolute after:inset-0 focus:outline-none focus-visible:underline dark:text-white"
      >
        {props.ticket.title}
        <Show when={props.ticket.is_private}>
          <Icon
            path={lockClosed}
            class="ml-1.5 inline h-4 w-4 align-[-2px] text-gray-500"
            aria-hidden="true"
          />
          <span class="sr-only"> (private)</span>
        </Show>
      </A>
      <div class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-gray-600 dark:text-gray-400">
        <StatusBadge status={props.ticket.status} />
        <CategoryChip category={props.ticket.category} />
        <span>{props.ticket.created_by.first_name}</span>
        <span aria-hidden="true">·</span>
        <time datetime={props.ticket.created_at}>
          {formatDate(props.ticket.created_at)}
        </time>
        <span aria-hidden="true">·</span>
        <span class="inline-flex items-center gap-1">
          <Icon
            path={chatBubbleOvalLeftEllipsis}
            class="h-4 w-4"
            aria-hidden="true"
          />
          <span class="sr-only">Replies:</span>
          {props.ticket.message_count}
        </span>
        <Show when={props.isStaff}>
          <span aria-hidden="true">·</span>
          <span>#{props.ticket.id}</span>
        </Show>
      </div>
    </div>
  </li>
);

export default TicketRow;
