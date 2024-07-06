import { Icon } from "solid-heroicons";
import { pencil } from "solid-heroicons/solid";

const EditRosteredPlayer = () => {
  return (
    <div>
      <button class="rounded-md px-1 text-yellow-400 outline outline-2 outline-yellow-300">
        <Icon path={pencil} class="inline h-4 w-4" />
        <span class="sr-only">Remove from roster</span>
      </button>
    </div>
  );
};

export default EditRosteredPlayer;
