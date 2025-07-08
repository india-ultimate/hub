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
  <div class={clsx("pr-2", props.isTeamAdmin ? "py-3" : "py-2")}>
    <div class={clsx("flex w-full items-center justify-between gap-x-4")}>
      <div class="flex items-center gap-x-4 font-medium">
        <Show
          when={props.registration?.player?.profile_pic_url}
          fallback={
            <div class="flex h-10 w-10 items-center justify-center rounded-full bg-gray-200">
              <span class="text-sm text-gray-500">
                {props.registration?.player?.full_name
                  ?.charAt(0)
                  ?.toUpperCase() || "?"}
              </span>
            </div>
          }
        >
          <img
            src={props.registration?.player?.profile_pic_url}
            alt={props.registration?.player?.full_name}
            class="inline-block h-10 w-10 rounded-full"
          />
        </Show>

        <div class="flex flex-col">
          <span class="flex items-center gap-x-2">
            {props.registration?.player?.full_name}
            <Show
              when={props.registration.player?.gender}
            >{` (${props.registration.player?.gender})`}</Show>
            <Show
              when={props.registration.player?.commentary_info?.jersey_number}
            >
              <span class="text-sm italic text-gray-400">
                {` #${props.registration.player?.commentary_info?.jersey_number}`}
              </span>
            </Show>
          </span>
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
      </div>
      <div class="flex gap-x-3 justify-self-end">
        <Show when={props.canRemovePlayer}>
          <RemoveFromRoster
            regId={props.registration.id}
            eventId={props.registration.event_id}
            teamId={props.registration.team?.id}
            playerName={props.registration.player?.full_name}
            removeMutation={props.removeMutation}
          />
        </Show>
        <Show when={props.canEditPlayer}>
          <EditRosteredPlayer
            registration={props.registration}
            eventId={props.registration.event_id}
            teamId={props.registration.team?.id}
            playerName={props.registration.player?.full_name}
            updateRegistrationMutation={props.updateMutation}
          />
        </Show>
      </div>
    </div>
  </div>
);

export default Registration;
