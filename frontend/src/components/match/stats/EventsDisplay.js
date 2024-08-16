import clsx from "clsx";
import { For, Match, Show, Switch } from "solid-js";

const EventTitle = props => {
  return (
    <Switch>
      <Match when={props.event?.type === "LS"}>
        <Show when={props.event?.started_on === "OF"} fallback="D-Line">
          O-Line
        </Show>
      </Match>
      <Match when={props.event?.type === "SC"}>Score</Match>
      <Match when={props.event?.type === "DR"}>Drop</Match>
      <Match when={props.event?.type === "TA"}>Throwaway</Match>
      <Match when={props.event?.type === "BL"}>Block</Match>
    </Switch>
  );
};

const EventDescription = props => {
  return (
    <Switch>
      <Match when={props.event?.type === "LS"}>
        {props.event?.players?.map(p => p.full_name).join(", ")}
      </Match>
      <Match when={props.event?.type === "SC"}>
        <span class="font-bold">{props.event?.assisted_by?.full_name}</span> to{" "}
        <span class="font-bold">{props.event?.scored_by?.full_name}</span>
      </Match>
      <Match when={props.event?.type === "DR"}>
        {props.event?.drop_by?.full_name}
      </Match>
      <Match when={props.event?.type === "TA"}>
        {props.event?.throwaway_by?.full_name}
      </Match>
      <Match when={props.event?.type === "BL"}>
        {props.event?.block_by?.full_name}
      </Match>
    </Switch>
  );
};

const EventsDisplay = props => {
  return (
    <div class="grid w-full grid-cols-12 gap-x-0 gap-y-4">
      <For each={props.match?.stats?.events}>
        {event => (
          <Switch>
            <Match when={event.team.id === props.match?.team_1?.id}>
              <div
                class={clsx(
                  "col-span-8 rounded-lg p-4",
                  event.type === "SC" ? "bg-blue-600" : "bg-blue-50"
                )}
              >
                <div class="flex flex-wrap justify-start">
                  <h2
                    class={clsx(
                      "w-full font-bold",
                      event.type === "SC" ? "text-white" : "text-blue-600"
                    )}
                  >
                    <EventTitle event={event} />
                  </h2>
                  <p
                    class={clsx(
                      "w-full text-sm",
                      event.type === "SC" ? "text-blue-50" : "text-blue-500"
                    )}
                  >
                    <EventDescription event={event} />
                  </p>
                </div>
              </div>
            </Match>
            <Match when={event.team.id === props.match?.team_2?.id}>
              <div
                class={clsx(
                  "col-span-8 col-start-5  rounded-lg p-4",
                  event.type === "SC" ? "bg-green-600" : "bg-green-50"
                )}
              >
                <div class="flex flex-wrap justify-end">
                  <h2
                    class={clsx(
                      "w-full text-right font-bold",
                      event.type === "SC" ? "text-white" : "text-green-600"
                    )}
                  >
                    <EventTitle event={event} />
                  </h2>
                  <p
                    class={clsx(
                      "w-full text-right text-sm",
                      event.type === "SC" ? "text-green-50" : "text-green-500"
                    )}
                  >
                    <EventDescription event={event} />
                  </p>
                </div>
              </div>
            </Match>
          </Switch>
        )}
      </For>
    </div>
  );
};

export default EventsDisplay;
