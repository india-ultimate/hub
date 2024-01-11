import { Icon } from "solid-heroicons";
import { questionMarkCircle } from "solid-heroicons/solid";
import { createSignal, Show } from "solid-js";

import { useStore } from "../store";
import ContactForm from "./ContactForm";

const HelpButton = () => {
  const [isOpen, setIsOpen] = createSignal(false);
  const [store] = useStore();

  const toggleOpen = () => setIsOpen(!isOpen());

  return (
    <Show when={store?.userFetched && store?.data?.username}>
      <button
        class="fixed bottom-6 right-4 me-2 inline-flex items-center rounded-full bg-blue-700 p-2 text-center text-sm font-medium text-white transition-all duration-300 ease-in-out hover:bg-blue-800 focus:outline-none md:bottom-6 md:right-8 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
        onClick={toggleOpen}
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
        <span class="sr-only">Help</span>
      </button>
      {isOpen() && (
        <div class="fixed bottom-20 right-4 w-80 rounded-lg border border-blue-400 bg-white p-4 shadow md:right-8 md:w-96 dark:bg-gray-900">
          <ContactForm close={() => setIsOpen(false)} />
        </div>
      )}
    </Show>
  );
};

export default HelpButton;
