import { createSignal, Show } from "solid-js";

import { useStore } from "../store";
import ContactForm from "./ContactForm";

const HelpButton = () => {
  const [isOpen, setIsOpen] = createSignal(false);
  const [store] = useStore();

  const toggleOpen = () => setIsOpen(!isOpen());

  return (
    <Show when={store?.userFetched && store?.data?.username}>
      <div class="fixed bottom-0 right-4">
        <button
          class="focus:shadow-outline rounded-full bg-purple-500 px-4 py-2 font-bold text-white hover:bg-purple-700 focus:outline-none"
          onClick={toggleOpen}
        >
          ? Help
        </button>
        {isOpen() && (
          <div class="absolute bottom-16 right-0 w-96 rounded-lg border border-purple-400 bg-white p-4 shadow dark:bg-gray-900">
            <ContactForm close={() => setIsOpen(false)} />
          </div>
        )}
      </div>
    </Show>
  );
};

export default HelpButton;
