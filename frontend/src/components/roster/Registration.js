import clsx from "clsx";
import { Show } from "solid-js";

import EditRosteredPlayer from "./EditRosteredPlayer";
import RemoveFromRoster from "./RemoveFromRoster";
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
  <div
    class={clsx(
      "mr-6 flex w-full items-center justify-between gap-x-4 pr-2",
      props.isTeamAdmin ? "py-4" : "py-2"
    )}
  >
    <div class="flex items-center gap-x-4 font-medium">
      <div>
        {props.registration?.player?.full_name}
        <Show
          when={props.registration.player?.gender}
        >{` (${props.registration.player?.gender})`}</Show>
        <Show
          when={props.registration.player?.commentary_info?.jersey_number}
        >{` | ${props.registration.player?.commentary_info?.jersey_number}`}</Show>
      </div>
      <div>
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
    <div class="flex gap-x-3 justify-self-end">
      <Show when={props.canRemovePlayer}>
        <RemoveFromRoster
          regId={props.registration.id}
          eventId={props.registration.event_id}
          teamId={props.registration.team_id}
          playerName={props.registration.player?.full_name}
          removeMutation={props.removeMutation}
        />
      </Show>
      <Show when={props.canEditPlayer}>
        <EditRosteredPlayer
          registration={props.registration}
          eventId={props.registration.event_id}
          teamId={props.registration.team_id}
          playerName={props.registration.player?.full_name}
          updateRegistrationMutation={props.updateMutation}
        />
      </Show>
    </div>
  </div>
);

export default Registration;
