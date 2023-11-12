import { createEffect, createSignal, Match, Show, Switch } from "solid-js";

const colors = {
  pool: ["blue", "green", "pink", "purple"],
  cross_pool: ["yellow", "red", "fuchsia"],
  bracket: [
    ["cyan", "indigo", "sky"],
    ["cyan", "indigo", "sky"],
    ["cyan", "indigo", "sky"]
  ],
  position_pool: ["lime", "pink", "emerald"]
};

const MatchCard = props => {
  const [color, setColor] = createSignal("blue");

  createEffect(() => {
    if (props.match.pool) {
      setColor(colors["pool"][props.match.pool.sequence_number - 1]);
    } else if (props.match.cross_pool) {
      setColor(colors["cross_pool"][props.match.sequence_number - 1]);
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

  const handleMatchCardClick = matchId => {
    const resultCard = document.getElementById(matchId);
    if (resultCard) {
      resultCard.scrollIntoView({
        behavior: "smooth",
        block: "center"
      });
      if (props.setFlash) {
        props.setFlash(matchId);
        setTimeout(() => {
          props.setFlash(-1);
        }, 1500);
      }
    }
  };

  const renderBadge = () => {
    return (
      <Switch>
        <Match when={props.match.pool}>
          <div
            class={`w-full flex justify-center flex-wrap bg-${color()}-100 text-${color()}-800 text-xs font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-${color()}-900 dark:text-${color()}-300`}
          >
            <h6 class="text-center w-full">Pool {props.match.pool.name}</h6>
            <Show when={props.showSeed}>
              <h6 class="text-center">
                {props.match.placeholder_seed_1 +
                  " vs " +
                  props.match.placeholder_seed_2}
              </h6>
            </Show>
          </div>
        </Match>
        <Match when={props.match.cross_pool}>
          <div
            class={`w-full flex justify-center flex-wrap bg-${color()}-100 text-${color()}-800 text-xs font-medium px-2.5 py-0.5 rounded dark:bg-${color()}-900 dark:text-${color()}-300`}
          >
            <h6 class="text-center w-full">CP</h6>
            <Show when={props.showSeed}>
              <h6 class="text-center">
                {props.match.placeholder_seed_1 +
                  " vs " +
                  props.match.placeholder_seed_2}
              </h6>
            </Show>
          </div>
        </Match>
        <Match when={props.match.bracket}>
          <div
            class={`w-full flex justify-center flex-wrap bg-${color()}-100 text-${color()}-800 text-xs font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-${color()}-900 dark:text-${color()}-300`}
          >
            <h6 class="text-center w-full">B {props.match.bracket.name}</h6>
            <Show when={props.showSeed}>
              <h6 class="text-center">
                {props.match.placeholder_seed_1 +
                  " vs " +
                  props.match.placeholder_seed_2}
              </h6>
            </Show>
          </div>
        </Match>
        <Match when={props.match.position_pool}>
          <div
            class={`w-full flex justify-center flex-wrap bg-${color()}-100 text-${color()}-800 text-xs font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-${color()}-900 dark:text-${color()}-300`}
          >
            <h6 class="text-center w-full">
              Pos. Pool {props.match.position_pool.name}
            </h6>
            <Show when={props.showSeed}>
              <h6 class="text-center">
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

  return (
    <Show when={props.setFlash} fallback={renderBadge()}>
      <button
        class="w-full"
        onClick={() => {
          handleMatchCardClick(props.match.id);
        }}
      >
        {renderBadge()}
      </button>
    </Show>
  );
};

export default MatchCard;
