import clsx from "clsx";
import { Icon } from "solid-heroicons";
import { chevronUp } from "solid-heroicons/solid";
import { createSignal } from "solid-js";

const ScrollUpButton = () => {
  const [visible, setVisible] = createSignal(false);

  const toggleVisible = () => {
    const scrolled = document.documentElement.scrollTop;
    if (scrolled > 300) {
      setVisible(true);
    } else if (scrolled <= 300) {
      setVisible(false);
    }
  };

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: "smooth"
    });
  };

  window.addEventListener("scroll", toggleVisible);

  return (
    <button
      type="button"
      onClick={scrollToTop}
      class={clsx(
        visible() ? "visible opacity-100" : "invisible opacity-0",
        "fixed bottom-6 right-4 me-2 inline-flex items-center rounded-full bg-blue-700 p-2 text-center text-sm font-medium text-white transition-all duration-300 ease-in-out hover:bg-blue-800 focus:outline-none dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 md:bottom-10 md:right-8"
      )}
    >
      <svg
        class="h-8 w-8 stroke-2"
        aria-hidden="true"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 14 10"
      >
        <Icon class="mx-1 h-8 w-8 stroke-2" path={chevronUp} />
      </svg>
      <span class="sr-only">Scroll to Top</span>
    </button>
  );
};

export default ScrollUpButton;
