import {
  createSignal,
  createEffect,
  onMount,
  For,
  Switch,
  Match,
  Show,
  Suspense
} from "solid-js";
import {
  displayDate,
  fetchUrl,
  membershipYearOptions,
  playerMatches
} from "../utils";
import {
  membershipStartDate,
  membershipEndDate,
  annualMembershipFee,
  sponsoredAnnualMembershipFee,
  minAge,
  minAgeWarning
} from "../constants";
import MembershipPlayerList from "./MembershipPlayerList";
import { Icon } from "solid-heroicons";
import { magnifyingGlass } from "solid-heroicons/solid-mini";
import { inboxStack } from "solid-heroicons/solid";
import Breadcrumbs from "./Breadcrumbs";
import PhonePePayment from "./PhonePePayment";
import { initFlowbite } from "flowbite";
import { createQuery } from "@tanstack/solid-query";
import { fetchPlayers } from "../queries";
import PlayersSkeleton from "../skeletons/Players";

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
            class="flex items-center justify-between w-full py-5 font-medium text-left text-gray-500 border-b border-gray-200 dark:border-gray-700 dark:text-gray-400"
            data-accordion-target="#accordion-flush-body-1"
            aria-expanded="true"
            aria-controls="accordion-flush-body-1"
          >
            <span>Search Players</span>
            <svg
              data-accordion-icon
              class="w-3 h-3 rotate-180 shrink-0"
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
          <div class="flex p-3 flex-wrap">
            <select
              id="countries"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 w-1/4 min-w-fit mr-5 mb-4 md:mb-0"
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
              <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                <Icon path={magnifyingGlass} style={{ width: "20px" }} />
              </div>
              <input
                type="search"
                id="default-search"
                class="block w-full p-4 pl-10 text-sm text-gray-900 border border-gray-300 rounded-lg bg-gray-50 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                placeholder="Search Player Names"
                onInput={onSearchInput}
              />
            </div>
          </div>
          <ul
            class="h-48 px-3 pb-3 overflow-y-auto text-sm text-gray-700 dark:text-gray-200"
            aria-labelledby="playerSearchButton"
          >
            <li>
              <div class="flex items-center pl-2 rounded hover:bg-gray-100 dark:hover:bg-gray-600">
                <input
                  id={"checkbox-item-0"}
                  type="checkbox"
                  class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-700 dark:focus:ring-offset-gray-700 focus:ring-2 dark:bg-gray-600 dark:border-gray-500"
                  onChange={handleSelectAll}
                  checked={selectAll()}
                />
                <label
                  for={"checkbox-item-0"}
                  class="w-full py-2 ml-2 text-sm font-medium text-gray-600 rounded dark:text-gray-400"
                >
                  <div class="w-full pl-3">Select All</div>
                </label>
              </div>
            </li>
            <Suspense fallback={<PlayersSkeleton n={10} />}>
              <For each={searchResults()}>
                {player => (
                  <li>
                    <div class="flex items-center pl-2 rounded hover:bg-gray-100 dark:hover:bg-gray-600">
                      <input
                        id={`checkbox-item-${player.id}`}
                        type="checkbox"
                        class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-700 dark:focus:ring-offset-gray-700 focus:ring-2 dark:bg-gray-600 dark:border-gray-500"
                        onChange={e => props.onPlayerChecked(e, player)}
                        checked={
                          player.has_membership || checkedPlayers()[player.id]
                        }
                        disabled={player.has_membership}
                      />
                      <label
                        for={`checkbox-item-${player.id}`}
                        class="w-full py-2 ml-2 text-sm font-medium text-gray-900 rounded dark:text-gray-300"
                      >
                        <div class="w-full pl-3">
                          <div class="text-gray-500 text-sm mb-1.5 dark:text-gray-400">
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
                class="p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300"
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
                class="p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300"
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
          class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
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
            class="p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50 dark:bg-gray-800 dark:text-red-400"
            role="alert"
          >
            * {minAgeWarning} Please ensure that all the players are atleast{" "}
            {minAge} years old before {displayDate(endDate())}.
          </div>
        </Show>
        <div>
          <Switch>
            <Match when={!paymentSuccess()}>
              <PhonePePayment
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
                class={`my-2 text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 ${
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
