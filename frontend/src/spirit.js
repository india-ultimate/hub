const DEFAULT_SCORE = 2;
const BLOCKS = [
  "spirit_score_team_1",
  "spirit_score_team_2",
  "self_spirit_score_team_1",
  "self_spirit_score_team_2"
];

const formValues = score => ({
  rules: score?.rules ?? DEFAULT_SCORE,
  fouls: score?.fouls ?? DEFAULT_SCORE,
  fair: score?.fair ?? DEFAULT_SCORE,
  positive: score?.positive ?? DEFAULT_SCORE,
  communication: score?.communication ?? DEFAULT_SCORE,
  mvp_id: score?.mvp ? String(score.mvp.id) : undefined,
  msp_id: score?.msp ? String(score.msp.id) : undefined
});

// What the director's spirit form starts from: the scores the match already
// has, or 2s for a block nobody has scored yet.
export const spiritInitialValues = match =>
  Object.fromEntries(BLOCKS.map(block => [block, formValues(match?.[block])]));

// The form has no comments box, but saving replaces each score, so the
// comments already on the match have to be sent back or they'd be wiped.
export const withSpiritComments = (values, match) =>
  Object.fromEntries(
    BLOCKS.map(block => [
      block,
      { ...values[block], comments: match?.[block]?.comments }
    ])
  );
