import { createSignal, createEffect, Show } from "solid-js";
import { useNavigate } from "@solidjs/router";

const Player = props => {
  const navigate = useNavigate();

  const navMembership = (e, playerId) => {
    e.preventDefault();
    navigate(`/membership/${playerId}`);
  };

  return (
    <div class="relative overflow-x-auto">
      <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
        <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
          <tr>
            <th scope="col" class="px-6 py-3">
              Field
            </th>
            <th scope="col" class="px-6 py-3">
              Value
            </th>
          </tr>
        </thead>
        <tbody>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Name
            </th>
            <td class="px-6 py-4">{props.player?.full_name}</td>
          </tr>
          <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
            <th
              scope="row"
              class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
            >
              Date of Birth
            </th>
            <td class="px-6 py-4">{props.player?.date_of_birth}</td>
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
            <td class="px-6 py-4">{props.player?.state_ut}</td>
          </tr>
          {/* FIXME: Add more rows with other player information */}
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
                {props.player?.membership.start_date} &mdash;{" "}
                {props.player?.membership.end_date}
                <Show when={!props.player?.membership?.is_active}>
                  <button
                    type="submit"
                    class="mx-10 text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                    onclick={e => navMembership(e, props.player?.id)}
                  >
                    Renew
                  </button>
                </Show>
              </td>
            </tr>
          </Show>
          <Show when={!props.player?.membership}>
            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
              <th
                scope="row"
                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
              >
                Membership
              </th>
              <td class="px-6 py-4">
                <button
                  type="submit"
                  class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                  onclick={e => navMembership(e, props.player?.id)}
                >
                  Enroll
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
