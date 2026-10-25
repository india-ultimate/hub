import { useParams } from "@solidjs/router";
import clsx from "clsx";
import { createSignal, For, Match, Show, Switch } from "solid-js";

import { usePrefetchPlayer } from "../../../playerLinks";
import QuickLook from "../../player-profile/QuickLook";

const PlayerButton = props => {
  const prefetch = usePrefetchPlayer();
  const warm = () => prefetch(props.player.slug);
  return (
    <Show when={props.player?.slug} fallback={props.player?.full_name}>
      <button
        type="button"
        class="-mx-1 -my-1.5 touch-manipulation px-1 py-1.5 underline decoration-dotted decoration-2 underline-offset-4 hover:decoration-solid focus-visible:rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
        classList={{ "font-bold": props.bold }}
        aria-haspopup="dialog"
        onPointerEnter={warm}
        onFocus={warm}
        onTouchStart={warm}
        onClick={() => props.onOpen(props.player)}
      >
        {props.player.full_name}
      </button>
    </Show>
  );
};

const EventTitle = props => {
  return (
    <Switch>
      <Match when={props.event?.type === "LS"}>
        <Show when={props.event?.started_on === "OF"} fallback="D-Line">
          O-Line
        </Show>
      </Match>
      <Match when={props.event?.type === "SC"}>
        Score {props.event?.post_event_score_team_1} -{" "}
        {props.event?.post_event_score_team_2}
      </Match>
      <Match when={props.event?.type === "DR"}>Drop</Match>
      <Match when={props.event?.type === "TA"}>Throwaway</Match>
      <Match when={props.event?.type === "BL"}>Block</Match>
    </Switch>
  );
};

const EventDescription = props => {
  const open = player => props.onOpen(player);
  return (
    <Switch>
      <Match when={props.event?.type === "LS"}>
        <For each={props.event?.players}>
          {(p, i) => (
            <>
              {i() > 0 && ", "}
              <PlayerButton player={p} onOpen={open} />
            </>
          )}
        </For>
      </Match>
      <Match when={props.event?.type === "SC"}>
        <PlayerButton player={props.event?.assisted_by} onOpen={open} bold /> to{" "}
        <PlayerButton player={props.event?.scored_by} onOpen={open} bold />
      </Match>
      <Match when={props.event?.type === "DR"}>
        <PlayerButton player={props.event?.drop_by} onOpen={open} />
      </Match>
      <Match when={props.event?.type === "TA"}>
        <PlayerButton player={props.event?.throwaway_by} onOpen={open} />
      </Match>
      <Match when={props.event?.type === "BL"}>
        <PlayerButton player={props.event?.block_by} onOpen={open} />
      </Match>
    </Switch>
  );
};

const EventsDisplay = props => {
  const params = useParams();
  const [player, setPlayer] = createSignal();
  let lookRef;
  const open = p => {
    setPlayer(p);
    lookRef.showModal();
  };
  const thisMatch = () => {
    const events = props.stats?.events ?? [];
    const count = key =>
      events.filter(e => player() && e[key]?.id === player().id).length;
    return {
      goals: count("scored_by"),
      assists: count("assisted_by"),
      blocks: count("block_by")
    };
  };
  const from = () => ({
    label: `${props.match?.team_1?.name} vs ${props.match?.team_2?.name}`,
    tournamentSlug: params.tournamentSlug
  });

  return (
    <>
      <div class="grid w-full grid-cols-12 gap-x-0 gap-y-4">
        <For each={props.stats?.events}>
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
                        "flex w-full justify-between font-bold",
                        event.type === "SC" ? "text-white" : "text-blue-600"
                      )}
                    >
                      <span>
                        <EventTitle event={event} />
                      </span>
                      <span class="text-sm font-normal italic">
                        {new Date(event.time).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit"
                        })}
                      </span>
                    </h2>
                    <p
                      class={clsx(
                        "w-full text-sm leading-8",
                        event.type === "SC" ? "text-blue-50" : "text-blue-700"
                      )}
                    >
                      <EventDescription event={event} onOpen={open} />
                    </p>
                  </div>
                </div>
              </Match>
              <Match when={event.team.id === props.match?.team_2?.id}>
                <div
                  class={clsx(
                    "col-span-8 col-start-5 rounded-lg p-4",
                    event.type === "SC" ? "bg-green-600" : "bg-green-50"
                  )}
                >
                  <div class="flex flex-wrap justify-end">
                    <h2
                      class={clsx(
                        "flex w-full justify-between text-right font-bold",
                        event.type === "SC" ? "text-white" : "text-green-600"
                      )}
                    >
                      <span class="text-sm font-normal italic">
                        {new Date(event.time).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit"
                        })}
                      </span>
                      <span>
                        <EventTitle event={event} />
                      </span>
                    </h2>
                    <p
                      class={clsx(
                        "w-full text-right text-sm leading-8",
                        event.type === "SC" ? "text-green-50" : "text-green-700"
                      )}
                    >
                      <EventDescription event={event} onOpen={open} />
                    </p>
                  </div>
                </div>
              </Match>
            </Switch>
          )}
        </For>
      </div>
      <QuickLook
        ref={lookRef}
        player={player()}
        match={thisMatch()}
        from={from()}
      />
    </>
  );
};

export default EventsDisplay;
