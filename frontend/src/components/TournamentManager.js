import { useStore } from "../store";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import {
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
  updateSeeding
} from "../queries";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";
import { createStore } from "solid-js/store";

const TournamentManager = () => {
  const queryClient = useQueryClient();
  const [store] = useStore();
  const [event, setEvent] = createSignal(0);
  const [selectedTeams, setSelectedTeams] = createSignal([]);
  const [selectedTournament, setSelectedTournament] = createSignal(0);
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

  createEffect(() => {
    if (tournamentsQuery.status === "success") {
      const tournament = tournamentsQuery.data?.filter(
        t => t.id === selectedTournament()
      )[0];
      const seeding = tournament?.initial_seeding;

      if (seeding) setTournamentSeeding(seeding);
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

  const eventsQuery = createQuery(() => ["events"], fetchEvents);
  const teamsQuery = createQuery(() => ["teams"], fetchTeams);
  const tournamentsQuery = createQuery(() => ["tournaments"], fetchTournaments);
  const poolsQuery = createQuery(
    () => ["pools", selectedTournament()],
    () => fetchPools(selectedTournament())
  );
  const crossPoolQuery = createQuery(
    () => ["cross-pool", selectedTournament()],
    () => fetchCrossPool(selectedTournament())
  );
  const bracketQuery = createQuery(
    () => ["brackets", selectedTournament()],
    () => fetchBrackets(selectedTournament())
  );
  const postionPoolsQuery = createQuery(
    () => ["position-pools", selectedTournament()],
    () => fetchPositionPools(selectedTournament())
  );
  const matchesQuery = createQuery(
    () => ["matches", selectedTournament()],
    () => fetchMatches(selectedTournament())
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
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["pools", selectedTournament()]
      })
  });

  const createCrossPoolMutation = createMutation({
    mutationFn: createCrossPool,
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["cross-pool", selectedTournament()]
      })
  });

  const createBracketMutation = createMutation({
    mutationFn: createBracket,
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["brackets", selectedTournament()]
      })
  });

  const createPositionPoolMutation = createMutation({
    mutationFn: createPositionPool,
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["position-pools", selectedTournament()]
      })
  });

  const createMatchMutation = createMutation({
    mutationFn: createMatch,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["matches", selectedTournament()]
      });
    }
  });

  return (
    <Show when={store?.data?.is_staff} fallback={<p>Not Authorised!</p>}>
      <div>
        <h1 class="text-center font-bold text-2xl text-blue-500">
          New Tournament
        </h1>
        <label
          htmlFor="events"
          className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
        >
          Select an Event
        </label>
        <select
          id="events"
          onChange={e => setEvent(parseInt(e.target.value))}
          className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
        >
          <option value={0} selected>
            Choose an event
          </option>
          <For each={eventsQuery.data}>
            {e => <option value={e.id}>{e.title}</option>}
          </For>
        </select>
        <div className="grid grid-cols-4 gap-4 my-5">
          <For each={teamsQuery.data}>
            {t => (
              <div className="flex items-center pl-4 border border-gray-200 rounded dark:border-gray-700">
                <input
                  id={"team-" + t.id}
                  type="checkbox"
                  value={t.id}
                  onChange={e =>
                    e.target.checked
                      ? setSelectedTeams([
                          ...selectedTeams().filter(
                            t => t !== parseInt(e.target.value)
                          ),
                          parseInt(e.target.value)
                        ])
                      : setSelectedTeams(
                          selectedTeams().filter(
                            t => t !== parseInt(e.target.value)
                          )
                        )
                  }
                  className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
                />
                <label
                  htmlFor={"team-" + t.id}
                  className="w-full py-4 ml-2 text-sm font-medium text-gray-900 dark:text-gray-300"
                >
                  {t.name}
                </label>
              </div>
            )}
          </For>
        </div>
        <button
          type="button"
          onClick={() =>
            createTournamentMutation.mutate({
              event_id: event(),
              team_ids: selectedTeams()
            })
          }
          className="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700"
        >
          Create Tournament
        </button>
      </div>
      <hr className="h-px my-8 bg-gray-200 border-0 dark:bg-gray-700" />
      <div>
        <h1 class="text-center font-bold text-2xl text-blue-500 mb-5">
          Existing Tournaments
        </h1>
        <select
          id="tournaments"
          onChange={e => setSelectedTournament(parseInt(e.target.value))}
          className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
        >
          <option value={0} selected>
            Choose a tournament
          </option>
          <For each={tournamentsQuery.data}>
            {t => <option value={t.id}>{t.event.title}</option>}
          </For>
        </select>

        <Show when={selectedTournament() > 0}>
          <div className="relative overflow-x-auto my-5">
            <table className="w-full text-sm text-left text-gray-500 dark:text-gray-400">
              <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th scope="col" className="px-6 py-3">
                    Seeding
                  </th>
                  <th scope="col" className="px-6 py-3">
                    Team Name
                  </th>
                  <th scope="col" className="px-6 py-3">
                    Team ID
                  </th>
                </tr>
              </thead>
              <tbody>
                <For each={Object.keys(tournamentSeeding())}>
                  {seed => (
                    <tr className="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                      <th
                        scope="row"
                        className="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                      >
                        {seed}
                      </th>
                      <td className="px-6 py-4">
                        {teamsMap()[tournamentSeeding()[seed]]}
                      </td>
                      <td className="px-6 py-4">{tournamentSeeding()[seed]}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>

            <label
              htmlFor="message"
              className="block mb-2 text-sm font-medium text-gray-900 dark:text-white mt-5"
            >
              Raw Seeding JSON
            </label>
            <textarea
              id="message"
              rows="4"
              className="block p-2.5 w-full text-sm text-gray-900 bg-gray-50 rounded-lg border border-gray-300 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-5"
              placeholder="Seeding JSON Here..."
              onChange={e => setTournamentSeeding(JSON.parse(e.target.value))}
            >
              {JSON.stringify(tournamentSeeding())}
            </textarea>
            <button
              type="button"
              onClick={() =>
                updateSeedingMutation.mutate({
                  id: selectedTournament(),
                  body: { seeding: tournamentSeeding() }
                })
              }
              className="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700"
            >
              Update Seeding
            </button>
            <button
              type="button"
              onClick={() =>
                deleteTournamentMutation.mutate({
                  id: selectedTournament()
                })
              }
              className="text-white bg-red-700 hover:bg-red-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-red-600 dark:hover:bg-red-700"
            >
              Delete Tournament
            </button>
          </div>
          <div>
            <h2 className="text-blue-500 text-xl font-bold mb-5">Pools</h2>
            <Show
              when={!poolsQuery.data?.message}
              fallback={<p>Select Tournament to see/add Pools</p>}
            >
              <div className="grid grid-cols-3 gap-4">
                <For each={poolsQuery.data}>
                  {pool => (
                    <div>
                      <h3>Pool - {pool.name}</h3>{" "}
                      <div className="relative overflow-x-auto">
                        <table className="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                          <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                            <tr>
                              <th scope="col" className="px-6 py-3">
                                Seeding
                              </th>
                              <th scope="col" className="px-6 py-3">
                                Team Name
                              </th>
                              <th scope="col" className="px-6 py-3">
                                Team ID
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            <For each={Object.keys(pool.initial_seeding)}>
                              {seed => (
                                <tr className="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                                  <th
                                    scope="row"
                                    className="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                                  >
                                    {seed}
                                  </th>
                                  <td className="px-6 py-4">
                                    {teamsMap()[pool.initial_seeding[seed]]}
                                  </td>
                                  <td className="px-6 py-4">
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
                <div className="border border-blue-600 rounded-lg p-5">
                  <h3>Add New Pool</h3>
                  <div>
                    <label
                      htmlFor="pool-name"
                      className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Pool Name
                    </label>
                    <input
                      type="text"
                      id="pool-name"
                      value={enteredPoolName()}
                      onChange={e => setEnteredPoolName(e.target.value)}
                      className="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="seedings-pool"
                      className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Seedings List
                    </label>
                    <input
                      type="text"
                      id="seedings-pool"
                      value={enteredSeedingList()}
                      onChange={e => setEnteredSeedingList(e.target.value)}
                      className="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      createPoolMutation.mutate({
                        tournament_id: selectedTournament(),
                        name: enteredPoolName(),
                        seq_num: poolsQuery.data.length + 1,
                        seeding_list: enteredSeedingList()
                      })
                    }
                    className="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700"
                  >
                    Create Pool
                  </button>
                </div>
              </div>
            </Show>
          </div>
          <div>
            <h3 className="text-blue-500 text-xl font-bold my-5">Cross Pool</h3>
            <Show
              when={crossPoolQuery.data?.message}
              fallback={<p>Cross Pool is Enabled for this Tournament</p>}
            >
              <p>{crossPoolQuery.data?.message}</p>
              <button
                type="button"
                onClick={() =>
                  createCrossPoolMutation.mutate({
                    tournament_id: selectedTournament()
                  })
                }
                className="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700"
              >
                Create Cross Pool
              </button>
            </Show>
          </div>
          <div>
            <h2 className="text-blue-500 text-xl font-bold my-5">Brackets</h2>
            <Show
              when={!bracketQuery.data?.message}
              fallback={<p>Select Tournament to see/add Bracket</p>}
            >
              <div className="grid grid-cols-3 gap-4">
                <For each={bracketQuery.data}>
                  {bracket => (
                    <div>
                      <h3>Bracket - {bracket.name}</h3>{" "}
                      <div className="relative overflow-x-auto">
                        <table className="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                          <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                            <tr>
                              <th scope="col" className="px-6 py-3">
                                Seeds in Bracket
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            <For each={Object.keys(bracket.initial_seeding)}>
                              {seed => (
                                <tr className="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                                  <th
                                    scope="row"
                                    className="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
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
                <div className="border border-blue-600 rounded-lg p-5">
                  <h3>Add New Bracket</h3>
                  <div>
                    <label
                      htmlFor="bracket-name"
                      className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Bracket Name
                    </label>
                    <input
                      type="text"
                      id="bracket-name"
                      value={enteredBracketName()}
                      onChange={e => setEnteredBracketName(e.target.value)}
                      className="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      createBracketMutation.mutate({
                        tournament_id: selectedTournament(),
                        name: enteredBracketName(),
                        seq_num: bracketQuery.data.length + 1
                      })
                    }
                    className="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700"
                  >
                    Create Bracket
                  </button>
                </div>
              </div>
            </Show>
          </div>
          <div>
            <h2 className="text-blue-500 text-xl font-bold my-5">
              Position Pools
            </h2>
            <Show
              when={!postionPoolsQuery.data?.message}
              fallback={<p>Select Tournament to see/add Position Pools</p>}
            >
              <div className="grid grid-cols-3 gap-4">
                <For each={postionPoolsQuery.data}>
                  {pool => (
                    <div>
                      <h3>Position Pool - {pool.name}</h3>{" "}
                      <div className="relative overflow-x-auto">
                        <table className="w-full text-sm text-left text-gray-500 dark:text-gray-400">
                          <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                            <tr>
                              <th scope="col" className="px-6 py-3">
                                Seeding
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            <For each={Object.keys(pool.initial_seeding)}>
                              {seed => (
                                <tr className="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                                  <th
                                    scope="row"
                                    className="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
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
                <div className="border border-blue-600 rounded-lg p-5">
                  <h3>Add New Positon Pool</h3>
                  <div>
                    <label
                      htmlFor="position-pool-name"
                      className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Pool Name
                    </label>
                    <input
                      type="text"
                      id="position-pool-name"
                      value={enteredPositionPoolName()}
                      onChange={e => setEnteredPositionPoolName(e.target.value)}
                      className="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="seedings-position-pool"
                      className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
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
                      className="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      createPositionPoolMutation.mutate({
                        tournament_id: selectedTournament(),
                        name: enteredPositionPoolName(),
                        seq_num: postionPoolsQuery.data.length + 1,
                        seeding_list: enteredPositionPoolSeedingList()
                      })
                    }
                    className="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700"
                  >
                    Create Position Pool
                  </button>
                </div>
              </div>
            </Show>
          </div>
          <div>
            <h3 className="text-blue-500 text-xl font-bold my-5">Matches</h3>
            <Show
              when={!matchesQuery.data?.message}
              fallback={<p>Select Tournament to see/add Matches</p>}
            >
              <div className="w-1/2">
                <div>
                  <label
                    htmlFor="match-stage"
                    className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Select Match Stage
                  </label>
                  <select
                    id="match-stage"
                    onChange={e => setMatchFields("stage", e.target.value)}
                    className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
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
                      htmlFor="match-stage-id"
                      className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Select Pool/Bracket/Cross-Pool
                    </label>
                    <select
                      id="match-stage-id"
                      onChange={e => setMatchFields("stage_id", e.target.value)}
                      className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
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
                    htmlFor="match-seq-num"
                    className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Sequence Number
                  </label>
                  <input
                    type="number"
                    id="match-seq-num"
                    onChange={e => setMatchFields("seq_num", e.target.value)}
                    className="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  />
                </div>
                <div>
                  <label
                    htmlFor="match-time"
                    className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Date & Time
                  </label>
                  <input
                    type="datetime-local"
                    id="match-time"
                    onChange={e => setMatchFields("time", e.target.value)}
                    min={
                      tournamentsQuery.data?.filter(
                        t => t.id === selectedTournament()
                      )[0]?.event?.start_date + "T00:00"
                    }
                    max={
                      tournamentsQuery.data?.filter(
                        t => t.id === selectedTournament()
                      )[0]?.event?.end_date + "T23:59"
                    }
                    class="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:placeholder-white dark:border-gray-600 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  />
                </div>
                <div>
                  <label
                    htmlFor="match-field"
                    className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Select Field
                  </label>
                  <select
                    id="match-field"
                    onChange={e => setMatchFields("field", e.target.value)}
                    className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  >
                    <option selected>Choose a stage</option>
                    <option value="Field 1">Field 1</option>
                    <option value="Field 2">Field 2</option>
                    <option value="Field 3">Field 3</option>
                    <option value="Field 4">Field 4</option>
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="match-seed-1"
                    className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Team 1 - Seed Number
                  </label>
                  <input
                    type="number"
                    id="match-seed-1"
                    onChange={e => setMatchFields("seed_1", e.target.value)}
                    className="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  />
                </div>
                <div>
                  <label
                    htmlFor="match-seed-2"
                    className="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Team 2 - Seed Number
                  </label>
                  <input
                    type="number"
                    id="match-seed-2"
                    onChange={e => setMatchFields("seed_2", e.target.value)}
                    className="block w-full p-2 text-gray-900 border border-gray-300 rounded-lg bg-gray-50 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500 mb-3"
                  />
                </div>
                <button
                  type="button"
                  onClick={() =>
                    createMatchMutation.mutate({
                      tournament_id: selectedTournament(),
                      body: matchFields
                    })
                  }
                  className="text-white bg-blue-700 hover:bg-blue-800 font-medium rounded-lg text-sm px-5 py-2.5 mr-2 mb-2 dark:bg-blue-600 dark:hover:bg-blue-700 mb-5"
                >
                  Add Match
                </button>
              </div>
            </Show>
            <table className="w-full text-sm text-left text-gray-500 dark:text-gray-400">
              <thead className="text-xs text-gray-700 uppercase bg-gray-50 dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th scope="col" className="px-6 py-3">
                    Teams
                  </th>
                  <th scope="col" className="px-6 py-3">
                    Stage
                  </th>
                  <th scope="col" className="px-6 py-3">
                    Date & Time
                  </th>
                  <th scope="col" className="px-6 py-3">
                    Field
                  </th>
                </tr>
              </thead>
              <tbody>
                <For each={matchesQuery.data}>
                  {match => (
                    <tr className="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                      <th
                        scope="row"
                        className="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                      >
                        {match.placeholder_seed_1 +
                          " vs " +
                          match.placeholder_seed_2}
                      </th>
                      <td className="px-6 py-4">Pool</td>
                      <td className="px-6 py-4">{match.time}</td>
                      <td className="px-6 py-4">{match.field}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
        </Show>
      </div>
    </Show>
  );
};

export default TournamentManager;
