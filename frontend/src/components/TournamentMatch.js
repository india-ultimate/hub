import { A } from "@solidjs/router";
import { createQuery, useQueryClient } from "@tanstack/solid-query";
import { clsx } from "clsx";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import { arrowRight, pencil, play } from "solid-heroicons/solid";
import { createEffect, createSignal, Match, Show, Switch } from "solid-js";

import {
  matchCardColorToButtonStyles,
  matchCardColorToRingColorMap
} from "../colors";
import { fetchTeams, fetchUserAccessByTournamentSlug } from "../queries";
import { getMatchCardColor } from "../utils";
import MatchCard from "./tournament/MatchCard";
import MatchScoreForm from "./tournament/MatchScoreForm";
import MatchSpiritScoreForm from "./tournament/MatchSpiritScoreForm";
import SpiritScoreTable from "./tournament/SpiritScoreTable";
/**
 * Returns a match block between 2 teams.
 * If a team should appear first, pass `currentTeamNo` = team id in match object (1 or 2).
 * If both team names should link to the team name, pass the `bothTeamsClickable` prop.
 *
 * @param {object} props
 * @param {object} props.match
 * @param {string} props.tournamentSlug
 * @param {number} [props.currentTeamNo]
 * @param {number} [props.opponentTeamNo]
 * @param {boolean} [props.bothTeamsClickable]
 */
