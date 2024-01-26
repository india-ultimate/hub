import { A } from "@solidjs/router";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import {
  arrowTopRightOnSquare,
  currencyRupee,
  document,
  documentCheck,
  handThumbDown,
  handThumbUp,
  identification,
  shieldCheck,
  shieldExclamation,
  videoCamera,
  xCircle
} from "solid-heroicons/solid-mini";
import { Match, Switch } from "solid-js";

import { getStatusAndPercent } from "../utils";

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
  const { status, percent } = getStatusAndPercent(props?.player);
  return (
    <div class="my-8">
      <div class="my-4 flex justify-between">
        <span class="text-center text-base font-medium dark:text-white">
          <div class="text-4xl font-bold text-gray-900 dark:text-white">
            {percent}%
          </div>
          of the profile is complete
        </span>
        <div class="w-full">
          <div class="h-2.5 w-full rounded-full bg-gray-200 dark:bg-gray-700">
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
                Complete the profile to participate in India Ultimate events
              </p>
              <p class="mt-2 text-xs">
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
      <ol class="mt-2 w-full items-center space-y-4 md:flex md:space-x-8 md:space-y-0">
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
        />
        <Step
          title="Accreditation"
          icon={
            status.accreditation
              ? props?.player?.accreditation?.level == "ADV"
                ? documentCheck
                : document
              : xCircle
          }
          color={status.accreditation ? "green" : "red"}
          link={`/accreditation/${props.player.id}`}
          last={true}
        />
        <Step
          title="Commentary Info"
          icon={videoCamera}
          color={status.commentary_info ? "green" : "red"}
          link={`/commentary-info/${props.player.id}`}
        />
      </ol>
    </div>
  );
};

export default StatusStepper;
