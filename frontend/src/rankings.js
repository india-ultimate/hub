export const eventLine = ({ tournament_title: title, tier, year }) => {
  let text = title;
  if (tier) {
    text = text
      .replace(new RegExp(`\\(\\s*${tier}\\s*\\)`, "gi"), "")
      .replace(new RegExp(`^\\s*${tier}\\b`, "i"), "")
      .replace(new RegExp(`\\b${tier}\\s*$`, "i"), "");
  }
  text = text.replace(/\s+/g, " ").replace(/^[\s\-–·]+|[\s\-–·]+$/g, "");
  return text.includes(String(year)) ? text : `${text} · ${year}`;
};
