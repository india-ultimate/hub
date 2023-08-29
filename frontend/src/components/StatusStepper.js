import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { A } from "@solidjs/router";

import {
  identification,
  currencyRupee,
  shieldExclamation,
  shieldCheck,
  handThumbUp,
  handThumbDown,
  arrowTopRightOnSquare
} from "solid-heroicons/solid-mini";

const Step = props => {
  const liClass = clsx(
    props?.color !== "gray"
      ? `flex w-full items-center text-${props.color}-600 dark:text-${props.color}-500 space-x-2.5`
      : "flex w-full items-center space-x-2.5 text-gray-500 dark:text-gray-400"
  );
  const iconClass = clsx(
    "flex items-center justify-center w-10 h-10 rounded-full lg:h-12 lg:w-12 shrink-0",
    props?.color && `bg-${props.color}-100 dark:bg-${props.color}-700`,
    !props?.color && "bg-gray-100 dark:bg-gray-700"
  );
  return (
    <li class={liClass}>
      <A class="flex items-center" href={props.link || ""}>
        <span class={iconClass}>
          <Icon path={props.icon} style={{ width: "20px" }} />
        </span>
        <span class="ml-2">
          <h3 class="font-medium">{props.title}</h3>
        </span>
      </A>
    </li>
  );
};

const StatusStepper = props => {
  return (
    <ol class="items-center w-full my-4 sm:flex sm:space-x-8">
      <Step
        title="Profile Info"
        link="/"
        icon={identification}
        color={props?.player ? "green" : "red"}
      />
      <Step
        title="Vaccine Info"
        icon={props?.player?.vaccination ? shieldCheck : shieldExclamation}
        link={`/vaccination/${props.player.id}`}
        color={props?.player?.vaccination ? "green" : "red"}
      />
      <Step
        title="Ultimate Central profile"
        icon={arrowTopRightOnSquare}
        link={`/uc-login/${props.player.id}`}
        color={props?.player?.ultimate_central_id ? "green" : "red"}
      />
      <Step
        title="Membership info"
        icon={currencyRupee}
        link={`/membership/${props.player.id}`}
        color={props?.player?.membership?.is_active ? "green" : "red"}
      />
      <Step
        title="Liability Waiver"
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
