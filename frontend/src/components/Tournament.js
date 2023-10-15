import { createQuery } from "@tanstack/solid-query";
import { fetchTeams, fetchTournamentBySlug } from "../queries";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";
import { A, useParams } from "@solidjs/router";
import { trophy } from "solid-heroicons/solid";
import Breadcrumbs from "./Breadcrumbs";

const Tournament = () => {
  const params = useParams();
  const [teamsMap, setTeamsMap] = createSignal({});

  const tournamentQuery = createQuery(
    () => ["tournament", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );
  const teamsQuery = createQuery(() => ["teams"], fetchTeams);

  createEffect(() => {
    if (teamsQuery.status === "success") {
      let newTeamsMap = {};
      teamsQuery.data.map(team => {
        newTeamsMap[team.id] = team;
      });
      setTeamsMap(newTeamsMap);
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
        pageList={[{ url: "/tournaments", name: "All Tournaments" }]}
      />

      <h1 class="text-center mb-5">
        <span class="font-extrabold text-transparent text-2xl bg-clip-text bg-gradient-to-r from-blue-500 to-green-500 w-fit">
          {tournamentQuery.data?.event?.title}
        </span>
      </h1>

      <Show
        when={tournamentQuery.data?.logo_dark}
        fallback={
          <div>
            <p class="text-sm text-center mt-2">
              {tournamentQuery.data?.event?.location}
            </p>
            <p class="text-sm text-center mt-2">
              {new Date(
                Date.parse(tournamentQuery.data?.event.start_date)
              ).toLocaleDateString("en-US", {
                year: "numeric",
                month: "short",
                day: "numeric",
                timeZone: "UTC"
              })}
              <Show
                when={
                  tournamentQuery.data?.event.start_date !==
                  tournamentQuery.data?.event.end_date
                }
              >
                {" "}
                to{" "}
                {new Date(
                  Date.parse(tournamentQuery.data?.event.end_date)
                ).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                  timeZone: "UTC"
                })}
              </Show>
            </p>
          </div>
        }
      >
        <div class="flex justify-center">
          <img
            src={tournamentQuery.data?.logo_dark}
            alt="Tournament logo"
            class="w-3/4 hidden dark:block"
          />
          <img
            src={tournamentQuery.data?.logo_light}
            alt="Tournament logo"
            class="w-3/4 block dark:hidden"
          />
        </div>
      </Show>

      <div class="flex justify-center mt-5">
        <Switch>
          <Match when={tournamentQuery.data?.status === "COM"}>
            <span class="h-fit bg-blue-100 text-blue-800 text-sm font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-blue-900 dark:text-blue-300">
              Completed
            </span>
          </Match>
          <Match when={tournamentQuery.data?.status === "LIV"}>
            <span class="h-fit bg-green-100 text-green-800 text-sm font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-green-900 dark:text-green-300">
              Live
            </span>
          </Match>
        </Switch>
      </div>
      <A
        href={`/tournament/${params.slug}/schedule`}
        class="block p-4 bg-white border border-blue-600 rounded-lg shadow dark:bg-gray-800 dark:border-blue-400 w-full mt-5"
      >
        <h5 class="mb-2 text-xl font-bold tracking-tight text-blue-600 dark:text-blue-400 capitalize text-center">
          Schedule
        </h5>
        <p class="text-sm text-center capitalize">
          View the detailed schedule of matches
        </p>
      </A>
      <A
        href={`/tournament/${params.slug}/standings`}
        class="block p-4 bg-white border border-blue-600 rounded-lg shadow dark:bg-gray-800 dark:border-blue-400 w-full mt-5"
      >
        <h5 class="mb-2 text-xl font-bold tracking-tight text-blue-600 dark:text-blue-400 capitalize text-center">
          Standings
        </h5>
        <p class="text-sm text-center capitalize">
          View the pools, brackets and the detailed standings
        </p>
      </A>

      <Switch>
        <Match when={tournamentQuery.data?.status === "COM"}>
          <h2 class="text-center mt-5 text-xl font-bold">Final Standings</h2>
        </Match>
        <Match when={tournamentQuery.data?.status === "LIV"}>
          <h2 class="text-center mt-5 text-xl font-bold">Current Standings</h2>
        </Match>
      </Switch>

      <div class="relative overflow-x-auto shadow-md rounded-lg mt-5">
        <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
          <tbody>
            <For
              each={Object.entries(tournamentQuery.data?.current_seeding || {})}
            >
              {([rank, team_id]) => (
                <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                  <th
                    scope="row"
                    class="pr-6 pl-10 py-4 whitespace-nowrap font-normal"
                  >
                    {rank}
                  </th>
                  <td class="px-6 py-4">
                    <A
                      href={`/tournament/${params.slug}/team/${
                        teamsMap()[team_id]?.ultimate_central_slug
                      }`}
                    >
                      <img
                        class="w-8 h-8 p-1 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 inline-block mr-3"
                        src={teamsMap()[team_id]?.image_url}
                        alt="Bordered avatar"
                      />
                      {teamsMap()[team_id]?.name}
                    </A>
                  </td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>

      <Switch>
        <Match when={tournamentQuery.data?.status === "COM"}>
          <h2 class="text-center mt-5 text-xl font-bold">
            Final Spirit Rankings
          </h2>
        </Match>
        <Match when={tournamentQuery.data?.status === "LIV"}>
          <h2 class="text-center mt-5 text-xl font-bold">
            Current Spirit Rankings
          </h2>
        </Match>
      </Switch>

      <div class="relative overflow-x-auto shadow-md rounded-lg mt-5">
        <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
          <tbody>
            <For each={tournamentQuery.data?.spirit_ranking}>
              {spirit => (
                <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                  <th
                    scope="row"
                    class="pr-6 pl-10 py-4 whitespace-nowrap font-normal"
                  >
                    {spirit.rank}
                  </th>
                  <td class="px-6 py-4">
                    <A
                      href={`/tournament/${params.slug}/team/${
                        teamsMap()[spirit.team_id]?.ultimate_central_slug
                      }`}
                    >
                      <img
                        class="w-8 h-8 p-1 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 inline-block mr-3"
                        src={teamsMap()[spirit.team_id]?.image_url}
                        alt="Bordered avatar"
                      />
                      {teamsMap()[spirit.team_id]?.name}
                    </A>
                  </td>
                  <td class="px-6 py-4">{spirit.points}</td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>
    </Show>
  );
};

export default Tournament;
