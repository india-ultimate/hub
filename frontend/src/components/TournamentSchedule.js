import { A, useParams } from "@solidjs/router";
import {
  createEffect,
  createSignal,
  For,
  Match,
  onMount,
  Show,
  Switch
} from "solid-js";
import { createQuery } from "@tanstack/solid-query";
import {
  fetchMatchesBySlug,
  fetchTeams,
  fetchTournamentBySlug
} from "../queries";
import Breadcrumbs from "./Breadcrumbs";
import { arrowRight, trophy } from "solid-heroicons/solid";
import { initFlowbite } from "flowbite";
import MatchCard from "./tournament/MatchCard";
import { createStore, reconcile } from "solid-js/store";
import { Icon } from "solid-heroicons";
import { play } from "solid-heroicons/solid";

const TournamentSchedule = () => {
  const params = useParams();
  const [teamsMap, setTeamsMap] = createSignal({});
  const [tournamentDays, setTournamentDays] = createSignal([]);
  const [matchDayTimeFieldMap, setMatchDayTimeFieldMap] = createStore({});
  const [fieldMap, setFieldMap] = createStore({});
  // const [_, setDateTimeMatchMap] = createSignal({});

  const tournamentQuery = createQuery(
    () => ["tournament", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
  const teamsQuery = createQuery(() => ["teams"], fetchTeams);
  const matchesQuery = createQuery(
    () => ["matches", params.slug],
    () => fetchMatchesBySlug(params.slug)
  );

  function sameDay(d1, d2) {
    return (
      d1.getFullYear() === d2.getUTCFullYear() &&
      d1.getMonth() === d2.getUTCMonth() &&
      d1.getDate() === d2.getUTCDate()
    );
  }

  createEffect(() => {
    if (teamsQuery.status === "success") {
      let newTeamsMap = {};
      teamsQuery.data.map(team => {
        newTeamsMap[team.id] = team;
      });
      setTeamsMap(newTeamsMap);
    }
  });

  createEffect(() => {
    if (
      tournamentQuery.status === "success" &&
      !tournamentQuery.data?.message
    ) {
      let days = [];
      let start = new Date(Date.parse(tournamentQuery.data?.event?.start_date));
      let end = new Date(Date.parse(tournamentQuery.data?.event?.end_date));

      for (var d = start; d <= end; d.setDate(d.getDate() + 1)) {
        days.push(new Date(d));
      }

      setTournamentDays(days);
    }
  });

  createEffect(() => {
    if (matchesQuery.status === "success" && !matchesQuery.data?.message) {
      setMatchDayTimeFieldMap(reconcile({}));
      setFieldMap(reconcile({}));
      matchesQuery.data?.map(match => {
        if (match.time && match.field) {
          const day = new Date(Date.parse(match.time)).toLocaleDateString(
            "en-US",
            {
              year: "numeric",
              month: "short",
              day: "numeric",
              timeZone: "UTC"
            }
          );
          const time = new Date(Date.parse(match.time));
          setMatchDayTimeFieldMap(day, {});
          setMatchDayTimeFieldMap(day, time, {});
          setMatchDayTimeFieldMap(day, time, match.field, match);

          setFieldMap(day, {});
          setFieldMap(day, match.field, true);
        }
      });
    }
  });

  onMount(() => {
    setTimeout(() => initFlowbite(), 100);
    setTimeout(() => initFlowbite(), 500);
    setTimeout(() => initFlowbite(), 1000);
    setTimeout(() => initFlowbite(), 3000);
    setTimeout(() => initFlowbite(), 5000);
    setTimeout(() => initFlowbite(), 8000);
  });

  // createEffect(() => {
  //   if (matchesQuery.status === "success" && !matchesQuery.data?.message) {
  //     let dateMatchMap = {};
  //
  //     for (const match of matchesQuery.data) {
  //       if (dateMatchMap[new Date(match.time)]) {
  //         dateMatchMap[new Date(match.time)].push(match);
  //       } else {
  //         dateMatchMap[new Date(match.time)] = [match];
  //       }
  //     }
  //
  //     setDateTimeMatchMap(dateMatchMap);
  //   }
  // });

  return (
    <Show
      when={!tournamentQuery.data?.message}
      fallback={
        <div>
          Tournament could not be fetched. Error -{" "}
          {tournamentQuery.data.message}
          <A href={"/tournaments"} class="text-blue-600 dark:text-blue-500">
            <br />
            Back to Tournaments Page
          </A>
        </div>
      }
    >
      <Breadcrumbs
        icon={trophy}
        pageList={[
          { url: "/tournaments", name: "All Tournaments" },
          {
            url: `/tournament/${params.slug}`,
            name: tournamentQuery.data?.event?.ultimate_central_slug
              ?.split("-")
              .splice(-2)
              .map(word => word[0].toUpperCase() + word.slice(1))
              .join(" ")
          }
        ]}
      />
      <h1 class="text-center mb-5">
        <span class="font-extrabold text-transparent text-2xl bg-clip-text bg-gradient-to-r from-blue-500 to-green-500 w-fit">
          Schedule
        </span>
      </h1>

      <div class="mb-4 border-b border-gray-200 dark:border-gray-700">
        <ul
          class="flex flex-wrap -mb-px text-sm font-medium text-center justify-center"
          id="myTab"
          data-tabs-toggle="#myTabContent"
          role="tablist"
        >
          <For each={tournamentDays()}>
            {(day, i) => (
              <li class="mr-2" role="presentation">
                <button
                  class="inline-block p-4 border-b-2 rounded-t-lg"
                  id={"day-tab-" + (i() + 1)}
                  data-tabs-target={"#day-" + (i() + 1)}
                  type="button"
                  role="tab"
                  aria-controls={"day-" + (i() + 1)}
                  aria-selected="false"
                >
                  {"Day " + (i() + 1)}
                </button>
              </li>
            )}
          </For>
        </ul>
      </div>
      <div id="myTabContent">
        <For each={tournamentDays()}>
          {(day, i) => (
            <div
              class="hidden p-4 rounded-lg"
              id={"day-" + (i() + 1)}
              role="tabpanel"
              aria-labelledby={"day-tab-" + (i() + 1)}
            >
              <For each={Object.keys(matchDayTimeFieldMap).sort()}>
                {day2 => (
                  <Show
                    when={sameDay(day, new Date(Date.parse(day2 + " GMT")))}
                  >
                    <div class="relative overflow-x-auto mb-8">
                      <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400 table-fixed">
                        <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                          <tr>
                            <th scope="col" class="px-2 py-3 text-center">
                              Time
                            </th>
                            <For each={Object.keys(fieldMap[day2]).sort()}>
                              {field => (
                                <th scope="col" class="px-1 py-3 text-center">
                                  {field}
                                </th>
                              )}
                            </For>
                          </tr>
                        </thead>
                        <tbody>
                          <For
                            each={Object.keys(matchDayTimeFieldMap[day2]).sort(
                              (a, b) => new Date(a) - new Date(b)
                            )}
                          >
                            {time => (
                              <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                                <th
                                  scope="row"
                                  class="px-2 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white text-center text-xs"
                                >
                                  {new Date(time).toLocaleTimeString("en-US", {
                                    hour: "numeric",
                                    minute: "numeric",
                                    timeZone: "UTC"
                                  })}
                                </th>
                                <For each={Object.keys(fieldMap[day2]).sort()}>
                                  {field => (
                                    <td class="px-1 py-4 text-xs">
                                      <Show
                                        when={
                                          matchDayTimeFieldMap[day2][time][
                                            field
                                          ]
                                        }
                                      >
                                        <MatchCard
                                          match={
                                            matchDayTimeFieldMap[day2][time][
                                              field
                                            ]
                                          }
                                          showSeed={true}
                                        />
                                      </Show>
                                    </td>
                                  )}
                                </For>
                              </tr>
                            )}
                          </For>
                        </tbody>
                      </table>
                      <p class="text-sm mt-2">
                        * CP - Cross Pool | B - Brackets
                      </p>
                    </div>
                  </Show>
                )}
              </For>
              <For each={matchesQuery.data}>
                {match => (
                  <Show when={sameDay(day, new Date(Date.parse(match.time)))}>
                    <div class="block py-2 px-1 bg-white border border-blue-600 rounded-lg shadow dark:bg-gray-800 dark:border-blue-400 w-full mb-5">
                      <Switch>
                        <Match when={match.pool}>
                          <p class="text-center text-sm mb-2">
                            Pool - {match.pool.name}
                          </p>
                        </Match>
                        <Match when={match.cross_pool}>
                          <p class="text-center text-sm mb-2">Cross Pool</p>
                        </Match>
                        <Match when={match.bracket}>
                          <p class="text-center text-sm mb-2">
                            Bracket - {match.bracket.name}
                          </p>
                        </Match>
                        <Match when={match.position_pool}>
                          <p class="text-center text-sm mb-2">
                            Position Pool - {match.position_pool.name}
                          </p>
                        </Match>
                      </Switch>
                      <div class="flex justify-center text-sm">
                        <Show
                          when={match.team_1}
                          fallback={
                            <span class="w-1/3 text-center font-bold">
                              {match.placeholder_seed_1}
                            </span>
                          }
                        >
                          <img
                            class="w-6 h-6 p-1 rounded-full ring-2 ring-blue-500 dark:ring-blue-400 inline-block mr-1"
                            src={teamsMap()[match.team_1.id]?.image_url}
                            alt="Bordered avatar"
                          />
                          <A
                            href={`/tournament/${params.slug}/team/${match.team_1.ultimate_central_slug}`}
                            class="w-1/3 text-center font-bold dark:text-blue-400 text-blue-500"
                          >
                            {match.team_1.name +
                              ` (${match.placeholder_seed_1})`}
                          </A>
                        </Show>
                        <span class="mx-2">VS</span>
                        <Show
                          when={match.team_2}
                          fallback={
                            <span class="w-1/3 text-center font-bold">
                              {match.placeholder_seed_2}
                            </span>
                          }
                        >
                          <A
                            href={`/tournament/${params.slug}/team/${match.team_2.ultimate_central_slug}`}
                            class="w-1/3 text-center font-bold dark:text-blue-400 text-blue-500"
                          >
                            {match.team_2.name +
                              ` (${match.placeholder_seed_2})`}
                          </A>
                          <img
                            class="w-6 h-6 p-1 rounded-full ring-2 ring-blue-500 dark:ring-blue-400 inline-block ml-1"
                            src={teamsMap()[match.team_2.id]?.image_url}
                            alt="Bordered avatar"
                          />
                        </Show>
                      </div>
                      <Show when={match.status === "COM"}>
                        <p class="text-center font-bold">
                          <Switch>
                            <Match
                              when={match.score_team_1 > match.score_team_2}
                            >
                              <span class="text-green-500 dark:text-green-400">
                                {match.score_team_1}
                              </span>
                              <span>{" - "}</span>
                              <span class="text-red-500 dark:text-red-400">
                                {match.score_team_2}
                              </span>
                            </Match>
                            <Match
                              when={match.score_team_1 < match.score_team_2}
                            >
                              <span class="text-red-500 dark:text-red-400">
                                {match.score_team_1}
                              </span>
                              <span>{" - "}</span>
                              <span class="text-green-500 dark:text-green-400">
                                {match.score_team_2}
                              </span>
                            </Match>
                            <Match
                              when={match.score_team_1 === match.score_team_2}
                            >
                              <span class="text-blue-500 dark:text-blue-400">
                                {match.score_team_1}
                              </span>
                              <span>{" - "}</span>
                              <span class="text-blue-500 dark:text-blue-400">
                                {match.score_team_2}
                              </span>
                            </Match>
                          </Switch>
                        </p>
                      </Show>
                      <p class="text-center text-sm mt-2">
                        {match.field +
                          " | " +
                          new Date(Date.parse(match.time)).toLocaleTimeString(
                            "en-US",
                            {
                              hour: "numeric",
                              minute: "numeric",
                              timeZone: "UTC"
                            }
                          )}
                      </p>
                      <Show when={match.video_url}>
                        <a
                          class="flex justify-center"
                          href={match.video_url}
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
                      <Show when={match.spirit_score_team_1}>
                        <div class="flex justify-center mt-5">
                          <button
                            data-modal-target={`modal-${match.id}`}
                            data-modal-toggle={`modal-${match.id}`}
                            class="relative inline-flex items-center justify-center p-0.5 mb-2 mr-2 overflow-hidden text-xs font-medium text-gray-900 rounded-lg group bg-gradient-to-br from-cyan-500 to-blue-500 group-hover:from-cyan-500 group-hover:to-blue-500 hover:text-white dark:text-white focus:ring-4 focus:outline-none focus:ring-cyan-200 dark:focus:ring-cyan-800"
                          >
                            <span class="relative px-3 py-2.5 transition-all ease-in duration-75 bg-white dark:bg-gray-800 rounded-md group-hover:bg-opacity-0 inline-flex items-center">
                              Spirit Scores, MVP & MSP
                              <Icon path={arrowRight} class="w-4 ml-1.5" />
                            </span>
                          </button>
                        </div>

                        <div
                          id={`modal-${match.id}`}
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
                                  data-modal-hide={`modal-${match.id}`}
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
                                          {match.team_1.name}
                                        </th>
                                        <th scope="col" class="px-2 py-3">
                                          {match.team_2.name}
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
                                          {match.spirit_score_team_1.rules}
                                        </td>
                                        <td class="px-2 py-4">
                                          {match.spirit_score_team_2.rules}
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
                                          {match.spirit_score_team_1.fouls}
                                        </td>
                                        <td class="px-2 py-4">
                                          {match.spirit_score_team_2.fouls}
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
                                          {match.spirit_score_team_1.fair}
                                        </td>
                                        <td class="px-2 py-4">
                                          {match.spirit_score_team_2.fair}
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
                                          {match.spirit_score_team_1.positive}
                                        </td>
                                        <td class="px-2 py-4">
                                          {match.spirit_score_team_2.positive}
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
                                            match.spirit_score_team_1
                                              .communication
                                          }
                                        </td>
                                        <td class="px-2 py-4">
                                          {
                                            match.spirit_score_team_2
                                              .communication
                                          }
                                        </td>
                                      </tr>
                                    </tbody>
                                  </table>
                                </div>
                                <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                                  MVPs
                                </h2>
                                <Show when={match.spirit_score_team_1.mvp}>
                                  <div class="flex items-center space-x-4 mx-5">
                                    <img
                                      class="w-10 h-10 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 p-1"
                                      src={
                                        match.spirit_score_team_1.mvp?.image_url
                                      }
                                      alt="Image"
                                    />
                                    <div class="font-medium dark:text-white">
                                      <div>
                                        {match.spirit_score_team_1.mvp
                                          ?.first_name +
                                          " " +
                                          match.spirit_score_team_1.mvp
                                            ?.last_name}
                                      </div>
                                      <div class="text-sm text-gray-500 dark:text-gray-400">
                                        {match.team_1.name}
                                      </div>
                                    </div>
                                  </div>
                                </Show>
                                <Show when={match.spirit_score_team_2.mvp}>
                                  <div class="flex items-center space-x-4 mx-5">
                                    <img
                                      class="w-10 h-10 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 p-1"
                                      src={
                                        match.spirit_score_team_2.mvp?.image_url
                                      }
                                      alt="Image"
                                    />
                                    <div class="font-medium dark:text-white">
                                      <div>
                                        {match.spirit_score_team_2.mvp
                                          ?.first_name +
                                          " " +
                                          match.spirit_score_team_2.mvp
                                            ?.last_name}
                                      </div>
                                      <div class="text-sm text-gray-500 dark:text-gray-400">
                                        {match.team_2.name}
                                      </div>
                                    </div>
                                  </div>
                                </Show>

                                <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                                  MSPs
                                </h2>
                                <Show when={match.spirit_score_team_1.msp}>
                                  <div class="flex items-center space-x-4 mx-5">
                                    <img
                                      class="w-10 h-10 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 p-1"
                                      src={
                                        match.spirit_score_team_1.msp?.image_url
                                      }
                                      alt="Image"
                                    />
                                    <div class="font-medium dark:text-white">
                                      <div>
                                        {match.spirit_score_team_1.msp
                                          ?.first_name +
                                          " " +
                                          match.spirit_score_team_1.msp
                                            ?.last_name}
                                      </div>
                                      <div class="text-sm text-gray-500 dark:text-gray-400">
                                        {match.team_1.name}
                                      </div>
                                    </div>
                                  </div>
                                </Show>
                                <Show when={match.spirit_score_team_2.msp}>
                                  <div class="flex items-center space-x-4 mx-5">
                                    <img
                                      class="w-10 h-10 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 p-1"
                                      src={
                                        match.spirit_score_team_2.msp?.image_url
                                      }
                                      alt="Image"
                                    />
                                    <div class="font-medium dark:text-white">
                                      <div>
                                        {match.spirit_score_team_2.msp
                                          ?.first_name +
                                          " " +
                                          match.spirit_score_team_2.msp
                                            ?.last_name}
                                      </div>
                                      <div class="text-sm text-gray-500 dark:text-gray-400">
                                        {match.team_2.name}
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
                  </Show>
                )}
              </For>
            </div>
          )}
        </For>
      </div>
    </Show>
  );
};

export default TournamentSchedule;
