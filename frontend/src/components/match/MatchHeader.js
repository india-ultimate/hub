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
  // Swiss round matches are named like "Swiss A R1 M1"
  const swissPattern = matchName?.match(/Swiss ([A-Z]+) R(\d+)/);
  if (swissPattern) {
    return `SW ${swissPattern[1]} - ${swissPattern[2]}`;
  }
  // Bracket matches are named like 5-8 Bracket, 9-12 Bracket
  // On smaller screens show as B 5-8, B 9-12
  const matchBracketPattern = matchName?.match(/(\d+-\d+) Bracket/);
  if (matchBracketPattern) {
    return `B ${matchBracketPattern[1]}`;
  }
  // Return same name otherwise (Finals)
  return matchName;
};

// Format Swiss names for public display: "Swiss A R1 M1" -> "Swiss A - 1"
const getPublicSwissName = name => {
  const m = name?.match(/Swiss ([A-Z]+) R(\d+)/);
  return m ? `Swiss ${m[1]} - ${m[2]}` : name;
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
          class="block w-full text-center sm:hidden"
          classList={{ "py-2": props.extraVerticalPadding }}
        >
          {getSmallName(props.name)}
        </h6>
        <h6
          class="hidden w-full text-center sm:block"
          classList={{ "py-2": props.extraVerticalPadding }}
        >
          {props.match?.swiss_round
            ? getPublicSwissName(props.name)
            : props.name}
        </h6>
      </>
    }
  >
    <h6
      class="w-full text-center"
      classList={{ "py-2": props.extraVerticalPadding }}
    >
      {props.match?.swiss_round ? getPublicSwissName(props.name) : props.name}
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
        <Match
          when={
            props.match?.pool ||
            props.match?.position_pool ||
            props.match?.swiss_round
          }
        >
          <div
            class={`flex w-full flex-wrap justify-center bg-${color()}-100 text-${color()}-800 rounded px-2.5 py-0.5 text-xs font-medium dark:bg-${color()}-900 dark:text-${color()}-300`}
          >
            <Show
              when={props.showSeed}
              fallback={
                <h6 class="w-full py-2 text-center">
                  {props.match?.swiss_round
                    ? (props.useSmallSwissName ? getSmallName(props.match?.name) : getPublicSwissName(props.match?.name))
                    : props.match?.name}
                </h6>
              }
            >
              <h6 class="w-full text-center">
                {props.match?.swiss_round
                  ? (props.useSmallSwissName ? getSmallName(props.match?.name) : getPublicSwissName(props.match?.name))
                  : props.match?.name}
              </h6>
              <h6 class="text-center">
                {props.match?.placeholder_seed_1 +
                  " v " +
                  props.match?.placeholder_seed_2}
              </h6>
            </Show>
          </div>
        </Match>
        <Match when={props.match?.cross_pool || props.match?.bracket}>
          <div
            class={`flex w-full flex-wrap justify-center bg-${color()}-100 text-${color()}-800 rounded px-2.5 py-0.5 text-xs font-medium dark:bg-${color()}-900 dark:text-${color()}-300`}
          >
            <Show
              when={
                props.showSeed && showSeedForBracketMatch(props.match?.name)
              }
              fallback={
                <MatchName
                  name={props.match?.name}
                  dontMinimiseMatchName={props.dontMinimiseMatchName}
                  extraVerticalPadding
                />
              }
            >
              <MatchName
                name={props.match?.name}
                dontMinimiseMatchName={props.dontMinimiseMatchName}
              />
              <h6 class="text-center">
                {props.match?.placeholder_seed_1 +
                  " v " +
                  props.match?.placeholder_seed_2}
              </h6>
            </Show>
          </div>
        </Match>
        <Match
          when={
            !(
              props.match?.pool ||
              props.match?.position_pool ||
              props.match?.cross_pool ||
              props.match?.bracket ||
              props.match?.swiss_round
            )
          }
        >
          <div class="flex w-full flex-wrap justify-center rounded bg-orange-100 px-2.5 py-0.5 text-xs font-medium text-orange-800 dark:bg-orange-900 dark:text-orange-300">
            <Show
              when={
                props.showSeed && showSeedForBracketMatch(props.match?.name)
              }
              fallback={
                <MatchName
                  name={props.match?.name}
                  dontMinimiseMatchName={props.dontMinimiseMatchName}
                  extraVerticalPadding
                />
              }
            >
              <MatchName
                name={props.match?.name}
                dontMinimiseMatchName={props.dontMinimiseMatchName}
              />
              <h6 class="text-center">
                {props.match?.placeholder_seed_1 +
                  " v " +
                  props.match?.placeholder_seed_2}
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
          handleMatchCardClick(props.match?.id);
        }}
      >
        {renderBadge()}
      </button>
    </Show>
  );
};

export default MatchCard;
