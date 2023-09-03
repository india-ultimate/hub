import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { A } from "@solidjs/router";
import { Switch, Match } from "solid-js";

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
  const status = {
    profile: !!props?.player,
    vaccine: !!props?.player?.vaccination,
    ucLink: !!props?.player?.ultimate_central_id,
    membership: props?.player?.membership?.is_active,
    waiver: props?.player?.membership?.waiver_valid
  };
  const percent = Math.round(
    (Object.values(status).filter(x => x).length * 100) /
      Object.keys(status).length
  );
  return (
    <div class="my-8">
      <div class="flex justify-between my-4">
        <span class="text-base font-medium dark:text-white text-center">
          <div class="text-4xl font-bold text-gray-900 dark:text-white">
            {percent}%
          </div>
          of the profile is complete
        </span>
        <div class="w-full">
          <div class="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700">
            <div
              class={clsx(
                percent < 100 ? "bg-red-400" : "bg-green-600",
                "h-2.5 rounded-full"
              )}
              style={`width: ${percent}%`}
            />
          </div>
          <Switch>
            <Match when={percent < 100}>
              <p class="text-md mt-2">
                Complete the profile to participate in UPAI events
              </p>
              <p class="text-xs mt-2">
                You can click on the incomplete steps (indicated in red) below,
                to complete those steps.
              </p>
            </Match>
            <Match when={percent === 100}>
              <p>Profile complete! 🎉</p>
            </Match>
          </Switch>
        </div>
      </div>
      <ol class="items-center w-full md:flex md:space-x-8 space-y-4 md:space-y-0 mt-2">
        <Step
          title="Profile Info"
          link={`/edit/registration/${props.player.id}`}
          icon={identification}
          color={status.profile ? "green" : "red"}
        />
        <Step
          title="Vaccine Info"
          icon={status.vaccine ? shieldCheck : shieldExclamation}
          link={`/vaccination/${props.player.id}`}
          color={status.vaccine ? "green" : "red"}
        />
        <Step
          title="Ultimate Central profile"
          icon={arrowTopRightOnSquare}
          link={`/uc-login/${props.player.id}`}
          color={status.ucLink ? "green" : "red"}
        />
        <Step
          title="Membership info"
          icon={currencyRupee}
          link={`/membership/${props.player.id}`}
          color={status.membership ? "green" : "red"}
        />
        <Step
          title="Liability Waiver"
          icon={status.waiver ? handThumbUp : handThumbDown}
          color={status.waiver ? "green" : "red"}
          link={`/waiver/${props.player.id}`}
          last={true}
        />
      </ol>
    </div>
  );
};

export default StatusStepper;
