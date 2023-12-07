import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { initFlowbite } from "flowbite";
import { trophy } from "solid-heroicons/solid";
import { createEffect, createSignal, For, onMount, Show } from "solid-js";
import { createStore, reconcile } from "solid-js/store";

import { matchCardColorToBorderColorMap } from "../colors";
import { fetchMatchesBySlug, fetchTournamentBySlug } from "../queries";
import { getMatchCardColor, getTournamentBreadcrumbName } from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import MatchCard from "./tournament/MatchCard";
import TournamentMatch from "./TournamentMatch";

const TournamentSchedule = () => {
  const params = useParams();
  const [tournamentDays, setTournamentDays] = createSignal([]);
  const [flash, setFlash] = createSignal(-1);
  const [matchDayTimeFieldMap, setMatchDayTimeFieldMap] = createStore({});
  const [fieldMap, setFieldMap] = createStore({});
  // const [_, setDateTimeMatchMap] = createSignal({});

  const tournamentQuery = createQuery(
    () => ["tournament", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
  const matchesQuery = createQuery(
    () => ["matches", params.slug],
    () => fetchMatchesBySlug(params.slug)
  );

  function sameDay(d1, d2) {
    return (
      d1.getUTCFullYear() === d2.getUTCFullYear() &&
      d1.getUTCMonth() === d2.getUTCMonth() &&
      d1.getUTCDate() === d2.getUTCDate()
    );
  }

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

      setTimeout(() => initFlowbite(), 500);
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

      setTimeout(() => initFlowbite(), 500);
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
            name: getTournamentBreadcrumbName(
              tournamentQuery.data?.event?.ultimate_central_slug || ""
            )
          }
        ]}
      />
      <h1 class="mb-5 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-2xl font-extrabold text-transparent">
          Schedule
        </span>
      </h1>

      <div class="mb-4 border-b border-gray-200 dark:border-gray-700">
        <ul
          class="-mb-px flex flex-wrap justify-center text-center text-sm font-medium"
          id="myTab"
          data-tabs-toggle="#myTabContent"
          role="tablist"
        >
          <For each={tournamentDays()}>
            {(day, i) => (
              <li class="mr-2" role="presentation">
                <button
                  class="inline-block rounded-t-lg border-b-2 p-4"
                  id={"day-tab-" + (i() + 1)}
                  data-tabs-target={"#day-" + (i() + 1)}
                  type="button"
                  role="tab"
                  aria-controls={"day-" + (i() + 1)}
                  aria-selected={
                    sameDay(day, new Date(Date.now())) ? "true" : "false"
                  }
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
              class="hidden rounded-lg p-4"
              id={"day-" + (i() + 1)}
              role="tabpanel"
              aria-labelledby={"day-tab-" + (i() + 1)}
            >
              <For each={Object.keys(matchDayTimeFieldMap).sort()}>
                {day2 => (
                  <Show
                    when={sameDay(day, new Date(Date.parse(day2 + " GMT")))}
                  >
                    <div class="relative mb-8 overflow-x-auto">
                      <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                        <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
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
                              <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                                <th
                                  scope="row"
                                  class="whitespace-nowrap px-2 py-4 text-center text-xs font-medium text-gray-900 dark:text-white"
                                >
                                  {new Date(time).toLocaleTimeString("en-US", {
                                    hour: "numeric",
                                    minute: "numeric",
                                    timeZone: "UTC"
                                  })}
                                </th>
                                <For each={Object.keys(fieldMap[day2]).sort()}>
                                  {field => (
                                    <td class="whitespace-nowrap px-2 py-4 text-xs">
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
                                          setFlash={setFlash}
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
                      <p class="mt-2 text-sm">
                        * CP - Cross Pool | B - Brackets
                      </p>
                    </div>
                  </Show>
                )}
              </For>
              <Show
                when={
                  matchesQuery.data?.filter(match =>
                    sameDay(day, new Date(Date.parse(match.time)))
                  ).length === 0
                }
              >
                <div
                  class="mb-4 flex items-center rounded-lg border border-blue-300 bg-blue-50 p-4 text-sm text-blue-800 dark:border-blue-800 dark:bg-gray-800 dark:text-blue-400"
                  role="alert"
                >
                  <svg
                    class="me-3 inline h-4 w-4 flex-shrink-0"
                    aria-hidden="true"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5ZM9.5 4a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM12 15H8a1 1 0 0 1 0-2h1v-3H8a1 1 0 0 1 0-2h2a1 1 0 0 1 1 1v4h1a1 1 0 0 1 0 2Z" />
                  </svg>
                  <span class="sr-only">Info</span>
                  <div>
                    <span class="font-medium capitalize">
                      No Matches Present on this day!
                    </span>
                  </div>
                </div>
              </Show>
              <For each={matchesQuery.data}>
                {match => (
                  <Show when={sameDay(day, new Date(Date.parse(match.time)))}>
                    <div
                      id={match.id}
                      class={clsx(
                        flash() == match.id
                          ? "bg-blue-100 text-black dark:bg-slate-700 dark:text-white"
                          : "bg-white dark:bg-gray-800",
                        "mb-5 block w-full rounded-lg border px-1 py-2 shadow transition",
                        matchCardColorToBorderColorMap[getMatchCardColor(match)]
                      )}
                    >
                      <TournamentMatch
                        match={match}
                        tournamentSlug={params.slug}
                        bothTeamsClickable
                      />
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
