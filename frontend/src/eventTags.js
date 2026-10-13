export const SANCTIONED = "Sanctioned by India Ultimate";

// Event tags, matching the choices on server Event. The create form asks for
// every one, in this order.
const tagChoices = values => values.map(value => ({ value, label: value }));
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
    options: tagChoices(["Open", "Masters", "U24", "U18"])
  },
  {
    name: "surface",
    label: "Surface",
    options: tagChoices(["Grass", "Beach"])
  },
  {
    name: "level",
    label: "Level",
    options: tagChoices(["Club", "State", "College", "Rec"])
  },
  {
    name: "stage",
    label: "Stage",
    options: tagChoices(["Sectionals", "Regionals", "Nationals", "Standalone"])
  },
  { name: "format", label: "Format", options: tagChoices(["7v7", "5v5"]) },
  {
    name: "skill_division",
    label: "Skill Division",
    options: tagChoices(["Not split", "Elite", "Challenger"])
  },
  { name: "is_adaptive", label: "Adaptive (e.g. Wheelchair)", options: yesNo }
];
