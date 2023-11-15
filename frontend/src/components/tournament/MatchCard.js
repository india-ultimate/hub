import { createEffect, createSignal, Match, Show, Switch } from "solid-js";
import { getMatchCardColor } from "../../utils";

const getSmallName = matchName => {
  if (matchName === "Cross Pool") {
    return "CP";
  }
  if (matchName === "Quarter Finals") {
    return "QF";
  }
  if (matchName === "Semi Finals") {
    return "SF";
  }
  // Bracket matches are named like 5-8 Bracket, 9-12 Bracket
  // On smaller screens show as B 5-8, B 9-12
  const matchBracketPattern = matchName.match(/(\d+-\d+) Bracket/);
  if (matchBracketPattern) {
    return `B ${matchBracketPattern[1]}`;
  }
  // Return same name otherwise (Finals)
  return matchName;
};

const showSeedForBracketMatch = matchName => {
  // Don't show seed for finals or position matches (3rd Place match is 3v4)
  const isFinals = matchName === "Finals";
  const isPositionMatch = matchName?.match(/(\d+)\w{2} Place/) !== null;
  return !(isFinals || isPositionMatch);
};

const MatchName = props => (
  <Show
    when={props.dontMinimiseMatchName}
    fallback={
      <>
        <h6
          class="text-center w-full block sm:hidden"
          classList={{ "py-2": props.extraVerticalPadding }}
        >
          {getSmallName(props.name)}
        </h6>
        <h6
          class="text-center w-full hidden sm:block"
          classList={{ "py-2": props.extraVerticalPadding }}
        >
          {props.name}
        </h6>
      </>
    }
  >
    <h6
      class="text-center w-full"
      classList={{ "py-2": props.extraVerticalPadding }}
    >
      {props.name}
    </h6>
  </Show>
);

const MatchCard = props => {
  const [color, setColor] = createSignal("blue");

  createEffect(() => {
    setColor(props.matchCardColorOverride ?? getMatchCardColor(props.match));
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
            class={`w-full flex justify-center flex-wrap bg-${color()}-100 text-${color()}-800 text-xs font-medium px-2.5 py-0.5 rounded dark:bg-${color()}-900 dark:text-${color()}-300`}
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
        <Match when={props.match.cross_pool || props.match.bracket}>
          <div
            class={`w-full flex justify-center flex-wrap bg-${color()}-100 text-${color()}-800 text-xs font-medium px-2.5 py-0.5 rounded dark:bg-${color()}-900 dark:text-${color()}-300`}
          >
            <Show
              when={props.showSeed && showSeedForBracketMatch(props.match.name)}
              fallback={
                <MatchName
                  name={props.match.name}
                  dontMinimiseMatchName={props.dontMinimiseMatchName}
                  extraVerticalPadding
                />
              }
            >
              <MatchName
                name={props.match.name}
                dontMinimiseMatchName={props.dontMinimiseMatchName}
              />
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
