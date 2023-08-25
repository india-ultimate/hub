import { useStore } from "../store";
import { createSignal, createEffect, onCleanup, onMount, For } from "solid-js";
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
  sponsoredAnnualMembershipFee
} from "../constants";
import MembershipPlayerList from "./MembershipPlayerList";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import { chevronDown, magnifyingGlass } from "solid-heroicons/solid-mini";

const PlayerSearchDropdown = props => {
  const [searchText, setSearchText] = createSignal("");

  return (
    <>
      <button
        id="playerSearchButton"
        data-dropdown-toggle="playerSearch"
        data-dropdown-placement="bottom"
        class="text-white mt-5 bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 mb-5 text-center inline-flex items-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
        type="button"
      >
        Select Players
        <Icon path={chevronDown} style={{ width: "24px" }} />
      </button>
      <div
        id="playerSearch"
        class="z-10 hidden bg-white rounded-lg shadow w-60 dark:bg-gray-700"
      >
        <div class="p-3">
          <label for="input-group-search" class="sr-only">
            Search
          </label>
          <div class="relative">
            <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
              <Icon path={magnifyingGlass} style={{ width: "24px" }} />
            </div>
            <input
              type="text"
              id="input-group-search"
              class="block w-full p-2 pl-10 text-sm text-gray-900 border border-gray-300 rounded-lg bg-gray-50 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-600 dark:border-gray-500 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder="Search player"
              onChange={e => setSearchText(e.target.value)}
            />
          </div>
        </div>
        <ul
          class="h-48 px-3 pb-3 overflow-y-auto text-sm text-gray-700 dark:text-gray-200"
          aria-labelledby="playerSearchButton"
        >
          <For
            each={
              searchText()
                ? props.players.filter(p => playerMatches(p, searchText()))
                : props.players
            }
          >
            {player => (
              <li>
                <div class="flex items-center pl-2 rounded hover:bg-gray-100 dark:hover:bg-gray-600">
                  <input
                    id={`checkbox-item-${player.id}`}
                    type="checkbox"
                    class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-700 dark:focus:ring-offset-gray-700 focus:ring-2 dark:bg-gray-600 dark:border-gray-500"
                    onChange={e => props.onPlayerChecked(e, player)}
                    checked={player.has_membership}
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
                        {player.team_name} ({player.city})
                      </div>
                    </div>
                  </label>
                </div>
              </li>
            )}
          </For>
        </ul>
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
  const [payingPlayers, setPayingPlayers] = createSignal([]);

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

  onMount(() => {
    initFlowbite();
    if (!store.loggedIn) {
      fetchUserData(setLoggedIn, setData);
    }
    fetchPlayers();
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
    if (e.target.checked) {
      // Add player to paying Players
      setPayingPlayers([...payingPlayers(), player]);
    } else {
      // Remove player from paying Players
      setPayingPlayers(payingPlayers().filter(p => p.id !== player.id));
    }
  };

  const triggerPurchase = () => {
    const data = {
      player_ids: payingPlayers().map(p => p.id),
      year: year()
    };
    purchaseMembership(data, setStatus, setPlayerById, fetchPlayers);
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
        <PlayerSearchDropdown
          players={players()}
          onPlayerChecked={handlePlayerChecked}
        />
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
        <div>
          <button
            class={`my-2 text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 ${
              payDisabled() ? "cursor-not-allowed" : ""
            } `}
            onClick={triggerPurchase}
            disabled={payDisabled()}
          >
            Pay
          </button>
        </div>
      </div>
      <p>{status()}</p>
    </div>
  );
};

export default GroupMembership;
