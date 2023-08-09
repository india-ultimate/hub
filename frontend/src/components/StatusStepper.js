import clsx from "clsx";
import { createSignal, createEffect } from "solid-js";
import { Icon } from "solid-heroicons";
import { A } from "@solidjs/router";

import {
  identification,
  currencyRupee,
  shieldExclamation,
  shieldCheck,
  handThumbUp,
  handThumbDown
} from "solid-heroicons/solid-mini";

const Step = props => {
  const liClass = clsx(
    props?.color !== "gray"
      ? `flex w-full items-center text-${props.color}-600 dark:text-${props.color}-500`
      : "flex w-full items-center",
    !props.last &&
      "after:content-[''] after:w-full after:h-1 after:border-b after:border-4 after:inline-block",
    !props.last &&
      (props.color
        ? `after:border-${props.color}-100 dark:after:border-${props.color}-700`
        : "after:border-gray-100 dark:after:border-gray-700")
  );
  const divClass = clsx(
    "flex items-center justify-center w-10 h-10 rounded-full lg:h-12 lg:w-12 shrink-0",
    props?.color && `bg-${props.color}-100 dark:bg-${props.color}-700`,
    !props?.color && "bg-gray-100 dark:bg-gray-700"
  );
  return (
    <li class={liClass}>
      <div class={divClass}>
        <A href={props.link || ""}>
          <Icon path={props.icon} style="width: 20px" />
        </A>
      </div>
    </li>
  );
};

const StatusStepper = props => {
  return (
    <ol class="flex items-center w-full my-4 sm:mb-5">
      <Step
        link="/"
        icon={identification}
        color={props?.player ? "green" : "red"}
      />
      <Step
        icon={currencyRupee}
        link={`/membership/${props.player.id}`}
        color={props?.player?.membership?.is_active ? "green" : "red"}
      />

      <Step
        icon={props?.player?.vaccination ? shieldCheck : shieldExclamation}
        link={`/vaccination/${props.player.id}`}
        color={props?.player?.vaccination ? "green" : "red"}
      />
      <Step
        icon={
          props?.player?.membership?.waiver_valid ? handThumbUp : handThumbDown
        }
        color={props?.player?.membership?.waiver_valid ? "green" : "red"}
        link={`/waiver/${props.player.id}`}
        last={true}
      />
    </ol>
  );
};

export default StatusStepper;
