import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { questionMarkCircle } from "solid-heroicons/solid";
import { Show } from "solid-js";

import { useStore } from "../store";

const HelpButton = () => {
  const [store] = useStore();

  return (
    <Show when={store?.userFetched && store?.data?.username}>
      <A
        href="/tickets"
        class="fixed bottom-6 right-4 me-2 inline-flex items-center rounded-full bg-blue-700 p-2 text-center text-sm font-medium text-white transition-all duration-300 ease-in-out hover:bg-blue-800 focus:outline-none dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 md:bottom-6 md:right-8"
        title="Access Help Center"
      >
        <svg
          class="h-8 w-8 stroke-2"
          aria-hidden="true"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 14 10"
        >
          <Icon class="mx-1 h-8 w-8 stroke-2" path={questionMarkCircle} />
        </svg>
        <span class="sr-only">Help Center</span>
      </A>
    </Show>
  );
};

export default HelpButton;
