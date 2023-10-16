import { Match, Switch, Show } from "solid-js";
import { A } from "@solidjs/router";
import { arrowRight, play } from "solid-heroicons/solid";
import { Icon } from "solid-heroicons";

const TournamentMatch = props => {
  return (
    <div class="block py-2 px-1 bg-white border border-blue-600 rounded-lg shadow dark:bg-gray-800 dark:border-blue-400 w-full mb-5">
      <Switch>
        <Match when={props.match.pool}>
          <p class="text-center text-sm mb-2">Pool - {props.match.pool.name}</p>
        </Match>
        <Match when={props.match.cross_pool}>
          <p class="text-center text-sm mb-2">Cross Pool</p>
        </Match>
        <Match when={props.match.bracket}>
          <p class="text-center text-sm mb-2">
            Bracket - {props.match.bracket.name}
          </p>
        </Match>
        <Match when={props.match.position_pool}>
          <p class="text-center text-sm mb-2">
            Position Pool - {props.match.position_pool.name}
          </p>
        </Match>
      </Switch>
      <div class="flex justify-center text-sm">
        {/* Show current team page as first */}
        {/* Current team page doesn't need to be clickable, we're already on that page */}
        <Show
          when={props.match[`team_${props.currentTeamNo}`]}
          fallback={
            <span class="w-1/3 text-center font-bold">
              {props.match[`placeholder_seed_${props.currentTeamNo}`]}
            </span>
          }
        >
          <img
            class="w-6 h-6 p-1 rounded-full ring-2 ring-blue-500 dark:ring-blue-400 inline-block mr-1"
            src={
              props.teamsMap()[props.match[`team_${props.currentTeamNo}`].id]
                ?.image_url
            }
            alt="Bordered avatar"
          />
          <span class="w-1/3 text-center font-bold dark:text-blue-400 text-blue-500">
            {props.match[`team_${props.currentTeamNo}`].name +
              ` (${props.match[`placeholder_seed_${props.currentTeamNo}`]})`}
          </span>
        </Show>
        <span class="mx-2">VS</span>
        <Show
          when={props.match[`team_${props.opponentTeamNo}`]}
          fallback={
            <span class="w-1/3 text-center font-bold">
              {props.match[`placeholder_seed_${props.opponentTeamNo}`]}
            </span>
          }
        >
          <span class="w-1/3 text-center font-bold dark:text-blue-400 text-blue-500">
            <A
              href={`/tournament/${props.tournamentSlug}/team/${
                props.match[`team_${props.opponentTeamNo}`]
                  .ultimate_central_slug
              }`}
            >
              {props.match[`team_${props.opponentTeamNo}`].name +
                ` (${props.match[`placeholder_seed_${props.opponentTeamNo}`]})`}
            </A>
          </span>
          <img
            class="w-6 h-6 p-1 rounded-full ring-2 ring-blue-500 dark:ring-blue-400 inline-block ml-1"
            src={
              props.teamsMap()[props.match[`team_${props.opponentTeamNo}`].id]
                ?.image_url
            }
            alt="Bordered avatar"
          />
        </Show>
      </div>
      <Show when={props.match.status === "COM"}>
        <p class="text-center font-bold">
          <Switch>
            {/* current > opponent */}
            <Match
              when={
                props.match[`score_team_${props.currentTeamNo}`] >
                props.match[`score_team_${props.opponentTeamNo}`]
              }
            >
              <span class="text-green-500 dark:text-green-400">
                {props.match[`score_team_${props.currentTeamNo}`]}
              </span>
              <span>{" - "}</span>
              <span class="text-red-500 dark:text-red-400">
                {props.match[`score_team_${props.opponentTeamNo}`]}
              </span>
            </Match>
            {/* current < opponent */}
            <Match
              when={
                props.match[`score_team_${props.currentTeamNo}`] <
                props.match[`score_team_${props.opponentTeamNo}`]
              }
            >
              <span class="text-red-500 dark:text-red-400">
                {props.match[`score_team_${props.currentTeamNo}`]}
              </span>
              <span>{" - "}</span>
              <span class="text-green-500 dark:text-green-400">
                {props.match[`score_team_${props.opponentTeamNo}`]}
              </span>
            </Match>
            {/* current == opponent */}
            <Match
              when={
                props.match[`score_team_${props.currentTeamNo}`] ===
                props.match[`score_team_${props.opponentTeamNo}`]
              }
            >
              <span class="text-blue-500 dark:text-blue-400">
                {props.match[`score_team_${props.currentTeamNo}`]}
              </span>
              <span>{" - "}</span>
              <span class="text-blue-500 dark:text-blue-400">
                {props.match[`score_team_${props.opponentTeamNo}`]}
              </span>
            </Match>
          </Switch>
        </p>
      </Show>
      <p class="text-center text-sm mt-2">
        {props.match.field +
          " | " +
          new Date(Date.parse(props.match.time)).toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "numeric",
            timeZone: "UTC"
          })}
      </p>
      <Show when={props.match.video_url}>
        <a
          class="flex justify-center"
          href={props.match.video_url}
          target="_blank"
        >
          <button
            type="button"
            class="text-white mt-2 bg-blue-600 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center inline-flex items-center dark:bg-blue-500 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          >
            <Icon class="w-4 mr-2" path={play} />
            Watch
          </button>
        </a>
      </Show>
      <Show when={props.match[`spirit_score_team_${props.currentTeamNo}`]}>
        <div class="flex justify-center mt-5">
          <button
            data-modal-target={`modal-${props.match.id}`}
            data-modal-toggle={`modal-${props.match.id}`}
            class="relative inline-flex items-center justify-center p-0.5 mb-2 mr-2 overflow-hidden text-xs font-medium text-gray-900 rounded-lg group bg-gradient-to-br from-cyan-500 to-blue-500 group-hover:from-cyan-500 group-hover:to-blue-500 hover:text-white dark:text-white focus:ring-4 focus:outline-none focus:ring-cyan-200 dark:focus:ring-cyan-800"
          >
            <span class="relative px-3 py-2.5 transition-all ease-in duration-75 bg-white dark:bg-gray-800 rounded-md group-hover:bg-opacity-0 inline-flex items-center">
              Spirit Scores, MVP & MSP
              <Icon path={arrowRight} class="w-4 ml-1.5" />
            </span>
          </button>
        </div>

        <div
          id={`modal-${props.match.id}`}
          tabindex="-1"
          aria-hidden="true"
          class="fixed top-0 left-0 right-0 z-50 hidden w-full p-4 overflow-x-hidden overflow-y-auto md:inset-0 h-[calc(100%-1rem)] max-h-full"
        >
          <div class="relative w-full max-w-2xl max-h-full">
            <div class="relative bg-white rounded-lg shadow dark:bg-gray-700">
              <div class="flex items-start justify-between p-4 border-b rounded-t dark:border-gray-600">
                <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
                  Spirit Scores, MVP & MSP
                </h3>
                <button
                  type="button"
                  class="text-gray-400 bg-transparent hover:bg-gray-200 hover:text-gray-900 rounded-lg text-sm w-8 h-8 ml-auto inline-flex justify-center items-center dark:hover:bg-gray-600 dark:hover:text-white"
                  data-modal-hide={`modal-${props.match.id}`}
                >
                  <svg
                    class="w-3 h-3"
                    aria-hidden="true"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 14 14"
                  >
                    <path
                      stroke="currentColor"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="m1 1 6 6m0 0 6 6M7 7l6-6M7 7l-6 6"
                    />
                  </svg>
                  <span class="sr-only">Close modal</span>
                </button>
              </div>
              <div class="p-2 space-y-2">
                <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                  Spirit Scores
                </h2>
                <div class="relative overflow-x-auto">
                  <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                    <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                      <tr>
                        <th scope="col" class="px-2 py-3">
                          Spirit Criteria
                        </th>
                        <th scope="col" class="px-2 py-3">
                          {props.match[`team_${props.currentTeamNo}`].name}
                        </th>
                        <th scope="col" class="px-2 py-3">
                          {props.match[`team_${props.opponentTeamNo}`].name}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr class="bg-white border-b dark:bg-gray-700 dark:border-gray-700">
                        <th
                          scope="row"
                          class="px-2 py-4 font-medium text-gray-900 dark:text-white"
                        >
                          Rules Knowledge & Use
                        </th>
                        <td class="px-2 py-4">
                          {
                            props.match[
                              `spirit_score_team_${props.currentTeamNo}`
                            ].rules
                          }
                        </td>
                        <td class="px-2 py-4">
                          {
                            props.match[
                              `spirit_score_team_${props.opponentTeamNo}`
                            ].rules
                          }
                        </td>
                      </tr>
                      <tr class="bg-white border-b dark:bg-gray-700 dark:border-gray-700">
                        <th
                          scope="row"
                          class="px-2 py-4 font-medium text-gray-900 dark:text-white"
                        >
                          Fouls & Body Contact
                        </th>
                        <td class="px-2 py-4">
                          {
                            props.match[
                              `spirit_score_team_${props.currentTeamNo}`
                            ].fouls
                          }
                        </td>
                        <td class="px-2 py-4">
                          {
                            props.match[
                              `spirit_score_team_${props.opponentTeamNo}`
                            ].fouls
                          }
                        </td>
                      </tr>
                      <tr class="bg-white border-b dark:bg-gray-700 dark:border-gray-700">
                        <th
                          scope="row"
                          class="px-2 py-4 font-medium text-gray-900 dark:text-white"
                        >
                          Fair-Mindedness
                        </th>
                        <td class="px-2 py-4">
                          {
                            props.match[
                              `spirit_score_team_${props.currentTeamNo}`
                            ].fair
                          }
                        </td>
                        <td class="px-2 py-4">
                          {
                            props.match[
                              `spirit_score_team_${props.opponentTeamNo}`
                            ].fair
                          }
                        </td>
                      </tr>
                      <tr class="bg-white border-b dark:bg-gray-700 dark:border-gray-700">
                        <th
                          scope="row"
                          class="px-2 py-4 font-medium text-gray-900 dark:text-white"
                        >
                          Positive Attitude & Self-Control
                        </th>
                        <td class="px-2 py-4">
                          {
                            props.match[
                              `spirit_score_team_${props.currentTeamNo}`
                            ].positive
                          }
                        </td>
                        <td class="px-2 py-4">
                          {
                            props.match[
                              `spirit_score_team_${props.opponentTeamNo}`
                            ].positive
                          }
                        </td>
                      </tr>
                      <tr class="bg-white border-b dark:bg-gray-700 dark:border-gray-700">
                        <th
                          scope="row"
                          class="px-2 py-4 font-medium text-gray-900 dark:text-white"
                        >
                          Communication
                        </th>
                        <td class="px-2 py-4">
                          {
                            props.match[
                              `spirit_score_team_${props.currentTeamNo}`
                            ].communication
                          }
                        </td>
                        <td class="px-2 py-4">
                          {
                            props.match[
                              `spirit_score_team_${props.opponentTeamNo}`
                            ].communication
                          }
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                  MVPs
                </h2>
                <Show
                  when={
                    props.match[`spirit_score_team_${props.currentTeamNo}`].mvp
                  }
                >
                  <div class="flex items-center space-x-4 mx-5">
                    <img
                      class="w-10 h-10 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 p-1"
                      src={
                        props.match[`spirit_score_team_${props.currentTeamNo}`]
                          .mvp?.image_url
                      }
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {props.match[`spirit_score_team_${props.currentTeamNo}`]
                          .mvp?.first_name +
                          " " +
                          props.match[
                            `spirit_score_team_${props.currentTeamNo}`
                          ].mvp?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${props.currentTeamNo}`].name}
                      </div>
                    </div>
                  </div>
                </Show>
                <Show
                  when={
                    props.match[`spirit_score_team_${props.opponentTeamNo}`].mvp
                  }
                >
                  <div class="flex items-center space-x-4 mx-5">
                    <img
                      class="w-10 h-10 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 p-1"
                      src={
                        props.match[`spirit_score_team_${props.opponentTeamNo}`]
                          .mvp?.image_url
                      }
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {props.match[
                          `spirit_score_team_${props.opponentTeamNo}`
                        ].mvp?.first_name +
                          " " +
                          props.match[
                            `spirit_score_team_${props.opponentTeamNo}`
                          ].mvp?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${props.opponentTeamNo}`].name}
                      </div>
                    </div>
                  </div>
                </Show>

                <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                  MSPs
                </h2>
                <Show
                  when={
                    props.match[`spirit_score_team_${props.currentTeamNo}`].msp
                  }
                >
                  <div class="flex items-center space-x-4 mx-5">
                    <img
                      class="w-10 h-10 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 p-1"
                      src={
                        props.match[`spirit_score_team_${props.currentTeamNo}`]
                          .msp?.image_url
                      }
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {props.match[`spirit_score_team_${props.currentTeamNo}`]
                          .msp?.first_name +
                          " " +
                          props.match[
                            `spirit_score_team_${props.currentTeamNo}`
                          ].msp?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${props.currentTeamNo}`].name}
                      </div>
                    </div>
                  </div>
                </Show>
                <Show
                  when={
                    props.match[`spirit_score_team_${props.opponentTeamNo}`].msp
                  }
                >
                  <div class="flex items-center space-x-4 mx-5">
                    <img
                      class="w-10 h-10 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 p-1"
                      src={
                        props.match[`spirit_score_team_${props.opponentTeamNo}`]
                          .msp?.image_url
                      }
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {props.match[
                          `spirit_score_team_${props.opponentTeamNo}`
                        ].msp?.first_name +
                          " " +
                          props.match[
                            `spirit_score_team_${props.opponentTeamNo}`
                          ].msp?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${props.opponentTeamNo}`].name}
                      </div>
                    </div>
                  </div>
                </Show>
              </div>
            </div>
          </div>
        </div>
      </Show>
    </div>
  );
};

export default TournamentMatch;
