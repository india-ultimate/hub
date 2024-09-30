import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { arrowTrendingUp, chevronRight } from "solid-heroicons/solid";
import { Show } from "solid-js";

const ViewStatsButton = props => {
  return (
    <button
      class={clsx(
        "group relative inline-flex items-center justify-center overflow-hidden rounded-full p-0.5 text-xs font-medium",
        "text-gray-900 focus:outline-none dark:text-white",
        "transition-all duration-75 ease-in hover:scale-105"
      )}
    >
      <span
        class={clsx(
          "relative inline-flex items-center rounded-full px-2 py-1.5 transition-all duration-75 ease-in group-hover:shadow-lg dark:bg-gray-700",
          props.bgColor
        )}
      >
        <Show
          when={props.match?.status !== "COM"}
          fallback={
            <>
              <span
                class={clsx(
                  "me-2 rounded-full px-2.5 py-0.5 text-white",
                  props.badgeColor
                )}
              >
                <Icon path={arrowTrendingUp} class="w-4" />
              </span>
              Timeline
              <Icon path={chevronRight} class="ml-1.5 w-4" />
            </>
          }
        >
          <span
            class={clsx(
              "me-2 rounded-full px-2.5 py-0.5 text-white",
              props.badgeColor
            )}
          >
            Live
          </span>
          {props.match?.stats?.score_team_1 +
            " - " +
            props.match?.stats?.score_team_2}
          <Icon path={chevronRight} class="ml-1.5 w-4" />
        </Show>
      </span>
    </button>
  );
};

export default ViewStatsButton;
