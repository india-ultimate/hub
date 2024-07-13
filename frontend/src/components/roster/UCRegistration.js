import { Show } from "solid-js";

import CaptainBadge from "./role-badges/Captain";
import SpiritCaptainBadge from "./role-badges/SpiritCaptain";

const isCaptain = registration => {
  return (
    registration?.roles?.includes("captain") ||
    registration?.roles?.includes("Captain")
  );
};

const isSpiritCaptain = registration => {
  return (
    registration?.roles?.includes("spirit captain") ||
    registration?.roles?.includes("Spirit Captain")
  );
};

const UCRegistration = props => (
  <div class="mr-4 flex w-full items-center gap-x-4 py-3 pr-2">
    <img
      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
      src={props.registration.person.image_url}
      alt="Bordered avatar"
    />
    <div class="font-medium">
      <div>
        {props.registration.person.first_name +
          " " +
          props.registration.person.last_name}
        <Show
          when={props.registration.person?.player?.gender}
        >{` (${props.registration.person?.player?.gender})`}</Show>
      </div>
    </div>
    <Show when={isCaptain(props.registration)}>
      <CaptainBadge />
    </Show>
    <Show when={isSpiritCaptain(props.registration)}>
      <SpiritCaptainBadge />
    </Show>
  </div>
);

export default UCRegistration;
