import { Icon } from "solid-heroicons";
import { mapPin } from "solid-heroicons/solid";
import { Show } from "solid-js";

import Initials from "../player-profile/Initials";

const chip =
  "inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-gray-700 dark:bg-gray-700 dark:text-gray-300";

const plural = (n, word) => (n === 1 ? word : `${word}s`);

const TeamHero = props => {
  const team = () => props.team;
  const logo = () => team().image || team().image_url;
  const place = () => [team().city, team().state].filter(Boolean).join(", ");
  const games = () => team().record?.played;
  const count = () => team().tournaments.length;
  return (
    <div class="rounded-2xl border border-gray-200 bg-gradient-to-br from-blue-50 via-white to-green-50 p-5 text-center shadow-sm dark:border-gray-700 dark:from-gray-800 dark:via-gray-800 dark:to-gray-800 md:flex md:items-center md:gap-8 md:p-6 md:text-left">
      <Show
        when={logo()}
        fallback={
          <Initials
            name={team().name}
            class="mx-auto h-24 w-24 rounded-full text-3xl ring-2 ring-gray-300 dark:ring-blue-500 md:mx-0 md:h-32 md:w-32 md:text-4xl"
          />
        }
      >
        <img
          src={logo()}
          alt=""
          width="128"
          height="128"
          class="mx-auto h-24 w-24 flex-none rounded-full bg-white object-cover ring-2 ring-gray-300 dark:ring-blue-500 md:mx-0 md:h-32 md:w-32"
        />
      </Show>
      <div class="min-w-0 md:flex-1">
        <h1 class="mt-3 break-words bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-3xl font-extrabold text-transparent md:mt-0 md:text-4xl">
          {team().name}
        </h1>
        <div class="mt-2 flex flex-wrap justify-center gap-2 text-xs md:justify-start">
          <Show when={team().category}>
            <span class={chip}>{team().category}</span>
          </Show>
          <Show when={place()}>
            <span class={chip}>
              <Icon class="h-3 w-3" path={mapPin} />
              {place()}
            </span>
          </Show>
        </div>
        <Show when={count()}>
          <p class="mt-4 text-sm text-gray-600 dark:text-gray-300 md:mt-3">
            <b class="text-gray-900 dark:text-white">{count()}</b>{" "}
            {plural(count(), "tournament")}
            <Show when={games()}>
              {" "}
              · <b class="text-gray-900 dark:text-white">{games()}</b>{" "}
              {plural(games(), "game")}
            </Show>
          </p>
        </Show>
        <Show when={props.isAdmin}>
          <div class="mt-4 flex flex-wrap justify-center gap-2 md:justify-start">
            {props.actions}
          </div>
        </Show>
      </div>
    </div>
  );
};

export default TeamHero;
