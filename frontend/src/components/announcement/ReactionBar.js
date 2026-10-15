import { createMutation, useQueryClient } from "@tanstack/solid-query";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { chatBubbleLeft } from "solid-heroicons/outline";
import { createSignal } from "solid-js";

import { saveReaction, toggled } from "../../reactions";
import Reactions from "./Reactions";

const focusRing =
  "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900";

// An announcement's reactions, and a link down to its comments.
const ReactionBar = props => {
  const queryClient = useQueryClient();
  const [failed, setFailed] = createSignal(false);

  const key = () => ["announcement", props.slug];
  const mutation = createMutation({
    mutationFn: ({ kind, on }) =>
      saveReaction(`/api/announcements/${props.slug}/reactions/${kind}`, on),
    onMutate: async ({ kind, on }) => {
      setFailed(false);
      await queryClient.cancelQueries({ queryKey: key() });
      const previous = queryClient.getQueryData(key());
      queryClient.setQueryData(key(), old =>
        old
          ? { ...old, reactions: toggled(old.reactions || [], kind, on) }
          : old
      );
      return { previous };
    },
    onError: (_error, _vars, context) => {
      queryClient.setQueryData(key(), context?.previous);
      setFailed(true);
    },
    // Toggles can overlap and land out of order: settle on the server's state.
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: key() });
      queryClient.invalidateQueries({ queryKey: ["announcements"] });
    }
  });

  return (
    <Reactions
      testId="reaction-bar"
      reactions={props.reactions}
      onToggle={(kind, on) => mutation.mutate({ kind, on })}
      failed={failed()}
    >
      <button
        type="button"
        onClick={() => props.onCommentsClick?.()}
        class={clsx(
          "ml-auto inline-flex min-h-[44px] items-center gap-1.5 rounded-lg px-2 text-sm font-medium text-gray-600 hover:text-blue-700 dark:text-gray-300 dark:hover:text-blue-300 [@media(pointer:fine)]:min-h-[36px]",
          focusRing
        )}
      >
        <Icon path={chatBubbleLeft} aria-hidden="true" class="h-5 w-5" />
        {props.commentCount} {props.commentCount === 1 ? "comment" : "comments"}
      </button>
    </Reactions>
  );
};

export default ReactionBar;
