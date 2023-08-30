import { Show, Switch, Match, For } from "solid-js";
import { useNavigate } from "@solidjs/router";
import { displayDate } from "../utils";
import VaccinationInformation from "./VaccinationInformation";
import StatusStepper from "./StatusStepper";
import { getLabel } from "../utils";
import { genderChoices, occupationChoices, stateChoices } from "../constants";

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

  const navUltimateCentral = (e, playerId) => {
    e.preventDefault();
    navigate(`/uc-login/${playerId}`);
  };

  return (
    <div class="relative overflow-x-auto">
      <StatusStepper player={props.player} />
      <Show when={props.player?.imported_data}>
        <div
          class="p-4 mb-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400"
          role="alert"
        >
          Your profile information has been imported from the UPAI Membership
          form for 2022-2023.
        </div>
      </Show>
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
              Phone number
            </th>
            <td class="px-6 py-4">{props.player?.phone}</td>
          </tr>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Email
            </th>
            <td class="px-6 py-4">{props.player?.email}</td>
          </tr>
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
              Teams
            </th>
            <td class="px-6 py-4">
              <Switch>
                <Match when={!props.player?.ultimate_central_id}>
                  <p class="mb-4">
                    Player's Ultimate Central profile is not linked
                  </p>
                  <button
                    type="submit"
                    class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                    onClick={e => navUltimateCentral(e, props.player?.id)}
                  >
                    Link profile
                  </button>
                </Match>
                <Match when={!props.player?.teams?.length}>
                  <p>No teams associated with player.</p>
                </Match>
                <Match when={props.player?.teams}>
                  <For each={props.player?.teams}>
                    {team => (
                      <a
                        href={`https://indiaultimate.org/en_in/t/${team.ultimate_central_slug}`}
                        class="bg-blue-100 hover:bg-blue-200 text-blue-800 text-xs font-semibold mr-2 px-2.5 py-0.5 rounded dark:bg-gray-700 dark:text-blue-400 border border-blue-400 inline-flex items-center justify-center"
                      >
                        {team.name}
                      </a>
                    )}
                  </For>
                </Match>
              </Switch>
            </td>
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
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Gender
            </th>
            <Show
              when={props.player?.gender != "O"}
              fallback={<td class="px-6 py-4">{props.player?.other_gender}</td>}
            >
              <td class="px-6 py-4">
                {getLabel(genderChoices, props.player?.gender)}
              </td>
            </Show>
          </tr>

          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Occupation
            </th>
            <td class="px-6 py-4">
              {getLabel(occupationChoices, props.player?.occupation)}
            </td>
          </tr>

          <Show when={props.player?.occupation === "Student"}>
            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
              <th
                scope="row"
                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
              >
                Educational Institution
              </th>
              <td class="px-6 py-4">{props.player?.educational_institution}</td>
            </tr>
          </Show>
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
