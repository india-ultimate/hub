import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import clsx from "clsx";
import { trophy } from "solid-heroicons/solid";
import {
  createEffect,
  createMemo,
  createSignal,
  For,
  Match,
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
import PillTabs from "./tabs/PillTabs";
import ScheduleTable from "./tournament/ScheduleTable";

const TournamentSchedule = () => {
  const params = useParams();
  const [tournamentDays, setTournamentDays] = createSignal([]);
  const [flash, setFlash] = createSignal(-1);
  const [matchDayTimeFieldMap, setMatchDayTimeFieldMap] = createStore({});
  const [dayFieldMap, setDayFieldMap] = createStore({});
  const [doneBuildingScheduleMap, setDoneBuildingScheduleMap] =
    createSignal(false);
  const [activeDay, setActiveDay] = createSignal(null);

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
    }
  });

  createEffect(() => {
    const days = tournamentDays();
    if (days.length > 0 && activeDay() === null) {
      const todayIndex = days.findIndex(day =>
        sameDay(day, new Date(Date.now()))
      );
      setActiveDay(todayIndex >= 0 ? todayIndex + 1 : 1);
    }
  });

  const dayTabs = createMemo(() => {
    return tournamentDays().map((_, i) => ({
      id: i + 1,
      label: `Day ${i + 1}`
    }));
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
    }
  });

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

      <PillTabs
        tabs={dayTabs()}
        activeTab={activeDay}
        onTabChange={setActiveDay}
      />

      <For each={tournamentDays()}>
        {(day, i) => (
          <Show when={activeDay() === i() + 1}>
            <div class="rounded-lg p-4">
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
                        * SW A, SW B - Swiss Group A, B | CP - Cross Pool | B -
                        Brackets
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
          </Show>
        )}
      </For>
    </Show>
  );
};

export default TournamentSchedule;
