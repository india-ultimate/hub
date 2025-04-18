import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { initFlowbite } from "flowbite";
import { trophy } from "solid-heroicons/solid";
import {
  createEffect,
  createSignal,
  For,
  Match,
  onMount,
  Show,
  Suspense,
  Switch
} from "solid-js";
import { createStore, reconcile } from "solid-js/store";

import { matchCardColorToBorderColorMap } from "../colors";
import {
  fetchFieldsByTournamentSlug,
  fetchMatchesBySlug,
  fetchTournamentBySlug
} from "../queries";
import DayScheduleSkeleton from "../skeletons/Schedule";
import { TournamentMatches as TournamentMatchesSkeleton } from "../skeletons/TournamentMatch";
import { getMatchCardColor, getTournamentBreadcrumbName } from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import MatchCard from "./match/MatchCard";
import ScheduleTable from "./tournament/ScheduleTable";

const TournamentSchedule = () => {
  const params = useParams();
  const [tournamentDays, setTournamentDays] = createSignal([]);
  const [flash, setFlash] = createSignal(-1);
  const [matchDayTimeFieldMap, setMatchDayTimeFieldMap] = createStore({});
  const [dayFieldMap, setDayFieldMap] = createStore({});
  // const [_, setDateTimeMatchMap] = createSignal({});
  const [doneBuildingScheduleMap, setDoneBuildingScheduleMap] =
    createSignal(false);

  const tournamentQuery = createQuery(
    () => ["tournaments", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
  const matchesQuery = createQuery(
    () => ["matches", params.slug],
    () => fetchMatchesBySlug(params.slug)
  );
  const fieldsQuery = createQuery(
    () => ["fields", params.slug],
    () => fetchFieldsByTournamentSlug(params.slug)
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

  const mapFieldIdToField = fields => {
    let newFieldsMap = {};
    fields?.map(field => {
      newFieldsMap[field.id] = field;
    });
    return newFieldsMap;
  };

  createEffect(() => {
    if (matchesQuery.status === "success" && !matchesQuery.data?.message) {
      setMatchDayTimeFieldMap(reconcile({}));
      setDayFieldMap(reconcile({}));
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
          const startTime = new Date(Date.parse(match.time));
          const endTime = new Date(
            startTime.getTime() + match.duration_mins * 60000
          );
          setMatchDayTimeFieldMap(day, {});
          setMatchDayTimeFieldMap(day, startTime, {});
          setMatchDayTimeFieldMap(day, startTime, endTime, {});
          setMatchDayTimeFieldMap(
            day,
            startTime,
            endTime,
            match.field?.id,
            match
          );

          setDayFieldMap(day, {});
          setDayFieldMap(day, match.field?.id, true);
        }
      });
      setDoneBuildingScheduleMap(true);
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
              tournamentQuery.data?.event?.slug || ""
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
              <Show
                when={doneBuildingScheduleMap()}
                fallback={<DayScheduleSkeleton />}
              />
              <For each={Object.keys(matchDayTimeFieldMap).sort()}>
                {day2 => (
                  <Show
                    when={sameDay(day, new Date(Date.parse(day2 + " GMT")))}
                  >
                    <div class="relative mb-8 overflow-x-auto">
                      <Switch>
                        <Match when={fieldsQuery.isError}>
                          <p>{fieldsQuery.error.message}</p>
                        </Match>
                        <Match when={fieldsQuery.isSuccess}>
                          <ScheduleTable
                            dayFieldMap={dayFieldMap}
                            day={day2}
                            matchDayTimeFieldMap={matchDayTimeFieldMap}
                            setFlash={setFlash}
                            fieldsMap={mapFieldIdToField(fieldsQuery.data)}
                          />
                        </Match>
                      </Switch>
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
              <Suspense fallback={<TournamentMatchesSkeleton />}>
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
                          matchCardColorToBorderColorMap[
                            getMatchCardColor(match)
                          ]
                        )}
                      >
                        <MatchCard
                          match={match}
                          tournamentSlug={params.slug}
                          tournamentType={tournamentQuery.data?.event?.type}
                          useUCRegistrations={
                            tournamentQuery.data?.use_uc_registrations
                          }
                          bothTeamsClickable
                        />
                      </div>
                    </Show>
                  )}
                </For>
              </Suspense>
            </div>
          )}
        </For>
      </div>
    </Show>
  );
};

export default TournamentSchedule;
