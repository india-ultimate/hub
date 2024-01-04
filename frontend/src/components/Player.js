import { useNavigate } from "@solidjs/router";
import { For, Match, Show, Switch } from "solid-js";

import { genderChoices, occupationChoices, stateChoices } from "../constants";
import { displayDate } from "../utils";
import { getLabel } from "../utils";
import StatusStepper from "./StatusStepper";
import VaccinationInformation from "./VaccinationInformation";

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
          class="mb-4 rounded-lg bg-blue-50 p-4 text-sm text-blue-800 dark:bg-gray-800 dark:text-blue-400"
          role="alert"
        >
          Your profile information has been imported from the India Ultimate
          Membership form for 2022-2023.
        </div>
      </Show>
      <table class="w-full break-all text-left text-sm text-gray-500 dark:text-gray-400">
        <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
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
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
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
                    class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 sm:w-auto dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
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
                        class="mr-2 inline-flex items-center justify-center rounded border border-blue-400 bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-800 hover:bg-blue-200 dark:bg-gray-700 dark:text-blue-400"
                      >
                        {team.name}
                      </a>
                    )}
                  </For>
                </Match>
              </Switch>
            </td>
          </tr>
          <Show when={props.player?.membership}>
            <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
              <th
                scope="row"
                class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
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
                    You need a valid India Ultimate membership to participate in
                    India Ultimate events.
                  </p>
                  <button
                    type="submit"
                    class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 sm:w-auto dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                    onClick={e => navMembership(e, props.player?.id)}
                  >
                    Renew
                  </button>
                </Show>
              </td>
            </tr>
            <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
              <th
                scope="row"
                class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
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
                      class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 sm:w-auto dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
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
            <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
              <th
                scope="row"
                class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
              >
                Membership
              </th>
              <td class="px-6 py-4">
                <p class="mb-4">
                  You need a India Ultimate membership to participate in India
                  Ultimate events.
                </p>
                <button
                  type="submit"
                  class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 sm:w-auto dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
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
            <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
              <th
                scope="row"
                class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
              >
                Vaccination details
              </th>
              <td class="px-6 py-4">
                <p class="mb-4">Your vaccination information is not complete</p>
                <button
                  type="submit"
                  class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 sm:w-auto dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                  onClick={e => navVaccination(e, props.player?.id)}
                >
                  Update
                </button>
              </td>
            </tr>
          </Show>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Phone number
            </th>
            <td class="px-6 py-4">{props.player?.phone}</td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Email
            </th>
            <td class="px-6 py-4">{props.player?.email}</td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Date of Birth
            </th>
            <td class="px-6 py-4">
              {props.player?.date_of_birth &&
                displayDate(props.player.date_of_birth)}
            </td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              City
            </th>
            <td class="px-6 py-4">{props.player?.city}</td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              State
            </th>
            <td class="px-6 py-4">
              {getLabel(stateChoices, props.player?.state_ut)}
            </td>
          </tr>
          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
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

          <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
            <th
              scope="row"
              class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
            >
              Occupation
            </th>
            <td class="px-6 py-4">
              {getLabel(occupationChoices, props.player?.occupation)}
            </td>
          </tr>
          <Show when={props.player?.educational_institution}>
            <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
              <th
                scope="row"
                class="whitespace-nowrap px-6 py-4 font-medium text-gray-900 dark:text-white"
              >
                Educational Institution
              </th>
              <td class="px-6 py-4">{props.player?.educational_institution}</td>
            </tr>
          </Show>
        </tbody>
      </table>
    </div>
  );
};

export default Player;
