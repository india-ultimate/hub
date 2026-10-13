import { A } from "@solidjs/router";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import {
  academicCap,
  bolt,
  cake,
  checkBadge,
  faceSmile,
  map,
  sun,
  trophy,
  userGroup,
  users
} from "solid-heroicons/solid";
import { For, Show } from "solid-js";

import { grass, wheelchair } from "./icons";

export const SANCTIONED = "Sanctioned by India Ultimate";
// /tournaments?iu=1 shows only sanctioned events.
export const SANCTIONED_LINK = "/tournaments?iu=1";

// Event tags, matching the choices on server Event. One table drives the
// create form (every entry), the chips (chip: on the tournament page; and on
// cards where standsOut) and the /tournaments filters (filter: by its name).
const tagChoices = (values, icon) =>
  values.map(value => ({ value, label: value, icon }));
const yesNo = [
  { value: "true", label: "Yes" },
  { value: "false", label: "No" }
];

export const tournamentTags = [
  { name: "is_iu_sanctioned", label: SANCTIONED, options: yesNo },
  {
    name: "is_subscription_needed",
    label: "IU membership required",
    options: yesNo
  },
  {
    name: "age",
    label: "Age Division",
    options: tagChoices(["Open", "Masters", "U24", "U18"], cake),
    chip: true,
    standsOut: v => v !== "Open",
    filter: true
  },
  {
    name: "surface",
    label: "Surface",
    options: [
      { value: "Grass", label: "Grass", icon: grass },
      { value: "Beach", label: "Beach", icon: sun }
    ],
    chip: true,
    standsOut: v => v === "Beach",
    filter: true
  },
  {
    name: "level",
    label: "Level",
    options: [
      { value: "Club", label: "Club", icon: userGroup },
      { value: "State", label: "State", icon: map },
      { value: "College", label: "College", icon: academicCap },
      { value: "Rec", label: "Rec", icon: faceSmile }
    ],
    chip: true,
    standsOut: v => v !== "Club"
  },
  {
    name: "stage",
    label: "Stage",
    options: tagChoices(
      ["Sectionals", "Regionals", "Nationals", "Standalone"],
      trophy
    ),
    chip: true,
    standsOut: v => v !== "Standalone",
    filter: true
  },
  {
    name: "format",
    label: "Format",
    options: tagChoices(["7v7", "5v5"], users),
    chip: true
  },
  {
    name: "skill_division",
    label: "Skill Division",
    options: tagChoices(["Not split", "Elite", "Challenger"], bolt),
    chip: true,
    standsOut: () => true
  },
  {
    name: "is_adaptive",
    label: "Adaptive (e.g. Wheelchair)",
    options: yesNo,
    chip: true,
    icon: wheelchair,
    chipText: "Adaptive",
    standsOut: () => true
  }
];

const seal = "h-5 w-5 shrink-0 text-blue-600 dark:text-blue-400";

// After a card's title, like a verified tick.
export const SanctionedSeal = () => (
  <span class="ml-1 inline-flex align-text-bottom">
    <Icon path={checkBadge} aria-hidden="true" class={seal} />
    <span class="sr-only">{SANCTIONED}</span>
  </span>
);

export const SanctionedPill = () => (
  <div class="flex flex-col items-center gap-1 text-center">
    <A
      href={SANCTIONED_LINK}
      class="inline-flex min-h-[44px] items-center gap-1.5 rounded-full bg-blue-50 px-4 text-sm font-medium text-blue-700 ring-1 ring-blue-600/20 hover:bg-blue-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:bg-blue-900/40 dark:text-blue-200 dark:ring-blue-400/30 dark:hover:bg-blue-900/60"
    >
      <Icon path={checkBadge} aria-hidden="true" class={seal} />
      {SANCTIONED}
    </A>
    <p class="text-sm text-gray-600 dark:text-gray-300">
      An official India Ultimate event.
    </p>
  </div>
);

// A chip for each tag the event has. On cards, only those that stand out.
const chipsFor = (event, onlyStandouts) =>
  tournamentTags
    .filter(tag => tag.chip)
    .flatMap(tag => {
      const value = event?.[tag.name];
      if (value === null || value === undefined || value === false) return [];
      if (onlyStandouts && !tag.standsOut?.(value)) return [];
      if (value === true) return [{ tag, icon: tag.icon, text: tag.chipText }];
      const option = tag.options.find(o => o.value === value);
      if (!option) return [];
      return [{ tag, value, icon: option.icon, text: option.label }];
    });

const chip =
  "inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-sm text-gray-700 dark:bg-gray-700 dark:text-gray-200";
// On the page every chip is tap-sized, so linked and plain ones line up.
const pageChip = "min-h-[44px] px-3";
const chipLink =
  "hover:bg-gray-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:hover:bg-gray-600";

export const TagChips = props => {
  const chips = () => chipsFor(props.event, props.variant === "card");
  return (
    <Show when={chips().length}>
      <ul class={clsx("flex flex-wrap gap-2", props.class)}>
        <For each={chips()}>
          {c => {
            const Body = () => (
              <>
                <Icon
                  path={c.icon}
                  aria-hidden="true"
                  class="h-4 w-4 shrink-0"
                />
                {c.text}
              </>
            );
            return (
              <li>
                <Show
                  when={props.variant === "page" && c.tag.filter && c.value}
                  fallback={
                    <span
                      class={clsx(chip, props.variant === "page" && pageChip)}
                    >
                      <Body />
                    </span>
                  }
                >
                  <A
                    href={`/tournaments?${c.tag.name}=${encodeURIComponent(c.value)}`}
                    class={clsx(chip, pageChip, chipLink)}
                  >
                    <Body />
                  </A>
                </Show>
              </li>
            );
          }}
        </For>
      </ul>
    </Show>
  );
};
