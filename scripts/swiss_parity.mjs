import { readFileSync } from "node:fs";

import {
  nextRound,
  rankTeams,
} from "../frontend/src/components/simulations/swiss.mjs";

const numberKeys = (obj) =>
  Object.fromEntries(Object.entries(obj).map(([id, v]) => [Number(id), v]));

const run = ({ results, games, lots, played, had_bye: hadBye }) => {
  const rank = rankTeams(numberKeys(results), games, numberKeys(lots));
  const playedKeys = new Set(
    played.map(([a, b]) => `${Math.min(a, b)}-${Math.max(a, b)}`),
  );
  const out = { rank };
  const { bye, pairs, order } = nextRound(
    numberKeys(results),
    games,
    numberKeys(lots),
    new Set(hadBye),
    playedKeys,
  );
  if (bye !== null) out.bye = bye;
  out.pairs = pairs;
  out.order = order;
  return out;
};

process.stdout.write(
  JSON.stringify(JSON.parse(readFileSync(0, "utf8")).map(run)),
);
