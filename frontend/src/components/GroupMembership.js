import { useStore } from "../store";
import {
  createSignal,
  createEffect,
  onCleanup,
  onMount,
  For,
  Switch,
  Match,
  Show
} from "solid-js";
import {
  fetchUserData,
  displayDate,
  fetchUrl,
  membershipYearOptions,
  purchaseMembership,
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
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import { magnifyingGlass } from "solid-heroicons/solid-mini";

const PlayerSearchDropdown = props => {
  const [searchText, setSearchText] = createSignal("");
  const [selectedTeam, setSelectedTeam] = createSignal("");
  const [selectAll, setSelectAll] = createSignal(false);
  const [checkedPlayers, setCheckedPlayers] = createSignal({});

  const handleSelectAll = e => {
    props.players
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
            <label
              for="default-search"
              class="mb-2 text-sm font-medium text-gray-900 sr-only dark:text-white"
            >
              Search
            </label>
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
              <button
                type="submit"
                class="text-white absolute right-2.5 bottom-2.5 bg-blue-700 hover:bg-blue-800 focus:outline-none font-medium rounded-lg text-sm px-4 py-2 dark:bg-blue-600 dark:hover:bg-blue-700"
              >
                Search
              </button>
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
            <For
              each={props.players.filter(p =>
                playerMatches(p, searchText(), selectedTeam())
              )}
            >
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
                          {player.teams.map(team => team["name"]).join(", ")} (
                          {player.city})
                        </div>
                      </div>
                    </label>
                  </div>
                </li>
              )}
            </For>
          </ul>
        </div>
      </div>
    </>
  );
};

const GroupMembership = () => {
  const [store, { setLoggedIn, setData, setPlayerById }] = useStore();

  const [status, setStatus] = createSignal();

  const years = membershipYearOptions();
  const [year, setYear] = createSignal(years?.[0]);
  const [startDate, setStartDate] = createSignal("");
  const [endDate, setEndDate] = createSignal("");

  const [players, setPlayers] = createSignal([]);
  const [teams, setTeams] = createSignal([]);
  const [payingPlayers, setPayingPlayers] = createSignal([]);
  const [paymentSuccess, setPaymentSuccess] = createSignal(false);

  const playersSuccessHandler = async response => {
    const data = await response.json();
    if (response.ok) {
      setPlayers(data);
    } else {
      console.log(data);
    }
  };

  const fetchPlayers = () => {
    console.log("Fetching players info...");
    fetchUrl("/api/players", playersSuccessHandler, error =>
      console.log(error)
    );
  };

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

  onMount(() => {
    initFlowbite();
    if (!store.loggedIn) {
      fetchUserData(setLoggedIn, setData);
    }
    fetchPlayers();
    fetchTeams();
  });

  let rzpScript;
  onMount(() => {
    rzpScript = document.createElement("script");
    rzpScript.src = "https://checkout.razorpay.com/v1/checkout.js";
    rzpScript.async = true;
    document.body.appendChild(rzpScript);
  });
  onCleanup(() => {
    if (rzpScript && document.body.contains(rzpScript)) {
      document.body.removeChild(rzpScript);
      document
        .querySelectorAll(".razorpay-container")
        .forEach(el => document.body.removeChild(el));
    }
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

  const paymentSuccessCallback = () => {
    fetchPlayers();
    setPaymentSuccess(true);
  };

  const triggerPurchase = () => {
    const data = {
      player_ids: payingPlayers().map(p => p.id),
      year: year()
    };
    purchaseMembership(data, setStatus, setPlayerById, paymentSuccessCallback);
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

  return (
    <div>
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
            players={players()}
            teams={teams()}
            payingPlayers={payingPlayers()}
            onPlayerChecked={handlePlayerChecked}
          />
        </Show>
        <MembershipPlayerList
          players={payingPlayers()}
          fee={
            payingPlayers().reduce(
              (acc, player) =>
                acc +
                (player?.sponsored
                  ? sponsoredAnnualMembershipFee
                  : annualMembershipFee),
              0
            ) / 100
          }
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
              <button
                class={`my-2 text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 ${
                  payDisabled() ? "cursor-not-allowed" : ""
                } `}
                onClick={triggerPurchase}
                disabled={payDisabled()}
              >
                Pay
              </button>
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
