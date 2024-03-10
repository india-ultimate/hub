import { createQuery } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import { inboxStack } from "solid-heroicons/solid";
import { magnifyingGlass } from "solid-heroicons/solid-mini";
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

import {
  annualMembershipFee,
  membershipEndDate,
  membershipStartDate,
  minAge,
  minAgeWarning,
  sponsoredAnnualMembershipFee
} from "../constants";
import { fetchPlayers } from "../queries";
import PlayersSkeleton from "../skeletons/Players";
import {
  displayDate,
  fetchUrl,
  membershipYearOptions,
  playerMatches
} from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import MembershipPlayerList from "./MembershipPlayerList";
import RazorpayPayment from "./RazorpayPayment";

const PlayerSearchDropdown = props => {
  const query = createQuery(() => ["players"], fetchPlayers, {
    refetchOnWindowFocus: false
  });
  const [searchText, setSearchText] = createSignal("");
  const [selectedTeam, setSelectedTeam] = createSignal("");
  const [selectAll, setSelectAll] = createSignal(false);
  const [checkedPlayers, setCheckedPlayers] = createSignal({});
  const [allTeamsSearch, setAllTeamsSearch] = createSignal(false);
  const [searchResults, setSearchResults] = createSignal([]);

  const handleSelectAll = e => {
    query?.data
      .filter(p => playerMatches(p, searchText(), selectedTeam()))
      .map(p => props.onPlayerChecked(e, p));

    setSelectAll(e.target.checked);
  };

  createEffect(() => {
    setSelectAll(false);
  });

  createEffect(() => {
    let newCheckedPlayers = {};

    props.payingPlayers.map(p => {
      newCheckedPlayers[p.id] = true;
    });

    setCheckedPlayers(newCheckedPlayers);
  });

  const [timer, setTimer] = createSignal();

  const onSearchInput = e => {
    if (timer()) {
      clearTimeout(timer());
    }
    const timeout = setTimeout(() => setSearchText(e.target.value), 700);
    setTimer(timeout);
  };

  createEffect(() => {
    let results = query?.data?.filter(p =>
      playerMatches(p, searchText(), selectedTeam())
    );
    if (results?.length > 0) {
      setAllTeamsSearch(false);
    } else if (query?.data?.length > 0) {
      setAllTeamsSearch(true);
      results = query?.data?.filter(p => playerMatches(p, searchText()));
    }
    setSearchResults(results);
  });

  return (
    <>
      <div
        id="accordion-flush"
        data-accordion="collapse"
        class="mb-10"
        data-active-classes="bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
        data-inactive-classes="text-gray-500 dark:text-gray-400"
      >
        <h2 id="accordion-flush-heading-1">
          <button
            type="button"
            class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
            data-accordion-target="#accordion-flush-body-1"
            aria-expanded="true"
            aria-controls="accordion-flush-body-1"
          >
            <span>Search Players</span>
            <svg
              data-accordion-icon
              class="h-3 w-3 shrink-0 rotate-180"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 10 6"
            >
              <path
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5 5 1 1 5"
              />
            </svg>
          </button>
        </h2>
        <div
          id="accordion-flush-body-1"
          class="hidden"
          aria-labelledby="accordion-flush-heading-1"
        >
          <div class="flex flex-wrap p-3">
            <select
              id="countries"
              class="mb-4 mr-5 block w-1/4 min-w-fit rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500 md:mb-0"
              onChange={e => setSelectedTeam(e.target.value)}
              value={selectedTeam()}
            >
              <option value="" selected>
                All Teams
              </option>
              <For each={props.teams}>
                {team => <option value={team.id}>{team.name}</option>}
              </For>
            </select>
            <div class="relative flex-grow">
              <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                <Icon path={magnifyingGlass} style={{ width: "20px" }} />
              </div>
              <input
                type="search"
                id="default-search"
                class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-4 pl-10 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
                placeholder="Search Player Names"
                onInput={onSearchInput}
              />
            </div>
          </div>
          <ul
            class="h-48 overflow-y-auto px-3 pb-3 text-sm text-gray-700 dark:text-gray-200"
            aria-labelledby="playerSearchButton"
          >
            <li>
              <div class="flex items-center rounded pl-2 hover:bg-gray-100 dark:hover:bg-gray-600">
                <input
                  id={"checkbox-item-0"}
                  type="checkbox"
                  class="h-4 w-4 rounded border-gray-300 bg-gray-100 text-blue-600 focus:ring-2 focus:ring-blue-500 dark:border-gray-500 dark:bg-gray-600 dark:ring-offset-gray-700 dark:focus:ring-blue-600 dark:focus:ring-offset-gray-700"
                  onChange={handleSelectAll}
                  checked={selectAll()}
                />
                <label
                  for={"checkbox-item-0"}
                  class="ml-2 w-full rounded py-2 text-sm font-medium text-gray-600 dark:text-gray-400"
                >
                  <div class="w-full pl-3">Select All</div>
                </label>
              </div>
            </li>
            <Suspense fallback={<PlayersSkeleton n={10} />}>
              <For each={searchResults()}>
                {player => (
                  <li>
                    <div class="flex items-center rounded pl-2 hover:bg-gray-100 dark:hover:bg-gray-600">
                      <input
                        id={`checkbox-item-${player.id}`}
                        type="checkbox"
                        class="h-4 w-4 rounded border-gray-300 bg-gray-100 text-blue-600 focus:ring-2 focus:ring-blue-500 dark:border-gray-500 dark:bg-gray-600 dark:ring-offset-gray-700 dark:focus:ring-blue-600 dark:focus:ring-offset-gray-700"
                        onChange={e => props.onPlayerChecked(e, player)}
                        checked={
                          player.has_membership || checkedPlayers()[player.id]
                        }
                        disabled={player.has_membership}
                      />
                      <label
                        for={`checkbox-item-${player.id}`}
                        class="ml-2 w-full rounded py-2 text-sm font-medium text-gray-900 dark:text-gray-300"
                      >
                        <div class="w-full pl-3">
                          <div class="mb-1.5 text-sm text-gray-500 dark:text-gray-400">
                            <span
                              class={`font-semibold ${
                                player.has_membership
                                  ? "text-gray-300 dark:text-gray-400"
                                  : "text-gray-900 dark:text-white"
                              }`}
                            >
                              {player.full_name}
                            </span>
                          </div>
                          <div class="text-xs text-blue-600 dark:text-blue-500">
                            {player.teams.map(team => team["name"]).join(", ")}{" "}
                            ({player.city})
                          </div>
                        </div>
                      </label>
                    </div>
                  </li>
                )}
              </For>
            </Suspense>
            <Show when={allTeamsSearch() && searchResults()?.length > 0}>
              <div
                class="mb-4 rounded-lg bg-yellow-50 p-4 text-sm text-yellow-800 dark:bg-gray-800 dark:text-yellow-300"
                role="alert"
              >
                Searching for players across all teams, since no player was
                found in "
                {props?.teams?.find(t => t.id === Number(selectedTeam()))?.name}
                " with the current search text. If the player is rostered with
                the team on Ultimate Central but not showing up in the team's
                search, they need to link their Ultimate Central account.
              </div>
            </Show>
            <Show when={searchResults()?.length == 0}>
              <div
                class="mb-4 rounded-lg bg-yellow-50 p-4 text-sm text-yellow-800 dark:bg-gray-800 dark:text-yellow-300"
                role="alert"
              >
                Could not find any player matching "{searchText()}"; Make sure
                that the player has registered on The Hub.
              </div>
            </Show>
          </ul>
        </div>
      </div>
    </>
  );
};

