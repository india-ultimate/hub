import { Icon } from "solid-heroicons";
import { xMark } from "solid-heroicons/solid";

const RemoveFromRoster = () => {
  return (
    <div>
      <button class="rounded-md text-red-400 outline outline-2 outline-red-300">
        <Icon path={xMark} class="inline h-6 w-6" />
        <span class="sr-only">Remove from roster</span>
      </button>
    </div>
  );
};

export default RemoveFromRoster;
