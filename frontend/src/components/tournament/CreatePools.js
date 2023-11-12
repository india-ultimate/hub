import {
  DragDropProvider,
  DragDropSensors,
  createDraggable,
  createDroppable,
  closestCenter
} from "@thisbeyond/solid-dnd";
import { For, batch, createSignal, Show } from "solid-js";

const remainingTeamsName = "Remaining";

/**
 * @param {object} props
 * @param {object} props.team
 * @param {int} props.team.seed
 * @param {str} props.team.name
 * @returns
 */
const TeamInfo = props => (
  <div class="p-2 text-start flex gap-4 cursor-grab text-sm">
    <div class="basis-1/6 text-center text-white dark:text-white-400 rounded-xl border-b bg-green-400 border-green-200 dark:bg-green-800 dark:border-green-700">
      {props.team.seed}
    </div>
    <div class="basis-5/6">{props.team.name}</div>
  </div>
);

/**
 * @param {object} props
 * @param {{seed: int, name: str}} props.team
 */
const Draggable = props => {
  const draggable = createDraggable(props.team.seed);
  return (
    <div
      use:draggable
      class="text-gray-500 dark:text-gray-400 my-2 rounded-lg bg-gray-200 border-gray-300 border-b dark:bg-gray-800 dark:border-gray-700"
    >
      <TeamInfo team={props.team} />
    </div>
  );
};

/**
 *
 * @param {object} props
 * @param {str} props.id
 * @param {str} props.name
 * @param {{seed: int, name: str}[]} props.teams
 */
const Droppable = props => {
  const droppable = createDroppable(props.id);
  return (
    <>
      <div
        use:droppable
        class="flex flex-col justify-items-center justify-start gap-y-2 content-center h-full p-4 rounded-lg dark:text-gray-400 bg-white text-center select-none border dark:border-gray-700"
        classList={{
          "ring-4 ring-blue-500": droppable.isActiveDroppable,
          "justify-between dark:bg-gray-700": props.id !== remainingTeamsName,
          "dark:bg-gray-900": props.id === remainingTeamsName
        }}
      >
        {/* bg-gray-200 dark:bg-gray-700 border-b dark:border-gray-600 rounded-b-xl */}
        <h4 class="text-center text-white p-2 justify-self-start">
          <Show when={props.id !== remainingTeamsName} fallback={"All teams"}>
            Pool - {props.name}
          </Show>
        </h4>
        <div class="">
          <For each={props.teams}>{team => <Draggable team={team} />}</For>
        </div>
        <Show when={props.id !== remainingTeamsName}>
          <button
            class="justify-self-end p-2 text-sm font-normal text-white rounded-lg bg-red-700 hover:bg-red-800 dark:bg-red-500/75 dark:hover:bg-red-700/75"
            onClick={() => props.removePool(props.id)}
          >
            Remove pool
          </button>
        </Show>
      </div>
    </>
  );
};

const CreatePools = props => {
  console.log("called created pools");
  const [enteredPoolName, setEnteredPoolName] = createSignal("");
  const [draggedTeam, setDraggedTeam] = createSignal({});
  const [draggableStartPool, setDraggableStartPool] = createSignal("");

  const onDragStart = ({ draggable }) => {
    if (draggable) {
      for (const [poolName, teams] of Object.entries(props.pools)) {
        const teamIdx = teams.findIndex(team => team.seed == draggable.id);
        if (teamIdx !== -1) {
          setDraggedTeam(teams[teamIdx]);
          setDraggableStartPool(poolName);
          break;
        }
      }
    }
  };

  const onDragEnd = ({ draggable, droppable }) => {
    if (draggable && droppable) {
      if (draggableStartPool() == droppable.id) {
        return;
      }
      batch(() => {
        props.updatePools(draggableStartPool(), teams =>
          teams.filter(team => team.seed !== draggable.id)
        );
        // its easier to look at the pools if the teams are sorted by seed
        props.updatePools(droppable.id, teams =>
          [...teams, draggedTeam()].sort((a, b) => a.seed - b.seed)
        );
      });
      props.setIsPoolsEdited(true);
    }
  };

  const removePool = droppableId => {
    batch(() => {
      props.updatePools(remainingTeamsName, teams =>
        [...teams, ...props.pools[droppableId]].sort((a, b) => a.seed - b.seed)
      );
      // setting value undefined to delete it from the store
      props.updatePools(droppableId, undefined);
    });
    props.setIsPoolsEdited(true);
  };

  const addPool = poolName => {
    if (!poolName || Object.keys(props.pools).includes(poolName)) {
      return;
    }
    props.updatePools(poolName, []);
  };

  return (
    <>
      <div class="w-1/2 mb-4 flex gap-4 justify-start items-center rounded-md">
        <input
          type="text"
          id="pool-name"
          placeholder="Enter Pool Name"
          value={enteredPoolName()}
          onChange={e => setEnteredPoolName(e.target.value.trim())}
          class="basis-2/3 p-2 placeholder:text-md placeholder:italic text-gray-900 rounded-lg bg-gray-50 border border-gray-300 dark:border-gray-600 sm:text-xs focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
        />
        <button
          type="button"
          onClick={() => {
            addPool(enteredPoolName());
            setEnteredPoolName("");
          }}
          class="basis-1/3 p-2 font-normal text-sm rounded-lg text-white bg-blue-700 hover:bg-blue-800 dark:bg-blue-600 dark:hover:bg-blue-700 disabled:dark:bg-gray-400"
        >
          Add Pool
        </button>
      </div>
      <DragDropProvider
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        collisionDetector={closestCenter}
      >
        <DragDropSensors>
          <div class="w-full grid grid-rows-2 grid-cols-3 grid-flow-row gap-4">
            <div
              class="row-span-2 col-span-1 transition-opacity"
              classList={{ "opacity-30": props.isUpdating }}
            >
              <Droppable
                id={remainingTeamsName}
                name={remainingTeamsName}
                teams={props.pools[remainingTeamsName]}
              />
            </div>

            <For each={Object.entries(props.pools)}>
              {([poolName, teams]) => (
                <Show when={poolName !== remainingTeamsName}>
                  <div
                    class="row-span-1 col-span-1 transition-opacity"
                    classList={{ "opacity-30": props.isUpdating }}
                  >
                    <Droppable
                      id={poolName}
                      name={poolName}
                      teams={teams}
                      removePool={removePool}
                    />
                  </div>
                </Show>
              )}
            </For>
          </div>
        </DragDropSensors>
      </DragDropProvider>
    </>
  );
};

export default CreatePools;
