import { useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import {
  fetchMatchesBySlug,
  fetchTeamBySlug,
  fetchTournamentBySlug,
  fetchTournamentTeamBySlug
} from "../queries";
import { createEffect, For, onMount, Show, createSignal } from "solid-js";
import Breadcrumbs from "./Breadcrumbs";
import { trophy } from "solid-heroicons/solid";
import { initFlowbite } from "flowbite";

import TournamentMatch from "./TournamentMatch";
import clsx from "clsx";
import { matchCardColorToBorderColorMap } from "../colors";

const TournamentTeam = () => {
  const params = useParams();
  const [matchesGroupedByDate, setMatchesGroupedByDate] = createSignal({});

  const tournamentQuery = createQuery(
    () => ["tournament", params.tournament_slug],
    () => fetchTournamentBySlug(params.tournament_slug)
  );
  const teamQuery = createQuery(
    () => ["team", params.team_slug],
    () => fetchTeamBySlug(params.team_slug)
  );
  const rosterQuery = createQuery(
    () => ["tournament-roster", params.tournament_slug, params.team_slug],
    () => fetchTournamentTeamBySlug(params.tournament_slug, params.team_slug)
  );
  const matchesQuery = createQuery(
    () => ["matches", params.tournament_slug],
    () => fetchMatchesBySlug(params.tournament_slug)
  );

  const currTeamNo = match =>
    params.team_slug === match.team_1.ultimate_central_slug ? 1 : 2;

  const oppTeamNo = match =>
    params.team_slug === match.team_1.ultimate_central_slug ? 2 : 1;

  const matchOutcomeColor = match => {
    if (match.status === "SCH") {
      return "blue";
    }
    if (match.status === "COM") {
      const currTeamScore = match[`score_team_${currTeamNo(match)}`];
      const oppTeamScore = match[`score_team_${oppTeamNo(match)}`];

      if (currTeamScore > oppTeamScore) {
        return "green";
      } else if (currTeamScore == oppTeamScore) {
        return "gray";
      } else {
        return "red";
      }
    }
  };

  createEffect(() => {
    if (matchesQuery.status === "success" && !matchesQuery.data?.message) {
      const teamMatches = matchesQuery.data?.filter(
        match =>
          match.team_1?.ultimate_central_slug === params.team_slug ||
          match.team_2?.ultimate_central_slug === params.team_slug
      );

      setMatchesGroupedByDate(
        Object.groupBy(teamMatches, ({ time }) =>
          new Date(Date.parse(time)).getUTCDate()
        )
      );
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

  return (
    <Show when={!teamQuery.data?.message}>
      <Breadcrumbs
        icon={trophy}
        pageList={[
          { url: "/tournaments", name: "All Tournaments" },
          {
            url: `/tournament/${params.tournament_slug}`,
            name: tournamentQuery.data?.event?.ultimate_central_slug
              ?.split("-")
              .splice(-2)
              .map(word => word[0].toUpperCase() + word.slice(1))
              .join(" ")
          }
        ]}
      />
      <div class="flex justify-center">
        <img
          class="w-24 h-24 p-1 rounded-full ring-2 ring-blue-600 dark:ring-blue-500 inline-block mr-3"
          src={teamQuery.data?.image_url}
          alt="Bordered avatar"
        />
      </div>

      <h1 class="text-center my-5">
        <span class="font-extrabold text-transparent text-2xl bg-clip-text bg-gradient-to-r from-blue-500 to-green-500 w-fit">
          {teamQuery.data?.name}
        </span>
      </h1>

      <h2 class="text-center font-bold text-xl">Roster</h2>

      <For each={rosterQuery.data}>
        {player => (
          <div class="flex my-5 px-6">
            <span>
              <img
                class="w-10 h-10 p-1 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 inline-block mr-3"
                src={player.image_url}
                alt="Bordered avatar"
              />
              {player.first_name + " " + player.last_name}
              <Show
                when={player?.player?.gender}
              >{` (${player?.player?.gender})`}</Show>
            </span>
          </div>
        )}
      </For>

      <h2 class="font-bold text-center text-xl my-5 mt-10 mb-10 underline underline-offset-8">
        Matches
      </h2>

      <For each={Object.entries(matchesGroupedByDate())}>
        {/* eslint-disable-next-line no-unused-vars */}
        {([tournamentDate, matches], idx) => (
          <div class="mb-10">
            <div class="mb-5 ml-1">
              <h3 class="font-bold text-lg text-center">Day - {idx() + 1}</h3>
            </div>
            <For each={matches}>
              {match => (
                <Show
                  when={
                    match.team_1?.ultimate_central_slug === params.team_slug ||
                    match.team_2?.ultimate_central_slug === params.team_slug
                  }
                >
                  <div
                    class={clsx(
                      "block py-2 px-1 bg-white border rounded-lg shadow dark:bg-gray-800 w-full mb-5",
                      matchCardColorToBorderColorMap[matchOutcomeColor(match)]
                    )}
                  >
                    <TournamentMatch
                      match={match}
                      currentTeamNo={currTeamNo(match)}
                      opponentTeamNo={oppTeamNo(match)}
                      tournamentSlug={params.tournament_slug}
                      imgRingColor={"gray"}
                      matchCardColorOverride={matchOutcomeColor(match)}
                      buttonColor={matchOutcomeColor(match)}
                    />
                  </div>
                </Show>
              )}
            </For>
          </div>
        )}
      </For>
    </Show>
  );
};

export default TournamentTeam;
