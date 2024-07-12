import { Show } from "solid-js";

import CaptainBadge from "./role-badges/Captain";
import CoachBadge from "./role-badges/Coach";
import ManagerBadge from "./role-badges/Manager";
import SpiritCaptainBadge from "./role-badges/SpiritCaptain";

const isCaptain = registration => registration?.role === "CAP";

const isSpiritCaptain = registration => registration?.role === "SCAP";

const isCoach = registration =>
  registration?.role === "COACH" || registration?.role === "ACOACH";

const isManager = registration => registration?.role === "MNGR";

const Registration = props => (
  <div class="mr-6 flex w-full items-center justify-between space-x-4 py-3 pr-2">
    <div class="flex items-center gap-x-4">
      <div class="font-medium">
        <div>
          {props.registration?.player?.full_name}
          <Show
            when={props.registration.player?.gender}
          >{` (${props.registration.player?.gender})`}</Show>
        </div>
      </div>
      <Show when={isCaptain(props.registration)}>
        <CaptainBadge />
      </Show>
      <Show when={isSpiritCaptain(props.registration)}>
        <SpiritCaptainBadge />
      </Show>
      <Show when={isManager(props.registration)}>
        <ManagerBadge />
      </Show>
      <Show when={isCoach(props.registration)}>
        <CoachBadge />
      </Show>
    </div>
  </div>
);

export default Registration;
