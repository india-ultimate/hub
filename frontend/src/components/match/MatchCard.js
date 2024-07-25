import { A } from "@solidjs/router";
import { createQuery, useQueryClient } from "@tanstack/solid-query";
import { clsx } from "clsx";
import { Icon } from "solid-heroicons";
import { arrowRight, pencil, play } from "solid-heroicons/solid";
import { createEffect, createSignal, Match, Show, Switch } from "solid-js";

import {
  matchCardColorToButtonStyles,
  matchCardColorToRingColorMap
} from "../../colors";
import { fetchTeams, fetchUserAccessByTournamentSlug } from "../../queries";
import { getMatchCardColor } from "../../utils";
import MatchScoreForm from "../tournament/MatchScoreForm";
import MatchSpiritScoreForm from "../tournament/MatchSpiritScoreForm";
import SpiritScoreTable from "../tournament/SpiritScoreTable";
import FinalSpiritScores from "./FinalSpiritScores";
import MatchHeader from "./MatchHeader";
import SubmitScore from "./SubmitScore";
import SubmitSpiritScore from "./SubmitSpiritScore";
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
  const [startTime, setStartTime] = createSignal("");
  const [endTime, setEndTime] = createSignal("");

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
    const startTimeObject = new Date(Date.parse(props.match.time));
    const endTimeObject = new Date(
      startTimeObject.getTime() + props.match.duration_mins * 60000
    );

    setStartTime(
      startTimeObject.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "numeric",
        timeZone: "UTC"
      })
    );
    setEndTime(
      endTimeObject.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "numeric",
        timeZone: "UTC"
      })
    );
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

  const isTeamAdminOf = team_id => {
    return (
      userAccessQuery?.data?.admin_team_ids?.length > 0 &&
      userAccessQuery?.data?.admin_team_ids.indexOf(team_id) > -1
    );
  };

  const hasUserNotSubmittedScores = () => {
    return (
      (isTeamAdminOf(props.match["team_1"].id) &&
        !props.match["suggested_score_team_1"]) ||
      (isTeamAdminOf(props.match["team_2"].id) &&
        !props.match["suggested_score_team_2"])
    );
  };

  const canUserSubmitSpiritScores = () => {
    return (
      (isTeamAdminOf(props.match["team_1"].id) &&
        !props.match["spirit_score_team_2"] &&
        (props.match["suggested_score_team_1"] ||
          props.match.status === "COM")) ||
      (isTeamAdminOf(props.match["team_2"].id) &&
        !props.match["spirit_score_team_1"] &&
        (props.match["suggested_score_team_2"] || props.match.status === "COM"))
    );
  };

  const isStaff = () => {
    return (
      userAccessQuery.data &&
      (userAccessQuery.data.is_staff ||
        userAccessQuery.data.is_tournament_admin)
    );
  };

  const getTeamImage = team => {
    return team?.image ?? team?.image_url;
  };

  return (
    <>
      <div class="mb-4">
        <MatchHeader
          match={props.match}
          dontMinimiseMatchName
          matchCardColorOverride={props.matchCardColorOverride}
        />
      </div>
      <div class="flex justify-center text-sm">
        <Show
          when={props.match[`team_${currTeamNo()}`]}
          fallback={
            <span class="w-1/3 text-center font-bold">
              {props.match[`placeholder_seed_${currTeamNo()}`]}
            </span>
          }
        >
          <img
            class={clsx(
              "mr-1 inline-block h-6 w-6 rounded-full p-1 ring-2",
              props.imgRingColor
                ? matchCardColorToRingColorMap[props.imgRingColor]
                : matchCardColorToRingColorMap[getMatchCardColor(props.match)]
            )}
            src={getTeamImage(
              teamsMap()[props.match[`team_${currTeamNo()}`].id]
            )}
            alt="Bordered avatar"
          />
          <span class="w-1/3 text-center font-bold text-gray-600 dark:text-gray-300">
            <Show
              when={props.bothTeamsClickable}
              fallback={`${props.match[`team_${currTeamNo()}`].name} (${
                props.match[`placeholder_seed_${currTeamNo()}`]
              })`}
            >
              <A
                href={`/tournament/${props.tournamentSlug}/team/${
                  props.match[`team_${currTeamNo()}`].slug
                }`}
              >
                {`${props.match[`team_${currTeamNo()}`].name} (${
                  props.match[`placeholder_seed_${currTeamNo()}`]
                })`}
              </A>
            </Show>
          </span>
        </Show>

        <span class="mx-2">VS</span>
        <Show
          when={props.match[`team_${oppTeamNo()}`]}
          fallback={
            <span class="w-1/3 text-center font-bold">
              {props.match[`placeholder_seed_${oppTeamNo()}`]}
            </span>
          }
        >
          <span class="w-1/3 text-center font-medium text-gray-600 dark:text-gray-300">
            <A
              href={`/tournament/${props.tournamentSlug}/team/${
                props.match[`team_${oppTeamNo()}`].slug
              }`}
            >
              {`${props.match[`team_${oppTeamNo()}`].name} (${
                props.match[`placeholder_seed_${oppTeamNo()}`]
              })`}
            </A>
          </span>

          <img
            class={clsx(
              "mr-1 inline-block h-6 w-6 rounded-full p-1 ring-2",
              props.imgRingColor
                ? matchCardColorToRingColorMap[props.imgRingColor]
                : matchCardColorToRingColorMap[getMatchCardColor(props.match)]
            )}
            src={getTeamImage(
              teamsMap()[props.match[`team_${oppTeamNo()}`].id]
            )}
            alt="Bordered avatar"
          />
        </Show>
      </div>

      {/* Match score */}
      <Show when={props.match.status === "COM"}>
        <p class="text-center font-bold">
          <Switch>
            <Match
              when={
                props.match[`score_team_${currTeamNo()}`] >
                props.match[`score_team_${oppTeamNo()}`]
              }
            >
              <span class="text-green-500 dark:text-green-400">
                {props.match[`score_team_${currTeamNo()}`]}
              </span>
              <span>{" - "}</span>
              <span class="text-red-500 dark:text-red-400">
                {props.match[`score_team_${oppTeamNo()}`]}
              </span>
            </Match>
            <Match
              when={
                props.match[`score_team_${currTeamNo()}`] <
                props.match[`score_team_${oppTeamNo()}`]
              }
            >
              <span class="text-red-500 dark:text-red-400">
                {props.match[`score_team_${currTeamNo()}`]}
              </span>
              <span>{" - "}</span>
              <span class="text-green-500 dark:text-green-400">
                {props.match[`score_team_${oppTeamNo()}`]}
              </span>
            </Match>
            <Match
              when={
                props.match[`score_team_${currTeamNo()}`] ===
                props.match[`score_team_${oppTeamNo()}`]
              }
            >
              <span class="text-blue-500 dark:text-blue-400">
                {props.match[`score_team_${currTeamNo()}`]}
              </span>
              <span>{" - "}</span>
              <span class="text-blue-500 dark:text-blue-400">
                {props.match[`score_team_${oppTeamNo()}`]}
              </span>
            </Match>
          </Switch>
        </p>
      </Show>
      {/* Field and duration */}
      <p class="mt-2 text-center text-sm">
        {props.match.field?.name +
          " | " +
          startTime() +
          " - " +
          endTime() +
          " | " +
          props.match.duration_mins +
          " mins"}
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
      <Show
        when={
          props.match[`spirit_score_team_${currTeamNo()}`] &&
          props.match[`spirit_score_team_${oppTeamNo()}`]
        }
      >
        <div class="mt-2 flex justify-center">
          <FinalSpiritScores
            bgColor={`bg-${
              props.buttonColor || getMatchCardColor(props.match)
            }-100`}
            badgeColor={
              props.buttonColor
                ? matchCardColorToButtonStyles[props.buttonColor]
                : matchCardColorToButtonStyles[getMatchCardColor(props.match)]
            }
            spiritScoreText={
              props.match[`spirit_score_team_${currTeamNo()}`].total +
              " - " +
              props.match[`spirit_score_team_${oppTeamNo()}`].total
            }
          >
            <div class="space-y-2 py-2 pr-2 sm:pl-2 sm:pr-4">
              <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                Spirit Scores
              </h2>
              <SpiritScoreTable
                team_1={props.match[`team_${currTeamNo()}`]}
                team_2={props.match[`team_${oppTeamNo()}`]}
                spirit_score_team_1={
                  props.match[`spirit_score_team_${currTeamNo()}`]
                }
                spirit_score_team_2={
                  props.match[`spirit_score_team_${oppTeamNo()}`]
                }
              />
              <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                Spirit Scores - Self
              </h2>
              <SpiritScoreTable
                team_1={props.match[`team_${currTeamNo()}`]}
                team_2={props.match[`team_${oppTeamNo()}`]}
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

              <Switch>
                <Match
                  when={
                    !props.useUCRegistrations &&
                    props.match[`spirit_score_team_${currTeamNo()}`].mvp_v2
                  }
                >
                  <div class="mx-2 font-medium dark:text-white">
                    <div>
                      {
                        props.match[`spirit_score_team_${currTeamNo()}`].mvp_v2
                          ?.full_name
                      }
                    </div>
                    <div class="text-sm text-gray-500 dark:text-gray-400">
                      {props.match[`team_${currTeamNo()}`].name}
                    </div>
                  </div>
                </Match>
                <Match
                  when={
                    props.useUCRegistrations &&
                    props.match[`spirit_score_team_${currTeamNo()}`].mvp
                  }
                >
                  <div class="mx-2 flex items-center space-x-4">
                    <img
                      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                      src={
                        props.match[`spirit_score_team_${currTeamNo()}`].mvp
                          ?.image_url
                      }
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {props.match[`spirit_score_team_${currTeamNo()}`].mvp
                          ?.first_name +
                          " " +
                          props.match[`spirit_score_team_${currTeamNo()}`].mvp
                            ?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${currTeamNo()}`].name}
                      </div>
                    </div>
                  </div>
                </Match>
              </Switch>

              <Switch>
                <Match
                  when={
                    !props.useUCRegistrations &&
                    props.match[`spirit_score_team_${oppTeamNo()}`].mvp_v2
                  }
                >
                  <div class="mx-2 font-medium dark:text-white">
                    <div>
                      {
                        props.match[`spirit_score_team_${oppTeamNo()}`].mvp_v2
                          ?.full_name
                      }
                    </div>
                    <div class="text-sm text-gray-500 dark:text-gray-400">
                      {props.match[`team_${oppTeamNo()}`].name}
                    </div>
                  </div>
                </Match>
                <Match
                  when={
                    props.useUCRegistrations &&
                    props.match[`spirit_score_team_${oppTeamNo()}`].mvp
                  }
                >
                  <div class="mx-2 flex items-center space-x-4">
                    <img
                      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                      src={
                        props.match[`spirit_score_team_${oppTeamNo()}`].mvp
                          ?.image_url
                      }
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {props.match[`spirit_score_team_${oppTeamNo()}`].mvp
                          ?.first_name +
                          " " +
                          props.match[`spirit_score_team_${oppTeamNo()}`].mvp
                            ?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${oppTeamNo()}`].name}
                      </div>
                    </div>
                  </div>
                </Match>
              </Switch>

              <h2 class="text-center font-bold text-blue-600 dark:text-blue-500">
                MSPs
              </h2>
              <Switch>
                <Match
                  when={
                    !props.useUCRegistrations &&
                    props.match[`spirit_score_team_${currTeamNo()}`].msp_v2
                  }
                >
                  <div class="mx-2 flex items-center space-x-4">
                    <div class="font-medium dark:text-white">
                      <div>
                        {
                          props.match[`spirit_score_team_${currTeamNo()}`]
                            .msp_v2?.full_name
                        }
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${currTeamNo()}`].name}
                      </div>
                    </div>
                  </div>
                </Match>
                <Match
                  when={
                    props.useUCRegistrations &&
                    props.match[`spirit_score_team_${currTeamNo()}`].msp
                  }
                >
                  <div class="mx-2 flex items-center space-x-4">
                    <img
                      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                      src={
                        props.match[`spirit_score_team_${currTeamNo()}`].msp
                          ?.image_url
                      }
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {props.match[`spirit_score_team_${currTeamNo()}`].msp
                          ?.first_name +
                          " " +
                          props.match[`spirit_score_team_${currTeamNo()}`].msp
                            ?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${currTeamNo()}`].name}
                      </div>
                    </div>
                  </div>
                </Match>
              </Switch>
              <Switch>
                <Match
                  when={
                    !props.useUCRegistrations &&
                    props.match[`spirit_score_team_${oppTeamNo()}`].msp_v2
                  }
                >
                  <div class="mx-2 flex items-center space-x-4">
                    <div class="font-medium dark:text-white">
                      <div>
                        {
                          props.match[`spirit_score_team_${oppTeamNo()}`].msp_v2
                            ?.full_name
                        }
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${oppTeamNo()}`].name}
                      </div>
                    </div>
                  </div>
                </Match>
                <Match
                  when={
                    props.useUCRegistrations &&
                    props.match[`spirit_score_team_${oppTeamNo()}`].msp
                  }
                >
                  <div class="mx-2 flex items-center space-x-4">
                    <img
                      class="h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500"
                      src={
                        props.match[`spirit_score_team_${oppTeamNo()}`].msp
                          ?.image_url
                      }
                      alt="Image"
                    />
                    <div class="font-medium dark:text-white">
                      <div>
                        {props.match[`spirit_score_team_${oppTeamNo()}`].msp
                          ?.first_name +
                          " " +
                          props.match[`spirit_score_team_${oppTeamNo()}`].msp
                            ?.last_name}
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${oppTeamNo()}`].name}
                      </div>
                    </div>
                  </div>
                </Match>
              </Switch>

              <Show
                when={
                  props.match[`self_spirit_score_team_${currTeamNo()}`]
                    ?.comments ||
                  props.match[`self_spirit_score_team_${oppTeamNo()}`]?.comments
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
                  <div class="mx-2 flex items-center space-x-4">
                    <div class="font-medium dark:text-white">
                      <div>
                        {
                          props.match[`self_spirit_score_team_${currTeamNo()}`]
                            ?.comments
                        }
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${currTeamNo()}`].name}
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
                  <div class="mx-2 flex items-center space-x-4">
                    <div class="font-medium dark:text-white">
                      <div>
                        {
                          props.match[`self_spirit_score_team_${oppTeamNo()}`]
                            ?.comments
                        }
                      </div>
                      <div class="text-sm text-gray-500 dark:text-gray-400">
                        {props.match[`team_${oppTeamNo()}`].name}
                      </div>
                    </div>
                  </div>
                </Show>
              </Show>
            </div>
          </FinalSpiritScores>
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
              {props.match[`team_${currTeamNo()}`].name}
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
              {props.match[`team_${oppTeamNo()}`].name}
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
            <SubmitScore
              buttonColor={
                props.buttonColor
                  ? matchCardColorToButtonStyles[props.buttonColor]
                  : matchCardColorToButtonStyles[getMatchCardColor(props.match)]
              }
              button={
                hasUserNotSubmittedScores()
                  ? { text: "Submit Score", icon: arrowRight }
                  : { text: "Edit Score", icon: pencil }
              }
              onClose={() => {
                queryClient.invalidateQueries({
                  queryKey: ["matches", props.tournamentSlug]
                });
                queryClient.invalidateQueries({
                  queryKey: ["team-matches", props.tournamentSlug]
                });
              }}
            >
              <div class="rounded-lg bg-white p-4 shadow dark:bg-gray-700">
                <MatchScoreForm
                  match={props.match}
                  currTeamNo={currTeamNo()}
                  oppTeamNo={oppTeamNo()}
                />
              </div>
            </SubmitScore>
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
        <Show when={!props.match[`spirit_score_team_${oppTeamNo()}`]}>
          <p class="text-center text-sm">
            {props.match[`team_${currTeamNo()}`].name} pending
          </p>
        </Show>
        <Show when={!props.match[`spirit_score_team_${currTeamNo()}`]}>
          <p class="text-center text-sm">
            {props.match[`team_${oppTeamNo()}`].name} pending
          </p>
        </Show>
      </Show>

      <Show
        when={
          (props.match.status === "COM" || props.match.status === "SCH") &&
          isMatchTeamAdmin() &&
          canUserSubmitSpiritScores()
        }
      >
        <div class="inline-flex w-full items-center justify-center">
          <hr class="my-6 h-px w-64 border-0 bg-gray-200 dark:bg-gray-700" />
          <span class="absolute left-1/2 -translate-x-1/2 bg-white px-3 text-sm dark:bg-gray-800">
            Spirit Scores
          </span>
        </div>
        <div class="mb-3 flex flex-wrap justify-center">
          <SubmitSpiritScore
            buttonColor={
              props.buttonColor
                ? matchCardColorToButtonStyles[props.buttonColor]
                : matchCardColorToButtonStyles[getMatchCardColor(props.match)]
            }
            onClose={() => {
              queryClient.invalidateQueries({
                queryKey: ["matches", props.tournamentSlug]
              });
              queryClient.invalidateQueries({
                queryKey: ["team-matches", props.tournamentSlug]
              });
            }}
          >
            <Show when={isTeamAdminOf(props.match["team_1"].id)}>
              <MatchSpiritScoreForm
                match={props.match}
                tournamentSlug={props.tournamentSlug}
                oppTeamNo={2}
                curTeamNo={1}
              />
            </Show>
            <Show when={isTeamAdminOf(props.match["team_2"].id)}>
              <MatchSpiritScoreForm
                match={props.match}
                tournamentSlug={props.tournamentSlug}
                oppTeamNo={1}
                curTeamNo={2}
              />
            </Show>
          </SubmitSpiritScore>
        </div>
      </Show>
    </>
  );
};

export default TournamentMatch;
