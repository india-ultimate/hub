import { useDragDropContext } from "@thisbeyond/solid-dnd";
import {
  DragDropProvider,
  DragDropSensors,
  DragOverlay,
  SortableProvider,
  createSortable,
  closestCenter
} from "@thisbeyond/solid-dnd";
import { createSignal, For } from "solid-js";

const TeamInfo = props => (
  <div class="p-2 text-start flex gap-4 cursor-grab">
    <div class="basis-1/6 text-center text-white dark:text-white-400 rounded-xl border-b bg-green-400 border-green-200 dark:bg-green-800 dark:border-green-700">
      {props.teamSeed + 1}
    </div>
    <div class="basis-5/6">{props.teamName}</div>
  </div>
);

const Sortable = props => {
  const sortable = createSortable(props.teamId);
  const [state] = useDragDropContext();
  return (
    <div
      use:sortable
      class="sortable text-gray-500 dark:text-gray-400 my-2 rounded-lg bg-gray-200 border-gray-300 border-b dark:bg-gray-800 dark:border-gray-700"
      classList={{
        "opacity-25": sortable.isActiveDraggable,
        "transition-transform": !!state.active.draggable
      }}
    >
      <TeamInfo
        teamSeed={props.teamSeed}
        teamName={props.teamsMap[props.teamId]}
      />
    </div>
  );
};

/**
 * @param {object} props
 * @param {int[]} props.teams
 * @param {callback} props.updateTeamSeeding
 */
const ReorderTeams = props => {
  const [activeItem, setActiveItem] = createSignal(null);

  const onDragStart = ({ draggable }) => setActiveItem(draggable.id);

  const onDragEnd = ({ draggable, droppable }) => {
    if (draggable && droppable) {
      const currentItems = props.teams;
      const fromIndex = currentItems.indexOf(draggable.id);
      const toIndex = currentItems.indexOf(droppable.id);
      if (fromIndex !== toIndex) {
        const updatedItems = currentItems.slice();
        updatedItems.splice(toIndex, 0, ...updatedItems.splice(fromIndex, 1));
        props.updateTeamSeeding(updatedItems);
      }
    }
  };

  return (
    <DragDropProvider
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      collisionDetector={closestCenter}
    >
      <DragDropSensors />
      <div
        class="column self-stretch transition-opacity"
        classList={{
          "opacity-30": props.disabled
        }}
      >
        <SortableProvider ids={props.teams}>
          <For each={props.teams}>
            {(teamId, seed) => (
              <Sortable
                teamSeed={seed()}
                teamId={teamId}
                teamsMap={props.teamsMap}
              />
            )}
          </For>
        </SortableProvider>
      </div>
      <DragOverlay>
        <div class="sortable text-gray-500 dark:text-gray-400 my-2 rounded-lg bg-white border-b dark:bg-gray-700 dark:border-gray-600">
          <TeamInfo
            teamName={props.teamsMap[activeItem()]}
            teamSeed={props.teams.indexOf(activeItem())}
          />
        </div>
      </DragOverlay>
    </DragDropProvider>
  );
};

export default ReorderTeams;
