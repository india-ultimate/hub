import { Show, Switch, Match } from "solid-js";
import { useNavigate } from "@solidjs/router";
import { displayDate } from "../utils";
import VaccinationInformation from "./VaccinationInformation";
import StatusStepper from "./StatusStepper";
import { getLabel } from "../utils";
import { stateChoices } from "../constants";

const Player = props => {
  const navigate = useNavigate();

  const navMembership = (e, playerId) => {
    e.preventDefault();
    navigate(`/membership/${playerId}`);
  };

  const navWaiver = (e, playerId) => {
    e.preventDefault();
    navigate(`/waiver/${playerId}`);
  };

  const navVaccination = (e, playerId) => {
    e.preventDefault();
    navigate(`/vaccination/${playerId}`);
  };

  return (
    <div class="relative overflow-x-auto">
      <StatusStepper player={props.player} />
      <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
        <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
          <tr>
            <th scope="col" class="px-6 py-3">
              Name
            </th>
            <th scope="col" class="px-6 py-3">
              {props.player?.full_name}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Date of Birth
            </th>
            <td class="px-6 py-4">
              {props.player?.date_of_birth &&
                displayDate(props.player.date_of_birth)}
            </td>
          </tr>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              City
            </th>
            <td class="px-6 py-4">{props.player?.city}</td>
          </tr>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              State
            </th>
            <td class="px-6 py-4">
              {getLabel(stateChoices, props.player?.state_ut)}
            </td>
          </tr>
          <Show when={props.player?.membership}>
            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
              <th
                scope="row"
                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
              >
                Membership number
              </th>
              <td class="px-6 py-4">
                {props.player?.membership.membership_number}
              </td>
            </tr>
            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
              <th
                scope="row"
                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
              >
                Membership validity
              </th>
              <td class="px-6 py-4">
                {props.player?.membership.start_date &&
                  displayDate(props.player.membership.start_date)}{" "}
                &mdash;{" "}
                {props.player?.membership.end_date &&
                  displayDate(props.player.membership.end_date)}
                <Show when={!props.player?.membership?.is_active}>
                  <p class="mb-4">
                    You need a valid UPAI membership to participate in UPAI
                    events.
                  </p>
                  <button
                    type="submit"
                    class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                    onClick={e => navMembership(e, props.player?.id)}
                  >
                    Renew
                  </button>
                </Show>
              </td>
            </tr>
            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
              <th
                scope="row"
                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
              >
                Waiver
              </th>
              <td class="px-6 py-4">
                <Switch>
                  <Match when={props.player?.membership.waiver_valid}>
                    Signed by {props.player?.membership.waiver_signed_by} on{" "}
                    {displayDate(props.player?.membership.waiver_signed_at)}
                  </Match>
                  <Match when={!props.player?.membership.waiver_valid}>
                    <button
                      type="submit"
                      class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                      onClick={e => navWaiver(e, props.player?.id)}
                    >
                      Sign Waiver
                    </button>
                  </Match>
                </Switch>
              </td>
            </tr>
          </Show>
          <Show when={!props.player?.membership && !props.others}>
            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
              <th
                scope="row"
                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
              >
                Membership
              </th>
              <td class="px-6 py-4">
                <p class="mb-4">
                  You need a UPAI membership to participate in UPAI events.
                </p>
                <button
                  type="submit"
                  class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                  onClick={e => navMembership(e, props.player?.id)}
                >
                  Enroll
                </button>
              </td>
            </tr>
          </Show>
          <Show when={props.player?.vaccination}>
            <VaccinationInformation vaccination={props.player?.vaccination} />
          </Show>
          <Show when={!props.player?.vaccination}>
            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
              <th
                scope="row"
                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
              >
                Vaccination details
              </th>
              <td class="px-6 py-4">
                <p class="mb-4">Your vaccination information is not complete</p>
                <button
                  type="submit"
                  class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                  onClick={e => navVaccination(e, props.player?.id)}
                >
                  Update
                </button>
              </td>
            </tr>
          </Show>
        </tbody>
      </table>
    </div>
  );
};

export default Player;
