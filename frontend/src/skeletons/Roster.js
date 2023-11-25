import { For } from "solid-js";
const Player = () => {
  return (
    <div class="my-5 flex animate-pulse justify-start space-x-2 px-6">
      <div class="mr-1 h-10 w-10 rounded-full p-1 ring-2 ring-gray-300 dark:ring-gray-500" />
      <div class="h-2.5 w-28 self-center rounded-full bg-gray-200 dark:bg-gray-700" />
      <div class="h-2.5 w-20  self-center rounded-full bg-gray-200 dark:bg-gray-700" />
    </div>
  );
};

const Roster = () => {
  return (
    <For each={new Array(15)}>
      {/* eslint-disable-next-line no-unused-vars */}
      {num => <Player />}
    </For>
  );
};

export default Roster;