const GroupMembership = () => {
  const [status, setStatus] = createSignal();

  const years = membershipYearOptions();
  const [year, setYear] = createSignal(years?.[0]);
  const [startDate, setStartDate] = createSignal("");
  const [endDate, setEndDate] = createSignal("");

  const [teams, setTeams] = createSignal([]);
  const [payingPlayers, setPayingPlayers] = createSignal([]);
  const [paymentSuccess, setPaymentSuccess] = createSignal(false);

  const teamsSuccessHandler = async response => {
    const data = await response.json();
    if (response.ok) {
      setTeams(
        data.sort((a, b) => a.name.toLowerCase() > b.name.toLowerCase())
      );
    } else {
      console.log(data);
    }
  };

  const fetchTeams = () => {
    console.log("Fetching teams info...");
    fetchUrl("/api/teams", teamsSuccessHandler, error => console.log(error));
  };

  const paymentSuccessCallback = () => {
    setPaymentSuccess(true);
  };

  onMount(() => {
    fetchTeams();
  });

  const handleYearChange = e => {
    setYear(Number(e.target.value));
  };

  const handlePlayerChecked = (e, player) => {
    // Don't perform any actions on a player who already has a membership
    if (player?.has_membership) {
      return;
    }
    if (e.target.checked) {
      // Add player to paying Players
      setPayingPlayers([
        ...payingPlayers().filter(p => p.id !== player.id),
        player
      ]);
    } else {
      // Remove player from paying Players
      setPayingPlayers(payingPlayers().filter(p => p.id !== player.id));
    }
  };

  const formatDate = dateArray => {
    const [dd, mm, YYYY] = dateArray;
    const DD = dd.toString().padStart(2, "0");
    const MM = mm.toString().padStart(2, "0");
    return `${YYYY}-${MM}-${DD}`;
  };

  createEffect(() => {
    setStartDate(formatDate([...membershipStartDate, year()]));
    setEndDate(formatDate([...membershipEndDate, year() + 1]));
  });

  const [payDisabled, setPayDisabled] = createSignal(false);
  createEffect(() => {
    setPayDisabled(payingPlayers().length === 0);
  });

  const getAmount = () =>
    payingPlayers().reduce(
      (acc, player) =>
        acc +
        (player?.sponsored
          ? sponsoredAnnualMembershipFee
          : annualMembershipFee),
      0
    ) / 100;

  return (
    <div>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Group Membership" }
        ]}
      />
      <h1 class="text-2xl font-bold text-blue-500">Group Membership</h1>
      <h3>Renew membership for a group</h3>
      <div class="my-2">
        <select
          id="year"
          class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          value={year()}
          onInput={handleYearChange}
          required
        >
          <For each={years}>
            {year => (
              <option value={year}>
                {year} &mdash; {year + 1}
              </option>
            )}
          </For>
        </select>
        <Show when={!paymentSuccess()}>
          <PlayerSearchDropdown
            teams={teams()}
            payingPlayers={payingPlayers()}
            onPlayerChecked={handlePlayerChecked}
          />
        </Show>
        <MembershipPlayerList
          players={payingPlayers()}
          fee={getAmount()}
          startDate={displayDate(startDate())}
          endDate={displayDate(endDate())}
        />
        <Show when={payingPlayers()?.find(p => p.is_minor)}>
          <div
            class="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-gray-800 dark:text-red-400"
            role="alert"
          >
            * {minAgeWarning} Please ensure that all the players are atleast{" "}
            {minAge} years old before {displayDate(endDate())}.
          </div>
        </Show>
        <div>
          <Switch>
            <Match when={!paymentSuccess()}>
              <RazorpayPayment
                disabled={payDisabled()}
                annual={true}
                year={year()}
                player_ids={payingPlayers().map(p => p.id)}
                amount={getAmount()}
                setStatus={setStatus}
                successCallback={paymentSuccessCallback}
              />
            </Match>
            <Match when={paymentSuccess()}>
              <button
                class={`my-2 w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto ${
                  payDisabled() ? "cursor-not-allowed" : ""
                } `}
                onClick={() => {
                  setPaymentSuccess(false);
                  setPayingPlayers([]);
                  setStatus("");
                  initFlowbite();
                }}
                disabled={!paymentSuccess()}
              >
                Make another Payment
              </button>
            </Match>
          </Switch>
        </div>
      </div>
      <p>{status()}</p>
    </div>
  );
};

export default GroupMembership;
