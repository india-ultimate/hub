import {
  closestCenter,
  createDraggable,
  createDroppable,
  DragDropProvider,
  DragDropSensors
} from "@thisbeyond/solid-dnd";
import { batch, createSignal, For, Show } from "solid-js";

const remainingTeamsName = "Remaining";

/**
 * @param {object} props
 * @param {object} props.team
 * @param {int} props.team.seed
 * @param {str} props.team.name
 * @returns
 */
const TeamInfo = props => (
  <div class="flex cursor-grab gap-4 p-2 text-start text-sm">
    <div class="dark:text-white-400 basis-1/6 rounded-xl border-b border-green-200 bg-green-400 text-center text-white dark:border-green-700 dark:bg-green-800">
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
      class="my-2 rounded-lg border-b border-gray-400 bg-gray-300 text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
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
        class="flex h-full select-none flex-col content-center justify-start justify-items-center gap-y-2 rounded-lg border bg-white p-4 text-center dark:border-gray-700 dark:text-gray-400"
        classList={{
          "ring-4 ring-blue-500": droppable.isActiveDroppable,
          "justify-between bg-gray-200/80 dark:bg-gray-700/80 text-black dark:text-white":
            props.id !== remainingTeamsName,
          "dark:bg-gray-900": props.id === remainingTeamsName
        }}
      >
        {/* bg-gray-200 dark:bg-gray-700 border-b dark:border-gray-600 rounded-b-xl */}
        <h4 class="justify-self-start p-2 text-center">
          <Show when={props.id !== remainingTeamsName} fallback={"All teams"}>
            Pool - {props.name}
          </Show>
        </h4>
        <div class="">
          <For each={props.teams}>{team => <Draggable team={team} />}</For>
        </div>
        <Show when={props.id !== remainingTeamsName}>
          <button
            class="justify-self-end rounded-lg bg-red-700 p-2 text-sm font-normal text-white hover:bg-red-800 dark:bg-red-500/75 dark:hover:bg-red-700/75"
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
    const removingEmptyPool = props.pools[droppableId].length == 0;
    batch(() => {
      props.updatePools(remainingTeamsName, teams =>
        [...teams, ...props.pools[droppableId]].sort((a, b) => a.seed - b.seed)
      );
      // setting value undefined to delete it from the store
      props.updatePools(droppableId, undefined);
    });
    props.setIsPoolsEdited(!removingEmptyPool);
  };

  const addPool = poolName => {
    if (!poolName || Object.keys(props.pools).includes(poolName)) {
      return;
    }
    props.updatePools(poolName, []);
  };

  return (
    <>
      <div class="mb-4 flex w-1/2 items-center justify-start gap-4 rounded-md">
        <input
          type="text"
          id="pool-name"
          placeholder="Enter Pool Name"
          value={enteredPoolName()}
          onChange={e => setEnteredPoolName(e.target.value.trim())}
          class="placeholder:text-md basis-2/3 rounded-lg border border-gray-300 bg-gray-50 p-2 text-gray-900 placeholder:italic focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500 sm:text-xs"
        />
        <button
          type="button"
          onClick={() => {
            addPool(enteredPoolName());
            setEnteredPoolName("");
          }}
          class="basis-1/3 rounded-lg bg-blue-700 p-2 text-sm font-normal text-white hover:bg-blue-800 dark:bg-blue-600 dark:hover:bg-blue-700 disabled:dark:bg-gray-400"
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
          <div class="grid w-full grid-flow-row grid-cols-3 grid-rows-2 gap-4">
            <div
              class="col-span-1 row-span-2 transition-opacity"
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
                    class="col-span-1 row-span-1 transition-opacity"
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
