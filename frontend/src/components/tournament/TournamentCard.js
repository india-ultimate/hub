import { A } from "@solidjs/router";
import { Match, Show, Switch } from "solid-js";

const TournamentCard = props => {
  return (
    <Show when={props.tournament.status !== "DFT"}>
      <A
        href={
          props.tournament.status === "REG" || props.tournament.status === "SCH"
            ? `/tournament/${props.tournament.event?.slug}/register`
            : `/tournament/${props.tournament.event?.slug}`
        }
        class="block w-full rounded-lg border border-blue-600 bg-white p-4 shadow dark:border-blue-400 dark:bg-gray-800"
      >
        <Show when={props.tournament.event?.type}>
          <span class="mr-2 h-fit rounded bg-blue-200 px-2.5 py-0.5 text-sm font-medium text-blue-800 dark:bg-green-900 dark:text-green-300">
            <Switch>
              <Match when={props.tournament.event?.type === "MXD"}>Mixed</Match>
              <Match when={props.tournament.event?.type === "OPN"}>Opens</Match>
              <Match when={props.tournament.event?.type === "WMN"}>
                Womens
              </Match>
            </Switch>
          </span>
        </Show>

        <Switch>
          <Match when={props.tournament.status === "REG"}>
            <span class="h-fit rounded bg-green-200 px-2.5 py-0.5 text-sm font-medium text-green-800 dark:bg-green-900 dark:text-green-300">
              Registrations open
            </span>
          </Match>
          <Match when={props.tournament.status === "SCH"}>
            <span class="h-fit rounded bg-yellow-100 px-2.5 py-0.5 text-sm font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
              Registrations closed
            </span>
          </Match>
          <Match when={props.tournament.status === "LIV"}>
            <span
              class={clsx(
                "h-fit rounded px-2.5 py-0.5 text-sm font-medium",
                new Date(Date.now()) < Date.parse(props.tournament.start_date)
                  ? "bg-blue-200 text-blue-800 dark:bg-blue-900 dark:text-blue-300"
                  : "bg-red-200 text-red-800 dark:bg-red-900 dark:text-red-300"
              )}
            >
              {new Date(Date.now()) < Date.parse(props.tournament.start_date)
                ? "Upcoming"
                : "Live"}
            </span>
          </Match>
          <Match when={props.tournament.status === "COM"}>
            <span class="h-fit rounded bg-gray-300 px-2.5 py-0.5 text-sm font-medium text-gray-700 dark:bg-gray-900 dark:text-gray-300">
              Completed
            </span>
          </Match>
        </Switch>
        <div class="mb-2 mt-2">
          <h5 class="text-xl font-bold capitalize tracking-tight text-blue-600 dark:text-blue-400">
            {props.tournament.event.title}
          </h5>
          <Show when={props.tournament.event?.series}>
            <p class="text-sm italic">
              Part of{" "}
              <span class="text-blue-600">
                {props.tournament.event?.series?.name}
              </span>
            </p>
          </Show>
        </div>

        <div class="flex justify-between">
          <span class="flex-grow text-sm capitalize">
            {props.tournament.event.location}
          </span>
        </div>
        <p class="text-sm text-blue-600 dark:text-blue-400">
          {new Date(
            Date.parse(props.tournament.event.start_date)
          ).toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
            timeZone: "UTC"
          })}
          <Show
            when={
              props.tournament.event.start_date !==
              props.tournament.event.end_date
            }
          >
            {" "}
            to{" "}
            {new Date(
              Date.parse(props.tournament.event.end_date)
            ).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
              timeZone: "UTC"
            })}
          </Show>
        </p>
        {props.children}
      </A>
    </Show>
  );
};

export default TournamentCard;
