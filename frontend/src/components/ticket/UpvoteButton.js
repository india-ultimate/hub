import { createMutation, useQueryClient } from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { chevronUp } from "solid-heroicons/solid";
import { createSignal, Show } from "solid-js";

import { setTicketUpvote } from "../../queries";

// Tickets with a vote on its way. Kept outside the component: the optimistic
// update puts a new ticket object in the cache, a list row keyed on it is
// recreated, and a flag inside the old button would be lost with it. The
// mutation's own loading state is no help either; it changes a tick later.
const saving = new Set();

const withVote = (ticket, upvoted) => ({
  ...ticket,
  has_upvoted: upvoted,
  upvote_count: ticket.upvote_count + (upvoted ? 1 : -1)
});

/**
 * The vote pill: the count, filled blue once you've upvoted. It updates every
 * cached copy of the ticket straight away and puts them back if the server
 * refuses. In a list row it sits above the row's link, so a click votes
 * rather than opening the ticket.
 */
const UpvoteButton = props => {
  const queryClient = useQueryClient();
  const [error, setError] = createSignal("");

  const blocked = () =>
    props.ticket.created_by.id === props.userId
      ? "You can't upvote your own ticket"
      : props.ticket.is_private
      ? "Private tickets can't be upvoted"
      : "";

  // Every list, suggestion and detail copy of this ticket, so all agree
  const apply = upvoted => {
    const id = props.ticket.id;
    queryClient.setQueriesData(
      ["tickets"],
      page =>
        page && {
          ...page,
          items: page.items.map(t => (t.id === id ? withVote(t, upvoted) : t))
        }
    );
    queryClient.setQueryData(
      ["ticket", String(id)],
      ticket => ticket && withVote(ticket, upvoted)
    );
  };

  const mutation = createMutation({
    mutationFn: upvoted => setTicketUpvote(props.ticket.id, upvoted),
    onMutate: upvoted => {
      setError("");
      apply(upvoted);
    },
    onError: (err, upvoted) => {
      apply(!upvoted);
      setError(err.message || "Couldn't save your upvote");
    },
    onSettled: () => {
      saving.delete(props.ticket.id);
      queryClient.invalidateQueries(["tickets"]);
      queryClient.invalidateQueries(["ticket", String(props.ticket.id)]);
    }
  });

  const vote = e => {
    e.preventDefault();
    e.stopPropagation();
    if (blocked() || saving.has(props.ticket.id)) return;
    saving.add(props.ticket.id);
    mutation.mutate(!props.ticket.has_upvoted);
  };

  return (
    <div class="flex flex-col items-center">
      <button
        type="button"
        id={`ticket-upvote-${props.ticket.id}`}
        onClick={vote}
        disabled={Boolean(blocked())}
        title={
          blocked() ||
          (props.ticket.has_upvoted
            ? "Remove your upvote"
            : "Upvote if this affects you too")
        }
        aria-pressed={props.ticket.has_upvoted}
        aria-label={`Upvote: ${props.ticket.upvote_count} ${
          props.ticket.upvote_count === 1 ? "upvote" : "upvotes"
        }`}
        class={clsx(
          "flex flex-col items-center justify-center rounded-lg border font-semibold transition-colors duration-150 focus:outline-none focus-visible:ring-4 focus-visible:ring-blue-300 disabled:cursor-not-allowed motion-reduce:transition-none dark:focus-visible:ring-blue-800",
          props.size === "lg" ? "h-16 w-16 text-lg" : "h-14 w-12 text-sm",
          props.ticket.has_upvoted
            ? "border-blue-700 bg-blue-700 text-white hover:bg-blue-800 dark:border-blue-600 dark:bg-blue-600"
            : "border-gray-300 bg-white text-gray-700 hover:border-blue-500 hover:text-blue-700 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 dark:hover:border-blue-400 dark:hover:text-blue-300",
          blocked() &&
            "opacity-60 hover:border-gray-300 hover:text-gray-700 dark:hover:border-gray-600 dark:hover:text-gray-200"
        )}
      >
        <Icon path={chevronUp} class="h-5 w-5" aria-hidden="true" />
        <span data-testid="upvote-count">{props.ticket.upvote_count}</span>
      </button>
      <Show when={error()}>
        <p
          role="alert"
          class="mt-1 w-24 text-center text-xs text-red-600 dark:text-red-400"
        >
          {error()}
        </p>
      </Show>
    </div>
  );
};

export default UpvoteButton;