const TournamentMatch = props => {
  const queryClient = useQueryClient();

  const [teamsMap, setTeamsMap] = createSignal({});
  const [currTeamNo, setCurrTeamNo] = createSignal(1);
  const [oppTeamNo, setOppTeamNo] = createSignal(2);

  const teamsQuery = createQuery(() => ["teams"], fetchTeams);
  const userAccessQuery = createQuery(
    () => ["user-access", props.tournamentSlug],
    () => fetchUserAccessByTournamentSlug(props.tournamentSlug)
  );

  createEffect(() => {
    setCurrTeamNo(props.currentTeamNo || 1);
    setOppTeamNo(props.opponentTeamNo || 2);
  });

  createEffect(() => {
    if (teamsQuery.status === "success") {
      let newTeamsMap = {};
      teamsQuery.data.map(team => {
        newTeamsMap[team.id] = team;
      });
      setTeamsMap(newTeamsMap);
    }
  });

  const checkIfSuggestedScoresClash = (
    suggested_score_team_1,
    suggested_score_team_2
  ) => {
    if (!suggested_score_team_1 || !suggested_score_team_2) {
      return false;
    }

    return (
      suggested_score_team_1["score_team_1"] !==
        suggested_score_team_2["score_team_1"] ||
      suggested_score_team_1["score_team_2"] !==
        suggested_score_team_2["score_team_2"]
    );
  };

  const isMatchTeamAdmin = () =>
    userAccessQuery?.data?.admin_team_ids?.length > 0 &&
    (userAccessQuery?.data?.admin_team_ids.indexOf(props.match["team_1"].id) >
      -1 ||
      userAccessQuery?.data?.admin_team_ids.indexOf(props.match["team_2"].id) >
        -1);

  const isStaff = () => {
    return userAccessQuery.data && userAccessQuery.data.is_staff;
  };

  const currTeam = () => props.match[`team_${currTeamNo()}`];
  const currTeamSeed = () => props.match[`placeholder_seed_${currTeamNo()}`];
  const currTeamScore = () => props.match[`score_team_${currTeamNo()}`];
  const currTeamSpiritScore = () =>
    props.match[`spirit_score_team_${currTeamNo()}`];

  const oppTeam = () => props.match[`team_${oppTeamNo()}`];
  const oppTeamSeed = () => props.match[`placeholder_seed_${oppTeamNo()}`];
  const oppTeamScore = () => props.match[`score_team_${oppTeamNo()}`];
  const oppTeamSpiritScore = () =>
    props.match[`spirit_score_team_${oppTeamNo()}`];

  return (
    <>
      <div class="mb-4">
        <MatchCard
          match={props.match}
          dontMinimiseMatchName
          matchCardColorOverride={props.matchCardColorOverride}
        />
      </div>
      <div class="flex justify-center text-sm">
        <Show
          when={currTeam()}
          fallback={
            <span class="w-1/3 text-center font-bold">{currTeamSeed()}</span>
          }
        >
          <img
            class={clsx(
              "mr-1 inline-block h-6 w-6 rounded-full p-1 ring-2",
              props.imgRingColor
                ? matchCardColorToRingColorMap[props.imgRingColor]
                : matchCardColorToRingColorMap[getMatchCardColor(props.match)]
            )}
            src={teamsMap()[currTeam().id]?.image_url}
            alt="Bordered avatar"
          />
          <span class="w-1/3 text-center font-bold text-gray-600 dark:text-gray-300">
            <Show
              when={props.bothTeamsClickable}
              fallback={`${currTeam().name} (${currTeamSeed()})`}
            >
              <A
                href={`/tournament/${props.tournamentSlug}/team/${
                  currTeam().ultimate_central_slug
                }`}
              >
                {`${currTeam().name} (${currTeamSeed()})`}
              </A>
            </Show>
          </span>
        </Show>

        <span class="mx-2">VS</span>
        <Show
          when={oppTeam()}
          fallback={
            <span class="w-1/3 text-center font-bold">{oppTeamSeed()}</span>
          }
        >
          <span class="w-1/3 text-center font-medium text-gray-600 dark:text-gray-300">
            <A
              href={`/tournament/${props.tournamentSlug}/team/${
                oppTeam().ultimate_central_slug
              }`}
            >
              {`${oppTeam().name} (${oppTeamSeed()})`}
            </A>
          </span>

          <img
            class={clsx(
              "mr-1 inline-block h-6 w-6 rounded-full p-1 ring-2",
              props.imgRingColor
                ? matchCardColorToRingColorMap[props.imgRingColor]
                : matchCardColorToRingColorMap[getMatchCardColor(props.match)]
            )}
            src={teamsMap()[oppTeam().id]?.image_url}
            alt="Bordered avatar"
          />
        </Show>
      </div>

      {/* Match score */}
      <Show when={props.match.status === "COM"}>
        <p class="text-center font-bold">
          <Switch>
            <Match when={currTeamScore() > oppTeamScore()}>
              <span class="text-green-500 dark:text-green-400">
                {currTeamScore()}
              </span>
              <span>{" - "}</span>
              <span class="text-red-500 dark:text-red-400">
                {oppTeamScore()}
              </span>
            </Match>
            <Match when={currTeamScore() < oppTeamScore()}>
              <span class="text-red-500 dark:text-red-400">
                {currTeamScore()}
              </span>
              <span>{" - "}</span>
              <span class="text-green-500 dark:text-green-400">
                {oppTeamScore()}
              </span>
            </Match>
            <Match when={currTeamScore() === oppTeamScore()}>
              <span class="text-blue-500 dark:text-blue-400">
                {currTeamScore()}
              </span>
              <span>{" - "}</span>
              <span class="text-blue-500 dark:text-blue-400">
                {oppTeamScore()}
              </span>
            </Match>
          </Switch>
        </p>
      </Show>
      {/* Field and duration */}
      <p class="mt-2 text-center text-sm">
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
            class="mt-2 inline-flex items-center rounded-lg bg-blue-600 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-500 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          >
            <Icon class="mr-2 w-4" path={play} />
            Watch
          </button>
        </a>
      </Show>
      {/* Score buttons */}
      <Show when={currTeamSpiritScore() && oppTeamSpiritScore()}>
        <div class="mt-5 flex justify-center">
          <button
            data-modal-target={`modal-${props.match.id}`}
            data-modal-toggle={`modal-${props.match.id}`}
            class={clsx(
              "group relative mb-2 mr-2 inline-flex items-center justify-center overflow-hidden rounded-lg p-0.5 text-xs font-medium",
              "text-gray-900 hover:text-white focus:outline-none focus:ring-4 dark:text-white",
              // "bg-gradient-to-br from-cyan-500 to-blue-500 group-hover:from-cyan-500 group-hover:to-blue-500",
              // "focus:ring-cyan-200 dark:focus:ring-cyan-800",
              props.buttonColor
                ? matchCardColorToButtonStyles[props.buttonColor]
                : matchCardColorToButtonStyles[getMatchCardColor(props.match)]
            )}
          >
            <span class="relative inline-flex items-center rounded-md bg-white px-3 py-2.5 transition-all duration-75 ease-in group-hover:bg-opacity-0 dark:bg-gray-800">
              Spirit Scores, MVP & MSP
              <Icon path={arrowRight} class="ml-1.5 w-4" />
            </span>
          </button>
        </div>

        <div
          id={`modal-${props.match.id}`}
          tabindex="-1"
          aria-hidden="true"
          class="fixed left-0 right-0 top-0 z-50 hidden h-[calc(100%-1rem)] max-h-full w-full overflow-y-auto overflow-x-hidden p-4 md:inset-0"
        >
          <div class="relative max-h-full w-full max-w-2xl">
            <div class="relative rounded-lg bg-white shadow dark:bg-gray-700">
              <div class="flex items-start justify-between rounded-t border-b p-4 dark:border-gray-600">
                <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
                  Spirit Scores, MVP & MSP
                </h3>
                <button
                  type="button"
                  class="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-transparent text-sm text-gray-400 hover:bg-gray-200 hover:text-gray-900 dark:hover:bg-gray-600 dark:hover:text-white"
                  data-modal-hide={`modal-${props.match.id}`}
                >
                  <svg
                    class="h-3 w-3"
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
              <div class="space-y-2 p-2">
                <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                  Spirit Scores
                </h2>
                <SpiritScoreTable
                  team_1={currTeam()}
                  team_2={oppTeam()}
                  spirit_score_team_1={currTeamSpiritScore()}
                  spirit_score_team_2={oppTeamSpiritScore()}
                />
                <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                  Spirit Scores - Self
                </h2>
                <SpiritScoreTable
                  team_1={currTeam()}
                  team_2={oppTeam()}
                  spirit_score_team_1={
                    props.match[`self_spirit_score_team_${currTeamNo()}`]
                  }
                  spirit_score_team_2={
                    props.match[`self_spirit_score_team_${oppTeamNo()}`]
                  }
                />
                <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                  MVPs
                </h2>
                <Show when={currTeamSpiritScore().mvp}>
                  <div class="mx-5 flex items-center space-x-4">
                    <img
                      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                      src={currTeamSpiritScore().mvp?.image_url}
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {currTeamSpiritScore().mvp?.first_name +
                          " " +
                          currTeamSpiritScore().mvp?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {currTeam().name}
                      </div>
                    </div>
                  </div>
                </Show>
                <Show when={oppTeamSpiritScore().mvp}>
                  <div class="mx-5 flex items-center space-x-4">
                    <img
                      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                      src={oppTeamSpiritScore().mvp?.image_url}
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {oppTeamSpiritScore().mvp?.first_name +
                          " " +
                          oppTeamSpiritScore().mvp?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {oppTeam().name}
                      </div>
                    </div>
                  </div>
                </Show>

                <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                  MSPs
                </h2>
                <Show when={currTeamSpiritScore().msp}>
                  <div class="mx-5 flex items-center space-x-4">
                    <img
                      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                      src={currTeamSpiritScore().msp?.image_url}
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {currTeamSpiritScore().msp?.first_name +
                          " " +
                          currTeamSpiritScore().msp?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {currTeam().name}
                      </div>
                    </div>
                  </div>
                </Show>
                <Show when={oppTeamSpiritScore().msp}>
                  <div class="mx-5 flex items-center space-x-4">
                    <img
                      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                      src={oppTeamSpiritScore().msp?.image_url}
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {oppTeamSpiritScore().msp?.first_name +
                          " " +
                          oppTeamSpiritScore().msp?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {oppTeam().name}
                      </div>
                    </div>
                  </div>
                </Show>

                <Show
                  when={
                    props.match[`self_spirit_score_team_${currTeamNo()}`]
                      ?.comments ||
                    props.match[`self_spirit_score_team_${oppTeamNo()}`]
                      ?.comments
                  }
                >
                  <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                    Comments
                  </h2>
                  <Show
                    when={
                      props.match[`self_spirit_score_team_${currTeamNo()}`]
                        ?.comments
                    }
                  >
                    <div class="mx-5 flex items-center space-x-4">
                      <div class="font-medium dark:text-white">
                        <div>
                          {
                            props.match[
                              `self_spirit_score_team_${currTeamNo()}`
                            ]?.comments
                          }
                        </div>
                        <div class="text-sm text-gray-500 dark:text-gray-400">
                          {currTeam().name}
                        </div>
                      </div>
                    </div>
                  </Show>
                  <Show
                    when={
                      props.match[`self_spirit_score_team_${oppTeamNo()}`]
                        ?.comments
                    }
                  >
                    <div class="mx-5 flex items-center space-x-4">
                      <div class="font-medium dark:text-white">
                        <div>
                          {
                            props.match[`self_spirit_score_team_${oppTeamNo()}`]
                              ?.comments
                          }
                        </div>
                        <div class="text-sm text-gray-500 dark:text-gray-400">
                          {oppTeam().name}
                        </div>
                      </div>
                    </div>
                  </Show>
                </Show>
              </div>
            </div>
          </div>
        </div>
      </Show>
      {/*Team Admin Actions*/}

      <Show
        when={props.match.status === "SCH" && (isMatchTeamAdmin() || isStaff())}
      >
        <div class="inline-flex w-full items-center justify-center">
          <hr class="my-6 h-px w-64 border-0 bg-gray-200 dark:bg-gray-700" />
          <span class="absolute left-1/2 -translate-x-1/2 bg-white px-3 text-sm dark:bg-gray-800">
            Match Scores
          </span>
        </div>
        <div class="flex flex-wrap justify-center">
          <Show
            when={checkIfSuggestedScoresClash(
              props.match["suggested_score_team_1"],
              props.match["suggested_score_team_2"]
            )}
          >
            <p class="mb-3 mr-2 rounded bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900 dark:text-red-300">
              Scores Clashing
            </p>
          </Show>
          <Show when={props.match[`suggested_score_team_${currTeamNo()}`]}>
            <p class="mb-2 w-full text-center text-sm">
              {
                props.match[`suggested_score_team_${currTeamNo()}`][
                  "entered_by"
                ]["full_name"].split(" ")[0]
              }
              {" | "}
              {currTeam().name}
              {": "}
              {
                props.match[`suggested_score_team_${currTeamNo()}`][
                  `score_team_${currTeamNo()}`
                ]
              }{" "}
              -{" "}
              {
                props.match[`suggested_score_team_${currTeamNo()}`][
                  `score_team_${oppTeamNo()}`
                ]
              }{" "}
            </p>
          </Show>
          <Show when={props.match[`suggested_score_team_${oppTeamNo()}`]}>
            <p class="mb-2 w-full text-center text-sm">
              {
                props.match[`suggested_score_team_${oppTeamNo()}`][
                  "entered_by"
                ]["full_name"].split(" ")[0]
              }
              {" | "}
              {oppTeam().name}
              {": "}
              {
                props.match[`suggested_score_team_${oppTeamNo()}`][
                  `score_team_${currTeamNo()}`
                ]
              }{" "}
              -{" "}
              {
                props.match[`suggested_score_team_${oppTeamNo()}`][
                  `score_team_${oppTeamNo()}`
                ]
              }{" "}
            </p>
          </Show>
          <Show
            when={
              isStaff() &&
              !isMatchTeamAdmin() &&
              !props.match[`suggested_score_team_${currTeamNo()}`] &&
              !props.match[`suggested_score_team_${oppTeamNo()}`]
            }
          >
            <p class="text-center text-sm">No scores have been submitted yet</p>
          </Show>
          <Show when={isMatchTeamAdmin()}>
            <button
              data-modal-target={"submit-score-modal" + props.match?.id}
              data-modal-toggle={"submit-score-modal" + props.match?.id}
              type="button"
              class={clsx(
                "relative mb-2 mr-2 inline-flex items-center justify-center overflow-hidden rounded-lg p-0.5 font-medium",
                "text-xs text-gray-900 hover:text-white focus:outline-none focus:ring-4 dark:text-white",
                props.buttonColor
                  ? matchCardColorToButtonStyles[props.buttonColor]
                  : matchCardColorToButtonStyles[getMatchCardColor(props.match)]
              )}
            >
              <Show
                when={
                  (props.match["team_1"].id === userAccessQuery.data.team_id &&
                    !props.match["suggested_score_team_1"]) ||
                  (props.match["team_2"].id === userAccessQuery.data.team_id &&
                    !props.match["suggested_score_team_2"])
                }
                fallback={
                  <>
                    <span class="relative inline-flex items-center rounded-md bg-white px-3 py-2.5 transition-all duration-75 ease-in group-hover:bg-opacity-0 dark:bg-gray-800">
                      Edit Score
                      <Icon path={pencil} class="ml-1.5 w-4" />
                    </span>
                  </>
                }
              >
                <span class="relative inline-flex items-center rounded-md bg-white px-3 py-2.5 transition-all duration-75 ease-in group-hover:bg-opacity-0 dark:bg-gray-800">
                  Submit Score
                  <Icon path={arrowRight} class="ml-1.5 w-4" />
                </span>
              </Show>
            </button>
          </Show>

          {/*Submit Score modal*/}
          <Show when={isMatchTeamAdmin()}>
            <div
              id={"submit-score-modal" + props.match?.id}
              data-modal-backdrop="static"
              tabIndex="-1"
              aria-hidden="true"
              class="fixed left-0 right-0 top-0 z-50 hidden h-[calc(100%-1rem)] max-h-full w-full overflow-y-auto overflow-x-hidden p-4 md:inset-0"
            >
              <div class="relative max-h-full w-full max-w-2xl">
                <div class="relative rounded-lg bg-white shadow dark:bg-gray-700">
                  <div class="flex items-start justify-between rounded-t border-b p-4 dark:border-gray-600">
                    <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
                      Submit Score
                    </h3>
                    <button
                      type="button"
                      class="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-transparent text-sm text-gray-400 hover:bg-gray-200 hover:text-gray-900 dark:hover:bg-gray-600 dark:hover:text-white"
                      data-modal-hide={"submit-score-modal" + props.match?.id}
                      onClick={() => {
                        queryClient.invalidateQueries({
                          queryKey: ["matches", props.tournamentSlug]
                        });
                        setTimeout(() => initFlowbite(), 500);
                      }}
                    >
                      <svg
                        class="h-3 w-3"
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
                  <div class="space-y-6 p-6">
                    <MatchScoreForm
                      match={props.match}
                      currTeamNo={currTeamNo()}
                      oppTeamNo={oppTeamNo()}
                    />
                  </div>
                  <div class="flex items-center rounded-b border-t border-gray-200 p-4 dark:border-gray-600 md:p-5">
                    <button
                      data-modal-hide={"submit-score-modal" + props.match?.id}
                      type="button"
                      onClick={() => {
                        queryClient.invalidateQueries({
                          queryKey: ["matches", props.tournamentSlug]
                        });
                        setTimeout(() => initFlowbite(), 500);
                      }}
                      class="ms-3 rounded-lg border border-gray-200 bg-white px-5 py-2.5 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-900 focus:z-10 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:border-gray-500 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-600"
                    >
                      Go Back
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </Show>
        </div>
      </Show>

      <Show
        when={
          (props.match.status === "COM" || props.match.status === "SCH") &&
          isStaff() &&
          (!props.match["spirit_score_team_2"] ||
            !props.match["spirit_score_team_1"])
        }
      >
        <div class="inline-flex w-full items-center justify-center">
          <hr class="my-6 h-px w-64 border-0 bg-gray-200 dark:bg-gray-700" />
          <span class="absolute left-1/2 -translate-x-1/2 bg-white px-3 text-sm dark:bg-gray-800">
            Spirit Scores
          </span>
        </div>
        <Show when={!oppTeamSpiritScore()}>
          <p class="text-center text-sm">{currTeam().name} pending</p>
        </Show>
        <Show when={!currTeamSpiritScore()}>
          <p class="text-center text-sm">{oppTeam().name} pending</p>
        </Show>
      </Show>
      <Show
        when={
          (props.match.status === "COM" || props.match.status === "SCH") &&
          isMatchTeamAdmin() &&
          ((props.match["team_1"].id === userAccessQuery?.data?.team_id &&
            !props.match["spirit_score_team_2"] &&
            (props.match["suggested_score_team_1"] ||
              props.match.status === "COM")) ||
            (props.match["team_2"].id === userAccessQuery?.data?.team_id &&
              !props.match["spirit_score_team_1"] &&
              (props.match["suggested_score_team_2"] ||
                props.match.status === "COM")))
        }
      >
        <div class="inline-flex w-full items-center justify-center">
          <hr class="my-6 h-px w-64 border-0 bg-gray-200 dark:bg-gray-700" />
          <span class="absolute left-1/2 -translate-x-1/2 bg-white px-3 text-sm dark:bg-gray-800">
            Spirit Scores
          </span>
        </div>
        <div class="mb-3 flex flex-wrap justify-center">
          <button
            data-modal-target={"submit-spirit-score-modal" + props.match?.id}
            data-modal-toggle={"submit-spirit-score-modal" + props.match?.id}
            type="button"
            class={clsx(
              "relative mb-2 mr-2 inline-flex items-center justify-center overflow-hidden rounded-lg p-0.5 font-medium",
              "text-xs text-gray-900 hover:text-white focus:outline-none focus:ring-4 dark:text-white",
              props.buttonColor
                ? matchCardColorToButtonStyles[props.buttonColor]
                : matchCardColorToButtonStyles[getMatchCardColor(props.match)]
            )}
          >
            <span class="relative inline-flex items-center rounded-md bg-white px-3 py-2.5 transition-all duration-75 ease-in group-hover:bg-opacity-0 dark:bg-gray-800">
              Submit Spirit Score
              <Icon path={arrowRight} class="ml-1.5 w-4" />
            </span>
          </button>

          {/*Submit Spirit Score modal*/}
          <div
            id={"submit-spirit-score-modal" + props.match?.id}
            data-modal-backdrop="static"
            tabIndex="-1"
            aria-hidden="true"
            class="fixed left-0 right-0 top-0 z-50 hidden h-[calc(100%-1rem)] max-h-full w-full overflow-y-auto overflow-x-hidden p-4 md:inset-0"
          >
            <div class="relative max-h-full w-full max-w-2xl">
              <div class="relative rounded-lg bg-white shadow dark:bg-gray-700">
                <div class="flex items-start justify-between rounded-t border-b p-4 dark:border-gray-600">
                  <h3 class="text-xl font-semibold text-gray-900 dark:text-white">
                    Submit Spirit Score
                  </h3>
                  <button
                    type="button"
                    class="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-transparent text-sm text-gray-400 hover:bg-gray-200 hover:text-gray-900 dark:hover:bg-gray-600 dark:hover:text-white"
                    data-modal-hide={
                      "submit-spirit-score-modal" + props.match?.id
                    }
                    onClick={() => {
                      queryClient.invalidateQueries({
                        queryKey: ["matches", props.tournamentSlug]
                      });
                      setTimeout(() => initFlowbite(), 500);
                    }}
                  >
                    <svg
                      class="h-3 w-3"
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
                <div class="space-y-6 p-6">
                  <MatchSpiritScoreForm
                    match={props.match}
                    oppTeamNo={
                      props.match["team_1"].id === userAccessQuery.data.team_id
                        ? 2
                        : 1
                    }
                  />
                </div>
                <div class="flex items-center rounded-b border-t border-gray-200 p-4 dark:border-gray-600 md:p-5">
                  <button
                    data-modal-hide={
                      "submit-spirit-score-modal" + props.match?.id
                    }
                    type="button"
                    onClick={() => {
                      queryClient.invalidateQueries({
                        queryKey: ["matches", props.tournamentSlug]
                      });
                      setTimeout(() => initFlowbite(), 500);
                    }}
                    class="ms-3 rounded-lg border border-gray-200 bg-white px-5 py-2.5 text-sm font-medium text-gray-500 hover:bg-gray-100 hover:text-gray-900 focus:z-10 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:border-gray-500 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-600"
                  >
                    Go Back
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Show>
    </>
  );
};

export default TournamentMatch;
