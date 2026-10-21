export const groupSections = (sections, fields) =>
  sections.length
    ? sections.map(section => ({
        section,
        fields: fields.filter(f => (f.section || "") === section.key)
      }))
    : [{ section: { key: "", next: "" }, fields }];

// The index of the section after `index`, or null to submit.
export const nextSectionIndex = (groups, index, answers) => {
  const { section, fields } = groups[index];
  let target = section.next || "";
  for (const field of fields) {
    const answer = answers[field.key];
    if (field.goto && typeof answer === "string") {
      target = field.goto[answer] || target;
    }
  }
  if (target === "submit") return null;
  const to = groups.findIndex(g => g.section.key === target);
  const next = target && to > index ? to : index + 1;
  return next < groups.length ? next : null;
};

// Indices of sections no path can reach, following every goto target and each section's next.
export const unreachableSections = groups => {
  const reached = new Set([0]);
  groups.forEach(({ section, fields }, index) => {
    if (!reached.has(index)) return;
    const targets = [
      section.next || "",
      ...fields.flatMap(f =>
        Object.values(f.goto || {}).map(t => t || section.next || "")
      )
    ];
    for (const target of targets) {
      if (target === "submit") continue;
      const to = groups.findIndex(g => g.section.key === target);
      reached.add(target && to > index ? to : index + 1);
    }
  });
  return new Set(groups.map((_, i) => i).filter(i => !reached.has(i)));
};
