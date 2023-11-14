import { useDragDropContext } from "@thisbeyond/solid-dnd";
import {
  closestCenter,
  createSortable,
  DragDropProvider,
  DragDropSensors,
  DragOverlay,
  SortableProvider
} from "@thisbeyond/solid-dnd";
import { createSignal, For } from "solid-js";

const TeamInfo = props => (
  <div class="flex cursor-grab gap-4 p-2 text-start">
    <div class="dark:text-white-400 basis-1/6 rounded-xl border-b border-green-200 bg-green-400 text-center text-white dark:border-green-700 dark:bg-green-800">
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
      class="sortable my-2 rounded-lg border-b border-gray-300 bg-gray-200 text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
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
        props.setIsStandingsEdited(true);
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
        <div class="sortable my-2 rounded-lg border-b bg-white text-gray-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-400">
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
