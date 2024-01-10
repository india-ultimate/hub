import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { rocketLaunch } from "solid-heroicons/solid";
import { Show } from "solid-js";

const AnnouncementBanner = props => {
  return (
    <div
      id="sticky-banner"
      tabIndex="-1"
      class="flex w-full justify-between bg-blue-600 p-4 dark:border-gray-600"
    >
      <div class="mx-auto flex items-center">
        <p class="flex items-center text-sm font-normal text-white">
          <span class="me-3 inline-flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-white p-1">
            <Icon path={rocketLaunch} class="h-4 w-4 text-blue-600" />
            <span class="sr-only">Announcement</span>
          </span>
          <span>{props.text}</span>
        </p>
      </div>
      <Show when={props.cta}>
        <div class="flex items-center">
          <A
            class="me-2 rounded border border-white px-2.5 py-0.5 text-xs font-medium uppercase text-white"
            href={props.cta?.href}
          >
            {props.cta?.text}
          </A>
        </div>
      </Show>
    </div>
  );
};

export default AnnouncementBanner;
