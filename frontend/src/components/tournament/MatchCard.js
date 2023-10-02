import { createEffect, createSignal, Match, Show, Switch } from "solid-js";

const colors = {
  pool: ["blue", "green", "pink", "purple"],
  cross_pool: "yellow",
  bracket: [
    ["cyan", "indigo", "sky"],
    ["cyan", "indigo", "sky"],
    ["cyan", "indigo", "sky"]
  ],
  position_pool: ["lime"]
};

const MatchCard = props => {
  const [color, setColor] = createSignal("blue");

  createEffect(() => {
    if (props.match.pool) {
      setColor(colors["pool"][props.match.pool.sequence_number - 1]);
    } else if (props.match.cross_pool) {
      setColor(colors["cross_pool"]);
    } else if (props.match.bracket) {
      setColor(
        colors["bracket"][props.match.bracket.sequence_number - 1][
          props.match.sequence_number - 1
        ]
      );
    } else if (props.match.position_pool) {
      setColor(
        colors["position_pool"][props.match.position_pool.sequence_number - 1]
      );
    }
  });

  return (
    <Switch>
      <Match when={props.match.pool}>
        <div
          class={`flex justify-center flex-wrap bg-${color()}-100 text-${color()}-800 text-sm font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-${color()}-900 dark:text-${color()}-300`}
        >
          <h6 class="text-center w-full">Pool {props.match.pool.name}</h6>
          <Show when={props.showSeed}>
            <h6 className="text-center">
              {props.match.placeholder_seed_1 +
                " vs " +
                props.match.placeholder_seed_2}
            </h6>
          </Show>
        </div>
      </Match>
      <Match when={props.match.cross_pool}>
        <div
          className={`flex justify-center flex-wrap bg-${color()}-100 text-${color()}-800 text-sm font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-${color()}-900 dark:text-${color()}-300`}
        >
          <h6 className="text-center w-full">Cross Pool</h6>
          <Show when={props.showSeed}>
            <h6 className="text-center">
              {props.match.placeholder_seed_1 +
                " vs " +
                props.match.placeholder_seed_2}
            </h6>
          </Show>
        </div>
      </Match>
      <Match when={props.match.bracket}>
        <div
          class={`flex justify-center flex-wrap bg-${color()}-100 text-${color()}-800 text-sm font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-${color()}-900 dark:text-${color()}-300`}
        >
          <h6 class="text-center w-full">Bracket {props.match.bracket.name}</h6>
          <Show when={props.showSeed}>
            <h6 className="text-center">
              {props.match.placeholder_seed_1 +
                " vs " +
                props.match.placeholder_seed_2}
            </h6>
          </Show>
        </div>
      </Match>
      <Match when={props.match.position_pool}>
        <div
          class={`flex justify-center flex-wrap bg-${color()}-100 text-${color()}-800 text-sm font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-${color()}-900 dark:text-${color()}-300`}
        >
          <h6 class="text-center w-full">
            Position Pool {props.match.position_pool.name}
          </h6>
          <Show when={props.showSeed}>
            <h6 className="text-center">
              {props.match.placeholder_seed_1 +
                " vs " +
                props.match.placeholder_seed_2}
            </h6>
          </Show>
        </div>
      </Match>
    </Switch>
  );
};

export default MatchCard;
