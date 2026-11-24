export const points = row => (row.wins ?? 0) * 2 + (row.draws ?? 0);

const ids = obj => Object.keys(obj).map(Number);

export function opponentStrength(results, games) {
  const strength = {};
  for (const id of ids(results)) strength[id] = 0;
  for (const [t1, t2] of games) {
    strength[t1] += points(results[t2]);
    strength[t2] += points(results[t1]);
  }
  return strength;
}

function headToHeadWins(group, games) {
  const wins = new Map(group.map(id => [id, 0]));
  for (const [t1, t2, s1, s2] of games) {
    if (wins.has(t1) && wins.has(t2)) {
      if (s1 > s2) wins.set(t1, wins.get(t1) + 1);
      else if (s2 > s1) wins.set(t2, wins.get(t2) + 1);
    }
  }
  return wins;
}

function splitBy(group, key) {
  const ordered = [...group].sort((a, b) => key(b) - key(a));
  const runs = [];
  for (const id of ordered) {
    const last = runs[runs.length - 1];
    if (last && key(last[0]) === key(id)) last.push(id);
    else runs.push([id]);
  }
  return runs;
}

function breakTie(group, results, games, strength, lots) {
  if (group.length === 1) return group;
  const h2h = headToHeadWins(group, games);
  const gf = id => results[id].GF ?? 0;
  const criteria = [
    id => h2h.get(id),
    id => strength[id],
    id => gf(id) - (results[id].GA ?? 0),
    gf
  ];
  for (const key of criteria) {
    if (new Set(group.map(key)).size > 1) {
      return splitBy(group, key).flatMap(run =>
        breakTie(run, results, games, strength, lots)
      );
    }
  }
  const hasLots = Object.keys(lots).length > 0;
  return [...group].sort((a, b) => (hasLots ? lots[a] - lots[b] : a - b));
}

export function rankTeams(results, games, lots) {
  const strength = opponentStrength(results, games);
  const byPoints = ids(results).sort(
    (a, b) => points(results[b]) - points(results[a]) || a - b
  );
  const ranked = [];
  let group = [];
  for (const id of byPoints) {
    if (group.length && points(results[group[0]]) !== points(results[id])) {
      ranked.push(...breakTie(group, results, games, strength, lots));
      group = [];
    }
    group.push(id);
  }
  if (group.length)
    ranked.push(...breakTie(group, results, games, strength, lots));
  return ranked;
}

const key = (a, b) => `${Math.min(a, b)}-${Math.max(a, b)}`;

function backtrackPair(order, played, paired, pairs, start) {
  let index = start;
  while (index < order.length && paired.has(order[index])) index++;
  if (index >= order.length) return true;

  const id = order[index];
  for (let j = index + 1; j < order.length; j++) {
    const candidate = order[j];
    if (paired.has(candidate) || played.has(key(id, candidate))) continue;
    paired.add(id);
    paired.add(candidate);
    pairs.push([id, candidate]);
    if (backtrackPair(order, played, paired, pairs, index + 1)) return true;
    paired.delete(id);
    paired.delete(candidate);
    pairs.pop();
  }
  return false;
}

export function pairTeams(order, playedKeys) {
  const paired = new Set();
  const pairs = [];
  if (backtrackPair(order, playedKeys, paired, pairs, 0)) return pairs;

  paired.clear();
  pairs.length = 0;
  order.forEach((id, i) => {
    if (paired.has(id)) return;
    const unpaired = order.slice(i + 1).filter(c => !paired.has(c));
    const fresh = unpaired.filter(c => !playedKeys.has(key(id, c)));
    const choice = fresh.length ? fresh : unpaired;
    if (choice.length) {
      pairs.push([id, choice[0]]);
      paired.add(id);
      paired.add(choice[0]);
    }
  });
  return pairs;
}

export function selectBye(order, hadBye) {
  for (let i = order.length - 1; i >= 0; i--) {
    if (!hadBye.has(order[i])) return order[i];
  }
  return order[order.length - 1];
}

export const BYE_SCORE = 15;

// Production's order for a round: pick the bye from the standings, give that
// team its win and goals, re-rank, then pair everyone else from the new order.
export function nextRound(results, games, lots, hadBye, playedKeys) {
  const order = rankTeams(results, games, lots);
  if (order.length % 2 === 0)
    return { bye: null, pairs: pairTeams(order, playedKeys), order };
  const bye = selectBye(order, hadBye);
  const after = {
    ...results,
    [bye]: {
      ...results[bye],
      wins: results[bye].wins + 1,
      GF: results[bye].GF + BYE_SCORE
    }
  };
  const ranked = rankTeams(after, games, lots);
  const rest = ranked.filter(id => id !== bye);
  return { bye, pairs: pairTeams(rest, playedKeys), order: ranked };
}
