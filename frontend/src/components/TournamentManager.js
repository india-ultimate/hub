import { useStore } from "../store";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import {
  addMatchScore,
  createBracket,
  createCrossPool,
  createMatch,
  createPool,
  createPositionPool,
  createTournament,
  deleteTournament,
  fetchBrackets,
  fetchCrossPool,
  fetchEvents,
  fetchMatches,
  fetchPools,
  fetchPositionPools,
  fetchTeams,
  fetchTournaments,
  generateTournamentFixtures,
  startTournament,
  updateMatch,
  updateSeeding
} from "../queries";
import {
  createEffect,
  createSignal,
  For,
  Match,
  onMount,
  Show,
  Switch
} from "solid-js";
import { createStore, reconcile } from "solid-js/store";
import MatchCard from "./tournament/MatchCard";

const TournamentManager = () => {
  const queryClient = useQueryClient();
  const [store] = useStore();
  const [event, setEvent] = createSignal(0);
  const [selectedTournament, setSelectedTournament] = createSignal();
  const [selectedTournamentID, setSelectedTournamentID] = createSignal(0);
  const [tournamentSeeding, setTournamentSeeding] = createSignal([]);
  const [teamsMap, setTeamsMap] = createSignal({});
  const [enteredPoolName, setEnteredPoolName] = createSignal("");
  const [enteredSeedingList, setEnteredSeedingList] = createSignal("[]");
  const [enteredBracketName, setEnteredBracketName] = createSignal("1-8");
  const [enteredPositionPoolName, setEnteredPositionPoolName] =
    createSignal("");
  const [enteredPositionPoolSeedingList, setEnteredPositionPoolSeedingList] =
    createSignal("[]");
  const [matchFields, setMatchFields] = createStore();
  const [matchScoreFields, setMatchStoreFields] = createStore();
  const [matchDayTimeFieldMap, setMatchDayTimeFieldMap] = createStore({});
  const [fieldMap, setFieldMap] = createStore({});
  const [datesList, setDatesList] = createSignal([]);
  const [timesList, setTimesList] = createSignal([]);
  const [updateMatchFields, setUpdateMatchFields] = createStore();

  onMount(() => {
    const dt = new Date(1970, 0, 1, 6, 0);
    let newTimesList = [];
    while (dt.getHours() < 22) {
      newTimesList.push(
        dt.toLocaleTimeString("en-US", { hour: "numeric", minute: "numeric" })
      );
      dt.setMinutes(dt.getMinutes() + 15);
    }
    setTimesList(newTimesList);
  });

  createEffect(() => {
    if (tournamentsQuery.status === "success") {
      const tournament = tournamentsQuery.data?.filter(
        t => t.id === selectedTournamentID()
      )[0];
      setSelectedTournament(tournament);
      const seeding = tournament?.initial_seeding;

      if (seeding) setTournamentSeeding(seeding);

      let newDatesList = [];
      for (
        let d = new Date(Date.parse(tournament?.event?.start_date));
        d <= new Date(Date.parse(tournament?.event?.end_date));
        d.setDate(d.getDate() + 1)
      ) {
        newDatesList.push(new Date(d));
      }
      setDatesList(newDatesList);
    }
  });

  createEffect(() => {
    if (teamsQuery.status === "success") {
      let newTeamsMap = {};
      teamsQuery.data.map(team => {
        newTeamsMap[team.id] = team.name;
      });
      setTeamsMap(newTeamsMap);
    }
  });

  createEffect(() => {
    if (matchesQuery.status === "success" && !matchesQuery.data?.message) {
      setMatchDayTimeFieldMap(reconcile({}));
      setFieldMap(reconcile({}));
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
          const time = new Date(Date.parse(match.time));
          setMatchDayTimeFieldMap(day, {});
          setMatchDayTimeFieldMap(day, time, {});
          setMatchDayTimeFieldMap(day, time, match.field, match);

          setFieldMap(day, {});
          setFieldMap(day, match.field, true);
        }
      });

      console.log(matchDayTimeFieldMap);
    }
  });

  const eventsQuery = createQuery(() => ["events"], fetchEvents);
  const teamsQuery = createQuery(() => ["teams"], fetchTeams);
  const tournamentsQuery = createQuery(() => ["tournaments"], fetchTournaments);
  const poolsQuery = createQuery(
    () => ["pools", selectedTournamentID()],
    () => fetchPools(selectedTournamentID())
  );
  const crossPoolQuery = createQuery(
    () => ["cross-pool", selectedTournamentID()],
    () => fetchCrossPool(selectedTournamentID())
  );
  const bracketQuery = createQuery(
    () => ["brackets", selectedTournamentID()],
    () => fetchBrackets(selectedTournamentID())
  );
  const postionPoolsQuery = createQuery(
    () => ["position-pools", selectedTournamentID()],
    () => fetchPositionPools(selectedTournamentID())
  );
  const matchesQuery = createQuery(
    () => ["matches", selectedTournamentID()],
    () => fetchMatches(selectedTournamentID())
  );

  const createTournamentMutation = createMutation({
    mutationFn: createTournament,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournaments"] })
  });

  const updateSeedingMutation = createMutation({
    mutationFn: updateSeeding,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournaments"] })
  });

  const deleteTournamentMutation = createMutation({
    mutationFn: deleteTournament,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["tournaments"] })
  });

  const createPoolMutation = createMutation({
    mutationFn: createPool,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["pools", selectedTournamentID()]
      });
      queryClient.invalidateQueries({
        queryKey: ["matches", selectedTournamentID()]
      });
    }
  });

  const createCrossPoolMutation = createMutation({
    mutationFn: createCrossPool,
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["cross-pool", selectedTournamentID()]
      })
  });

  const createBracketMutation = createMutation({
    mutationFn: createBracket,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["brackets", selectedTournamentID()]
      });
      queryClient.invalidateQueries({
        queryKey: ["matches", selectedTournamentID()]
      });
    }
  });

  const createPositionPoolMutation = createMutation({
    mutationFn: createPositionPool,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["position-pools", selectedTournamentID()]
      });
      queryClient.invalidateQueries({
        queryKey: ["matches", selectedTournamentID()]
      });
    }
  });

  const createMatchMutation = createMutation({
    mutationFn: createMatch,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["matches", selectedTournamentID()]
      });
    }
  });

  const updateMatchMutation = createMutation({
    mutationFn: updateMatch,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["matches", selectedTournamentID()]
      });
    }
  });

  const startTournamentMutation = createMutation({
    mutationFn: startTournament,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["tournaments"]
      });
      queryClient.invalidateQueries({
        queryKey: ["matches", selectedTournamentID()]
      });
    }
  });

  const generateTournamentFixturesMutation = createMutation({
    mutationFn: generateTournamentFixtures,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["matches", selectedTournamentID()]
      });
    }
  });

  const addMatchScoreMutation = createMutation({
    mutationFn: addMatchScore,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["matches", selectedTournamentID()]
      });
    }
  });

  Date.prototype.yyyymmdd = function () {
    var mm = this.getMonth() + 1; // getMonth() is zero-based
    var dd = this.getDate();

    return [
      this.getFullYear(),
      (mm > 9 ? "" : "0") + mm,
      (dd > 9 ? "" : "0") + dd
    ].join("-");
  };

  const convertTime12to24 = time12h => {
    const [time, modifier] = time12h.split(" ");

    let [hours, minutes] = time.split(":");

    if (hours === "12") {
      hours = "00";
    }

    if (modifier === "PM") {
      hours = parseInt(hours, 10) + 12;
    }

    return `${hours}:${minutes}`;
  };

  return (
    <Show when={store?.data?.is_staff} fallback={<p>Not Authorised!</p>}>
      <div>
        <h1 class="text-center font-bold text-2xl text-blue-500">
          New Tournament
        </h1>
        <label
          for="events"
          class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
        >
          Select an Event
        </label>
        <select
          id="events"
          onChange={e => setEvent(parseInt(e.target.value))}
          class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
        >
          <option value={0} selected>
            Choose an event
          </option>
          <For each={eventsQuery.data}>
            {e => <option value={e.id}>{e.title}</option>}
          </For>
        </select>
        {/*<div class="grid grid-cols-4 gap-4 my-5">*/}
        {/*  <For each={teamsQuery.data}>*/}
        {/*    {t => (*/}
        {/*      <div class="flex items-center pl-4 border border-gray-200 rounded dark:border-gray-700">*/}
        {/*        <input*/}
        {/*          id={"team-" + t.id}*/}
        {/*          type="checkbox"*/}
        {/*          value={t.id}*/}
        {/*          onChange={e =>*/}
        {/*            e.target.checked*/}
        {/*              ? setSelectedTeams([*/}
        {/*                  ...selectedTeams().filter(*/}
        {/*                    t => t !== parseInt(e.target.value)*/}
        {/*                  ),*/}
        {/*                  parseInt(e.target.value)*/}
        {/*                ])*/}
        {/*              : setSelectedTeams(*/}
        {/*                  selectedTeams().filter(*/}
        {/*                    t => t !== parseInt(e.target.value)*/}
        {/*                  )*/}
        {/*                )*/}
        {/*          }*/}
        {/*          class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"*/}
        {/*        />*/}
        {/*        <label*/}
        {/*          for={"team-" + t.id}*/}
        {/*          class="w-full py-4 ml-2 text-sm font-medium text-gray-900 dark:text-gray-300"*/}
        {/*        >*/}
        {/*          {t.name}*/}

        {/*          <img*/}
        {/*            class="w-8 h-8 p-1 rounded-full ring-2 ring-gray-300 dark:ring-gray-500 inline-block ml-3"*/}
        {/*            src={t.image_url}*/}
        {/*            alt="Bordered avatar"*/}
        {/*          />*/}
        {/*        </label>*/}
        {/*      </div>*/}
        {/*    )}*/}
        {/*  </For>*/}
        {/*</div>*/}
        <button
          type="button"
          onClick={() =>
            createTournamentMutation.mutate({
              event_id: event()
            })
          }
          class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 my-5"
        >
          Create Tournament
        </button>
      </div>
      <hr class="h-px my-8 bg-gray-200 border-0 dark:bg-gray-700" />
      <div>
        <h1 class="text-center font-bold text-2xl text-blue-500 mb-5">
          Existing Tournaments
        </h1>
        <select
          id="tournaments"
          onChange={e => setSelectedTournamentID(parseInt(e.target.value))}
          class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
        >
          <option value={0} selected>
            Choose a tournament
          </option>
          <For each={tournamentsQuery.data}>
            {t => <option value={t.id}>{t.event.title}</option>}
          </For>
        </select>

        <Show when={selectedTournamentID() > 0 && selectedTournament()}>
          <div class="relative overflow-x-auto my-5">
            <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
              <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th scope="col" class="px-6 py-3">
                    Seeding
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Team Name
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Team ID
                  </th>
                </tr>
              </thead>
              <tbody>
                <For each={Object.keys(tournamentSeeding())}>
                  {seed => (
                    <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                      <th
                        scope="row"
                        class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                      >
                        {seed}
                      </th>
                      <td class="px-6 py-4">
                        {teamsMap()[tournamentSeeding()[seed]]}
                      </td>
                      <td class="px-6 py-4">{tournamentSeeding()[seed]}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>

            <label
              for="message"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white mt-5"
            >
              Raw Seeding JSON
            </label>
            <textarea
              id="message"
              rows="4"
              class="block p-2.5 w-full text-sm text-gray-900 bg-gray-50 rounded-lg border border-gray-300 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-5"
              placeholder="Seeding JSON Here..."
              onChange={e => setTournamentSeeding(JSON.parse(e.target.value))}
            >
              {JSON.stringify(tournamentSeeding())}
            </textarea>
            <button
              type="button"
              onClick={() =>
                updateSeedingMutation.mutate({
                  id: selectedTournamentID(),
                  body: { seeding: tournamentSeeding() }
                })
              }
              disabled={selectedTournament()?.status !== "DFT"}
              class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 disabled:dark:bg-gray-400"
            >
              Update Seeding
            </button>
            <button
              type="button"
              onClick={() =>
                deleteTournamentMutation.mutate({
                  id: selectedTournamentID()
                })
              }
              class="text-white bg-red-700 hover:bg-red-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-red-600 dark:hover:bg-red-700"
            >
              Delete Tournament
            </button>
          </div>
          <div>
            <h2 class="text-blue-500 text-xl font-bold mb-5">Pools</h2>
            <Show
              when={!poolsQuery.data?.message}
              fallback={<p>Select Tournament to see/add Pools</p>}
            >
              <div class="grid grid-cols-3 gap-4">
                <For each={poolsQuery.data}>
                  {pool => (
                    <div>
                      <h3>Pool - {pool.name}</h3>{" "}
                      <div class="relative overflow-x-auto">
                        <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                          <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                            <tr>
                              <th scope="col" class="px-6 py-3">
                                Seeding
                              </th>
                              <th scope="col" class="px-6 py-3">
                                Team Name
                              </th>
                              <th scope="col" class="px-6 py-3">
                                Team ID
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            <For each={Object.keys(pool.initial_seeding)}>
                              {seed => (
                                <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                                  <th
                                    scope="row"
                                    class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                                  >
                                    {seed}
                                  </th>
                                  <td class="px-6 py-4">
                                    {teamsMap()[pool.initial_seeding[seed]]}
                                  </td>
                                  <td class="px-6 py-4">
                                    {pool.initial_seeding[seed]}
                                  </td>
                                </tr>
                              )}
                            </For>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </For>
                <div class="border border-blue-600 rounded-lg p-5">
                  <h3>Add New Pool</h3>
                  <div>
                    <label
                      for="pool-name"
                      class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Pool Name
                    </label>
                    <input
                      type="text"
                      id="pool-name"
                      value={enteredPoolName()}
                      onChange={e => setEnteredPoolName(e.target.value)}
                      class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label
                      for="seedings-pool"
                      class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Seedings List
                    </label>
                    <input
                      type="text"
                      id="seedings-pool"
                      value={enteredSeedingList()}
                      onChange={e => setEnteredSeedingList(e.target.value)}
                      class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      createPoolMutation.mutate({
                        tournament_id: selectedTournamentID(),
                        name: enteredPoolName(),
                        seq_num: poolsQuery.data.length + 1,
                        seeding_list: enteredSeedingList()
                      })
                    }
                    disabled={selectedTournament()?.status !== "DFT"}
                    class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 disabled:dark:bg-gray-400 mt-5"
                  >
                    Create Pool
                  </button>
                </div>
              </div>
            </Show>
          </div>
          <div>
            <h3 class="text-blue-500 text-xl font-bold my-5">Cross Pool</h3>
            <Show
              when={crossPoolQuery.data?.message}
              fallback={<p>Cross Pool is Enabled for this Tournament</p>}
            >
              <p>{crossPoolQuery.data?.message}</p>
              <button
                type="button"
                onClick={() =>
                  createCrossPoolMutation.mutate({
                    tournament_id: selectedTournamentID()
                  })
                }
                disabled={selectedTournament()?.status !== "DFT"}
                class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 disabled:dark:bg-gray-400 mt-5"
              >
                Create Cross Pool
              </button>
            </Show>
          </div>
          <div>
            <h2 class="text-blue-500 text-xl font-bold my-5">Brackets</h2>
            <Show
              when={!bracketQuery.data?.message}
              fallback={<p>Select Tournament to see/add Bracket</p>}
            >
              <div class="grid grid-cols-3 gap-4">
                <For each={bracketQuery.data}>
                  {bracket => (
                    <div>
                      <h3>Bracket - {bracket.name}</h3>{" "}
                      <div class="relative overflow-x-auto">
                        <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                          <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                            <tr>
                              <th scope="col" class="px-6 py-3">
                                Seeds in Bracket
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            <For each={Object.keys(bracket.initial_seeding)}>
                              {seed => (
                                <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                                  <th
                                    scope="row"
                                    class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                                  >
                                    {seed}
                                  </th>
                                </tr>
                              )}
                            </For>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </For>
                <div class="border border-blue-600 rounded-lg p-5">
                  <h3>Add New Bracket</h3>
                  <div>
                    <label
                      for="bracket-name"
                      class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Bracket Name
                    </label>
                    <input
                      type="text"
                      id="bracket-name"
                      value={enteredBracketName()}
                      onChange={e => setEnteredBracketName(e.target.value)}
                      class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      createBracketMutation.mutate({
                        tournament_id: selectedTournamentID(),
                        name: enteredBracketName(),
                        seq_num: bracketQuery.data.length + 1
                      })
                    }
                    disabled={selectedTournament()?.status !== "DFT"}
                    class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 disabled:dark:bg-gray-400 mt-5"
                  >
                    Create Bracket
                  </button>
                </div>
              </div>
            </Show>
          </div>
          <div>
            <h2 class="text-blue-500 text-xl font-bold my-5">Position Pools</h2>
            <Show
              when={!postionPoolsQuery.data?.message}
              fallback={<p>Select Tournament to see/add Position Pools</p>}
            >
              <div class="grid grid-cols-3 gap-4">
                <For each={postionPoolsQuery.data}>
                  {pool => (
                    <div>
                      <h3>Position Pool - {pool.name}</h3>{" "}
                      <div class="relative overflow-x-auto">
                        <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                          <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                            <tr>
                              <th scope="col" class="px-6 py-3">
                                Seeding
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            <For each={Object.keys(pool.initial_seeding)}>
                              {seed => (
                                <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                                  <th
                                    scope="row"
                                    class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                                  >
                                    {seed}
                                  </th>
                                </tr>
                              )}
                            </For>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </For>
                <div class="border border-blue-600 rounded-lg p-5">
                  <h3>Add New Positon Pool</h3>
                  <div>
                    <label
                      for="position-pool-name"
                      class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Pool Name
                    </label>
                    <input
                      type="text"
                      id="position-pool-name"
                      value={enteredPositionPoolName()}
                      onChange={e => setEnteredPositionPoolName(e.target.value)}
                      class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label
                      for="seedings-position-pool"
                      class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Seedings List
                    </label>
                    <input
                      type="text"
                      id="seedings-position-pool"
                      value={enteredPositionPoolSeedingList()}
                      onChange={e =>
                        setEnteredPositionPoolSeedingList(e.target.value)
                      }
                      class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      createPositionPoolMutation.mutate({
                        tournament_id: selectedTournamentID(),
                        name: enteredPositionPoolName(),
                        seq_num: postionPoolsQuery.data.length + 1,
                        seeding_list: enteredPositionPoolSeedingList()
                      })
                    }
                    disabled={selectedTournament()?.status !== "DFT"}
                    class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 disabled:dark:bg-gray-400 mt-5"
                  >
                    Create Position Pool
                  </button>
                </div>
              </div>
            </Show>
          </div>
          <div>
            <h3 class="text-blue-500 text-xl font-bold my-5">Matches</h3>
            <Show
              when={!matchesQuery.data?.message}
              fallback={<p>Select Tournament to see/add Matches</p>}
            >
              <div class="w-1/2">
                <div>
                  <label
                    for="match-stage"
                    class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Select Match Stage
                  </label>
                  <select
                    id="match-stage"
                    onChange={e => setMatchFields("stage", e.target.value)}
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  >
                    <option selected>Choose a stage</option>
                    <option value="pool">Pool</option>
                    <option value="cross_pool">Cross Pool</option>
                    <option value="bracket">Bracket</option>
                    <option value="position_pool">Position Pool</option>
                  </select>
                </div>
                <Show when={matchFields["stage"]}>
                  <div>
                    <label
                      for="match-stage-id"
                      class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Select Pool/Bracket/Cross-Pool
                    </label>
                    <select
                      id="match-stage-id"
                      onChange={e => setMatchFields("stage_id", e.target.value)}
                      class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                    >
                      <option selected>Choose a option</option>
                      <Switch>
                        <Match when={matchFields["stage"] === "pool"}>
                          <For each={poolsQuery.data}>
                            {p => <option value={p.id}>Pool - {p.name}</option>}
                          </For>
                        </Match>
                        <Match when={matchFields["stage"] === "bracket"}>
                          <For each={bracketQuery.data}>
                            {b => (
                              <option value={b.id}>Bracket - {b.name}</option>
                            )}
                          </For>
                        </Match>
                        <Match when={matchFields["stage"] === "cross_pool"}>
                          <option value={crossPoolQuery.data.id}>
                            Cross Pool
                          </option>
                        </Match>
                        <Match when={matchFields["stage"] === "position_pool"}>
                          <For each={postionPoolsQuery.data}>
                            {p => (
                              <option value={p.id}>
                                Position Pool - {p.name}
                              </option>
                            )}
                          </For>
                        </Match>
                      </Switch>
                    </select>
                  </div>
                </Show>
                <div>
                  <label
                    for="match-seq-num"
                    class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Sequence Number
                  </label>
                  <input
                    type="number"
                    id="match-seq-num"
                    onChange={e => setMatchFields("seq_num", e.target.value)}
                    class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  />
                </div>
                <div>
                  <label
                    for="match-time"
                    class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Date & Time
                  </label>
                  <input
                    type="datetime-local"
                    id="match-time"
                    onChange={e => setMatchFields("time", e.target.value)}
                    min={selectedTournament()?.event?.start_date + "T00:00"}
                    max={selectedTournament()?.event?.end_date + "T23:59"}
                    class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:placeholder-white dark:border-gray-600 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  />
                </div>
                <div>
                  <label
                    for="match-field"
                    class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Select Field
                  </label>
                  <select
                    id="match-field"
                    onChange={e => setMatchFields("field", e.target.value)}
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  >
                    <option selected>Choose a field</option>
                    <option value="Field 1">Field 1</option>
                    <option value="Field 2">Field 2</option>
                    <option value="Field 3">Field 3</option>
                    <option value="Field 4">Field 4</option>
                  </select>
                </div>
                <div>
                  <label
                    for="match-seed-1"
                    class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Team 1 - Seed Number
                  </label>
                  <input
                    type="number"
                    id="match-seed-1"
                    onChange={e => setMatchFields("seed_1", e.target.value)}
                    class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  />
                </div>
                <div>
                  <label
                    for="match-seed-2"
                    class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Team 2 - Seed Number
                  </label>
                  <input
                    type="number"
                    id="match-seed-2"
                    onChange={e => setMatchFields("seed_2", e.target.value)}
                    class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => {
                    createMatchMutation.mutate({
                      tournament_id: selectedTournamentID(),
                      body: matchFields
                    });
                  }}
                  disabled={selectedTournament()?.status !== "DFT"}
                  class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 mb-5 disabled:dark:bg-gray-400"
                >
                  Add Match
                </button>
              </div>
            </Show>
            <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
              <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th scope="col" class="px-6 py-3">
                    Seeds
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Team 1
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Team 2
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Stage
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Date & Time
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Field
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Score
                  </th>
                </tr>
              </thead>
              <tbody>
                <For each={matchesQuery.data}>
                  {match => (
                    <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                      <th
                        scope="row"
                        class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                      >
                        {match.placeholder_seed_1 +
                          " vs " +
                          match.placeholder_seed_2}
                      </th>
                      <td class="px-6 py-4 text-center">
                        {match.team_1 ? match.team_1.name : "-"}
                        <Show when={match.status === "SCH"}>
                          <label
                            for="match-score-1"
                            class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                          >
                            Score
                          </label>
                          <input
                            type="number"
                            id="match-score-1"
                            onChange={e =>
                              setMatchStoreFields(match.id, {
                                ...matchScoreFields[match.id],
                                team_1_score: parseInt(e.target.value)
                              })
                            }
                            class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                          />
                        </Show>
                      </td>
                      <td class="px-6 py-4 text-center">
                        {match.team_2 ? match.team_2.name : "-"}
                        <Show when={match.status === "SCH"}>
                          <label
                            for="match-score-2"
                            class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                          >
                            Score
                          </label>
                          <input
                            type="number"
                            id="match-score-2"
                            onChange={e =>
                              setMatchStoreFields(match.id, {
                                ...matchScoreFields[match.id],
                                team_2_score: parseInt(e.target.value)
                              })
                            }
                            class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                          />
                        </Show>
                      </td>
                      <td class="px-6 py-4">
                        <MatchCard match={match} />
                      </td>
                      <td class="px-6 py-4 w-fit">
                        {new Date(Date.parse(match.time)).toLocaleDateString(
                          "en-US",
                          {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                            hour: "numeric",
                            minute: "numeric",
                            timeZone: "UTC"
                          }
                        )}
                        <Show when={match.status !== "COM"}>
                          <div class="mt-2">
                            <select
                              onChange={e => {
                                setUpdateMatchFields(match.id, {});
                                setUpdateMatchFields(
                                  match.id,
                                  "date",
                                  e.target.value
                                );
                              }}
                              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-2"
                            >
                              <option selected>Choose new date</option>
                              <For each={datesList()}>
                                {date => (
                                  <option value={date}>
                                    {date.toLocaleDateString("en-US", {
                                      month: "short",
                                      day: "numeric",
                                      timeZone: "UTC"
                                    })}
                                  </option>
                                )}
                              </For>
                            </select>
                            <select
                              onChange={e => {
                                setUpdateMatchFields(match.id, {});
                                setUpdateMatchFields(
                                  match.id,
                                  "time",
                                  e.target.value
                                );
                              }}
                              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                            >
                              <option selected>Choose new time</option>
                              <For each={timesList()}>
                                {time => <option value={time}>{time}</option>}
                              </For>
                            </select>
                          </div>
                        </Show>
                      </td>
                      <td class="px-6 py-4">
                        {match.field}
                        <Show when={match.status !== "COM"}>
                          <select
                            onChange={e => {
                              setUpdateMatchFields(match.id, {});
                              setUpdateMatchFields(
                                match.id,
                                "field",
                                e.target.value
                              );
                            }}
                            class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                          >
                            <option selected>Update Field</option>
                            <option value="Field 1">Field 1</option>
                            <option value="Field 2">Field 2</option>
                            <option value="Field 3">Field 3</option>
                            <option value="Field 4">Field 4</option>
                          </select>
                        </Show>
                      </td>
                      <td class="px-6 py-4">
                        <Switch>
                          <Match when={match.status === "YTF"}>
                            <button
                              type="button"
                              onClick={() => {
                                if (
                                  updateMatchFields[match.id]["date"] &&
                                  updateMatchFields[match.id]["time"] &&
                                  updateMatchFields[match.id]["field"]
                                ) {
                                  const date = new Date(
                                    updateMatchFields[match.id]["date"]
                                  );
                                  updateMatchMutation.mutate({
                                    match_id: match.id,
                                    body: {
                                      time:
                                        date.yyyymmdd() +
                                        "T" +
                                        convertTime12to24(
                                          updateMatchFields[match.id]["time"]
                                        ),
                                      field:
                                        updateMatchFields[match.id]["field"]
                                    }
                                  });
                                }
                              }}
                              class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 mb-5 disabled:dark:bg-gray-400"
                            >
                              Update
                            </button>
                          </Match>
                          <Match when={match.status === "SCH"}>
                            <button
                              type="button"
                              onClick={() => {
                                if (
                                  matchScoreFields[match.id]["team_1_score"] >
                                    0 &&
                                  matchScoreFields[match.id]["team_2_score"] > 0
                                )
                                  addMatchScoreMutation.mutate({
                                    match_id: match.id,
                                    body: matchScoreFields[match.id]
                                  });
                              }}
                              class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 mb-5 disabled:dark:bg-gray-400"
                            >
                              Add Score
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                if (
                                  updateMatchFields[match.id]["date"] &&
                                  updateMatchFields[match.id]["time"] &&
                                  updateMatchFields[match.id]["field"]
                                ) {
                                  const date = new Date(
                                    updateMatchFields[match.id]["date"]
                                  );
                                  updateMatchMutation.mutate({
                                    match_id: match.id,
                                    body: {
                                      time:
                                        date.yyyymmdd() +
                                        "T" +
                                        convertTime12to24(
                                          updateMatchFields[match.id]["time"]
                                        ),
                                      field:
                                        updateMatchFields[match.id]["field"]
                                    }
                                  });
                                }
                              }}
                              class="text-white bg-green-700 hover:bg-green-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-green-600 dark:hover:bg-green-700 mb-5 disabled:dark:bg-gray-400"
                            >
                              Update
                            </button>
                          </Match>
                          <Match when={match.status === "COM"}>
                            {match.score_team_1 + " - " + match.score_team_2}
                          </Match>
                        </Switch>
                      </td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
          <div>
            <For each={Object.keys(matchDayTimeFieldMap).sort()}>
              {day => (
                <div>
                  <h6 class="text-center my-5">Schedule - {day}</h6>
                  <div class="relative overflow-x-auto">
                    <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                      <thead class="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                        <tr>
                          <th scope="col" class="px-6 py-3 text-center">
                            Time
                          </th>
                          <For each={Object.keys(fieldMap[day]).sort()}>
                            {field => (
                              <th scope="col" class="px-6 py-3 text-center">
                                {field}
                              </th>
                            )}
                          </For>
                        </tr>
                      </thead>
                      <tbody>
                        <For
                          each={Object.keys(matchDayTimeFieldMap[day]).sort(
                            (a, b) => new Date(a) - new Date(b)
                          )}
                        >
                          {time => (
                            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                              <th
                                scope="row"
                                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white text-center"
                              >
                                {new Date(time).toLocaleTimeString("en-US", {
                                  hour: "numeric",
                                  minute: "numeric",
                                  timeZone: "UTC"
                                })}
                              </th>
                              <For each={Object.keys(fieldMap[day]).sort()}>
                                {field => (
                                  <td class="px-6 py-4">
                                    <Show
                                      when={
                                        matchDayTimeFieldMap[day][time][field]
                                      }
                                    >
                                      <MatchCard
                                        match={
                                          matchDayTimeFieldMap[day][time][field]
                                        }
                                        showSeed={true}
                                      />
                                    </Show>
                                  </td>
                                )}
                              </For>
                            </tr>
                          )}
                        </For>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </For>
          </div>
          <Switch>
            <Match when={selectedTournament()?.status === "DFT"}>
              <button
                type="button"
                onClick={() =>
                  startTournamentMutation.mutate({
                    tournament_id: selectedTournamentID()
                  })
                }
                class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 my-5"
              >
                Start Tournament
              </button>
            </Match>
            <Match when={selectedTournament()?.status === "LIV"}>
              <button
                type="button"
                onClick={() =>
                  generateTournamentFixturesMutation.mutate({
                    tournament_id: selectedTournamentID()
                  })
                }
                class="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 my-5"
              >
                Populate Fixtures
              </button>
            </Match>
            <Match when={selectedTournament()?.status === "COM"}>
              Completed!!!
            </Match>
          </Switch>
        </Show>
      </div>
    </Show>
  );
};

export default TournamentManager;
