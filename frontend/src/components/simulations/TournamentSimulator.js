import { createMemo, createSignal, For, Show } from "solid-js";

// ============ UTILITY FUNCTIONS ============

function seededRandom(seed) {
  const x = Math.sin(seed * 9301 + 49297) * 49297;
  return x - Math.floor(x);
}

function generateScore(matchId) {
  const r1 = seededRandom(matchId * 7 + 3);
  const r2 = seededRandom(matchId * 13 + 7);
  const r3 = seededRandom(matchId * 17 + 11);
  const winner = 13 + Math.floor(r1 * 3); // 13-15
  const loser = 7 + Math.floor(r2 * 6); // 7-12
  return r3 > 0.5 ? [winner, loser] : [loser, winner];
}

function ordinalSuffix(num) {
  if (10 < num % 100 && num % 100 < 20) return "th";
  const lastDigit = num % 10;
  if (lastDigit === 1) return "st";
  if (lastDigit === 2) return "nd";
  if (lastDigit === 3) return "rd";
  return "th";
}

function distributeTeamsToPoolsSerpentine(numTeams, numPools) {
  const pools = Array.from({ length: numPools }, () => []);
  for (let seed = 1; seed <= numTeams; seed++) {
    const row = Math.floor((seed - 1) / numPools);
    const col = (seed - 1) % numPools;
    const poolIndex = row % 2 === 0 ? col : numPools - 1 - col;
    pools[poolIndex].push(seed);
  }
  return pools;
}

const POOL_NAMES = "ABCDEFGHIJKLMNOP";

const STAGE_COLORS = {
  pool: "blue",
  swiss: "teal",
  bracket: "purple",
  position_pool: "amber"
};

// ============ TOURNAMENT ALGORITHMS ============

function computeOpponentStrength(matches, results) {
  // Sum of opponents' points for each team (higher = faced stronger opponents)
  const strength = {};
  for (const id of Object.keys(results)) {
    strength[parseInt(id)] = 0;
  }
  for (const match of matches) {
    if (!match.team_1 || !match.team_2) continue;
    const t1 = match.team_1.id;
    const t2 = match.team_2.id;
    const t1Pts = (results[t1]?.wins || 0) * 2 + (results[t1]?.draws || 0);
    const t2Pts = (results[t2]?.wins || 0) * 2 + (results[t2]?.draws || 0);
    if (t1 in strength) strength[t1] += t2Pts;
    if (t2 in strength) strength[t2] += t1Pts;
  }
  return strength;
}

function swissSort(a, b, strengthA = 0, strengthB = 0) {
  // Sort descending: points (win=2, draw=1) → opponent strength (higher = better) → GD → GF
  const ptsA = a.wins * 2 + (a.draws || 0);
  const ptsB = b.wins * 2 + (b.draws || 0);
  const pDiff = ptsB - ptsA;
  if (pDiff !== 0) return pDiff;
  const sDiff = strengthB - strengthA; // higher = faced stronger opponents
  if (sDiff !== 0) return sDiff;
  const gdDiff = b.GF - b.GA - (a.GF - a.GA);
  if (gdDiff !== 0) return gdDiff;
  return b.GF - a.GF;
}

function computePoolResults(matches, teamIds) {
  const results = {};
  teamIds.forEach((id, i) => {
    results[id] = {
      rank: i + 1,
      wins: 0,
      losses: 0,
      draws: 0,
      GF: 0,
      GA: 0
    };
  });

  for (const match of matches) {
    if (!match.team_1 || !match.team_2) continue;
    const t1 = match.team_1.id;
    const t2 = match.team_2.id;
    results[t1].GF += match.score_team_1;
    results[t1].GA += match.score_team_2;
    results[t2].GF += match.score_team_2;
    results[t2].GA += match.score_team_1;

    if (match.score_team_1 > match.score_team_2) {
      results[t1].wins++;
      results[t2].losses++;
    } else if (match.score_team_1 < match.score_team_2) {
      results[t2].wins++;
      results[t1].losses++;
    } else {
      results[t1].draws++;
      results[t2].draws++;
    }
  }

  // Rank by: wins desc, GD desc, GF desc
  const ranked = Object.entries(results).sort(([, a], [, b]) => {
    const wDiff = b.wins - a.wins;
    if (wDiff !== 0) return wDiff;
    const gdDiff = b.GF - b.GA - (a.GF - a.GA);
    if (gdDiff !== 0) return gdDiff;
    return b.GF - a.GF;
  });
  ranked.forEach(([, stats], i) => {
    stats.rank = i + 1;
  });

  return results;
}

function generateSwissPairings(
  results,
  playedPairs,
  excludeTeam = null,
  swissMatches = []
) {
  const oppStrength = computeOpponentStrength(swissMatches, results);
  const standings = Object.entries(results)
    .sort(([idA, a], [idB, b]) =>
      swissSort(
        a,
        b,
        oppStrength[parseInt(idA)] || 0,
        oppStrength[parseInt(idB)] || 0
      )
    )
    .map(([id]) => parseInt(id))
    .filter(id => id !== excludeTeam);

  const paired = new Set();
  const pairs = [];

  for (let i = 0; i < standings.length; i++) {
    const tid = standings[i];
    if (paired.has(tid)) continue;

    let foundPartner = false;
    for (let j = i + 1; j < standings.length; j++) {
      const candidate = standings[j];
      if (paired.has(candidate)) continue;
      const key = [Math.min(tid, candidate), Math.max(tid, candidate)].join(
        "-"
      );
      if (!playedPairs.has(key)) {
        pairs.push([tid, candidate]);
        paired.add(tid);
        paired.add(candidate);
        foundPartner = true;
        break;
      }
    }
    if (!foundPartner) {
      for (let j = i + 1; j < standings.length; j++) {
        const candidate = standings[j];
        if (!paired.has(candidate)) {
          pairs.push([tid, candidate]);
          paired.add(tid);
          paired.add(candidate);
          break;
        }
      }
    }
  }
  return pairs;
}

const BYE_SCORE = 15;

function selectByeTeam(results, teamsWithByes, swissMatches = []) {
  // Sort ascending (worst first) — reverse of swissSort
  const oppStrength = computeOpponentStrength(swissMatches, results);
  const standings = Object.entries(results)
    .sort(([idA, a], [idB, b]) =>
      swissSort(
        b,
        a,
        oppStrength[parseInt(idB)] || 0,
        oppStrength[parseInt(idA)] || 0
      )
    )
    .map(([id]) => parseInt(id));

  for (const tid of standings) {
    if (!teamsWithByes.has(tid)) return tid;
  }
  return standings[0]; // fallback
}

function applyByeToResults(results, teamId) {
  results[teamId].wins += 1;
  results[teamId].GF += BYE_SCORE;
}

function rerankResults(results, swissMatches = []) {
  // Compute OS (sum of opponents' points) and store on each team
  const oppStrength = computeOpponentStrength(swissMatches, results);
  for (const [id, stats] of Object.entries(results)) {
    stats.os = oppStrength[parseInt(id)] || 0;
  }

  // Rank by: points → OS (higher = better) → GD → GF
  const ranked = Object.entries(results).sort(([, a], [, b]) =>
    swissSort(a, b, a.os || 0, b.os || 0)
  );
  ranked.forEach(([, stats], i) => {
    stats.rank = i + 1;
  });
}

function updateBracketSeeding(seeding, match) {
  if (!match.team_1 || !match.team_2) return { ...seeding };
  const newSeeding = { ...seeding };
  if (
    match.placeholder_seed_2 > match.placeholder_seed_1 &&
    match.score_team_2 > match.score_team_1
  ) {
    newSeeding[match.placeholder_seed_1] = match.team_2.id;
    newSeeding[match.placeholder_seed_2] = match.team_1.id;
  } else if (
    match.placeholder_seed_1 > match.placeholder_seed_2 &&
    match.score_team_1 > match.score_team_2
  ) {
    newSeeding[match.placeholder_seed_2] = match.team_1.id;
    newSeeding[match.placeholder_seed_1] = match.team_2.id;
  }
  return newSeeding;
}

function getBracketMatchName(start, end, seed1, seed2) {
  const bracketSize = end - start + 1;
  const seed = Math.min(seed1, seed2);

  if (bracketSize === 2) {
    if (seed === 1) return "Finals";
    return `${seed}${ordinalSuffix(seed)} Place`;
  }
  if (bracketSize === 4) {
    if (seed >= 1 && seed <= 4) return "Semi Finals";
    return `${start}-${end} Bracket`;
  }
  if (bracketSize === 8) {
    if (seed >= 1 && seed <= 8) return "Quarter Finals";
    return `${start}-${end} Bracket`;
  }
  return `${start}-${end} Bracket`;
}

function createBracketSequenceMatches(
  bracketRef,
  start,
  end,
  seqNum,
  matches,
  idCounter
) {
  for (let i = 0; i < Math.floor((end - start + 1) / 2); i++) {
    const seed1 = start + i;
    const seed2 = end - i;
    matches.push({
      id: idCounter.next++,
      name: getBracketMatchName(start, end, seed1, seed2),
      bracket: bracketRef,
      pool: null,
      swiss_round: null,
      position_pool: null,
      sequence_number: seqNum,
      placeholder_seed_1: seed1,
      placeholder_seed_2: seed2,
      team_1: null,
      team_2: null,
      score_team_1: 0,
      score_team_2: 0
    });
  }
  if (end - start > 1) {
    const mid = start + Math.floor((end - start + 1) / 2) - 1;
    createBracketSequenceMatches(
      bracketRef,
      start,
      mid,
      seqNum + 1,
      matches,
      idCounter
    );
    createBracketSequenceMatches(
      bracketRef,
      mid + 1,
      end,
      seqNum + 1,
      matches,
      idCounter
    );
  }
}

// ============ RECOMPUTATION ENGINE ============

function recomputeTournament(config, scoreOverrides) {
  const {
    numTeams,
    initialStage,
    numPools,
    swissRounds: numSwissRounds,
    teamNames
  } = config;

  // 1. Create teams
  const teams = Array.from({ length: numTeams }, (_, i) => ({
    id: i + 1,
    name: teamNames[i] || `Team ${i + 1}`
  }));
  const teamsById = {};
  teams.forEach(t => {
    teamsById[t.id] = t;
  });

  // 2. Initial seeding
  const initialSeeding = {};
  teams.forEach((t, i) => {
    initialSeeding[i + 1] = t.id;
  });
  let currentSeeding = { ...initialSeeding };

  const idCounter = { next: 1 };
  const stages = [];
  const allMatches = [];

  // 3. Create initial stage
  if (initialStage === "pools") {
    const poolDist = distributeTeamsToPoolsSerpentine(numTeams, numPools);

    poolDist.forEach((seedsInPool, poolIdx) => {
      const poolName = POOL_NAMES[poolIdx];
      const poolRef = { id: poolIdx + 1, name: poolName, type: "pool" };

      // Create round-robin matches
      const poolMatches = [];
      for (let i = 0; i < seedsInPool.length; i++) {
        for (let j = i + 1; j < seedsInPool.length; j++) {
          const matchId = idCounter.next++;
          const [s1, s2] = scoreOverrides[matchId] || generateScore(matchId);
          const m = {
            id: matchId,
            name: `${poolName}${i + 1} vs ${poolName}${j + 1}`,
            pool: poolRef,
            swiss_round: null,
            bracket: null,
            position_pool: null,
            sequence_number: 1,
            placeholder_seed_1: seedsInPool[i],
            placeholder_seed_2: seedsInPool[j],
            team_1: teamsById[initialSeeding[seedsInPool[i]]],
            team_2: teamsById[initialSeeding[seedsInPool[j]]],
            score_team_1: s1,
            score_team_2: s2
          };
          poolMatches.push(m);
          allMatches.push(m);
        }
      }

      // Compute results
      const teamIdsInPool = seedsInPool.map(s => initialSeeding[s]);
      const results = computePoolResults(poolMatches, teamIdsInPool);

      // Update current seeding from pool results
      const rankedTeams = Object.entries(results).sort(([, a], [, b]) => {
        const wDiff = b.wins - a.wins;
        if (wDiff !== 0) return wDiff;
        const gdDiff = b.GF - b.GA - (a.GF - a.GA);
        if (gdDiff !== 0) return gdDiff;
        return b.GF - a.GF;
      });
      const sortedSeeds = [...seedsInPool].sort((a, b) => a - b);
      rankedTeams.forEach(([teamId], idx) => {
        currentSeeding[sortedSeeds[idx]] = parseInt(teamId);
      });

      stages.push({
        type: "pool",
        name: `Pool ${poolName}`,
        matches: poolMatches,
        results,
        teamIds: teamIdsInPool,
        seeds: seedsInPool
      });
    });
  } else {
    // Swiss Round
    const swissRef = { id: 1, type: "swiss" };
    const allSwissMatches = [];
    const playedPairs = new Set();
    const isOdd = numTeams % 2 !== 0;
    const teamsWithByes = new Set();

    // Initialize results
    let swissResults = {};
    teams.forEach(t => {
      swissResults[t.id] = {
        rank: t.id,
        wins: 0,
        losses: 0,
        draws: 0,
        GF: 0,
        GA: 0
      };
    });

    for (let round = 1; round <= numSwissRounds; round++) {
      let pairings;
      let byeTeamId = null;

      if (round === 1) {
        // Bye: last seed in round 1
        if (isOdd) {
          byeTeamId = initialSeeding[numTeams];
          teamsWithByes.add(byeTeamId);
          applyByeToResults(swissResults, byeTeamId);
          rerankResults(swissResults, allSwissMatches);
        }
        // Pair remaining seeds: 1 vs N-1, 2 vs N-2, etc.
        pairings = [];
        const activeCount = isOdd ? numTeams - 1 : numTeams;
        for (let i = 0; i < activeCount / 2; i++) {
          const seed1 = i + 1;
          const seed2 = activeCount - i;
          pairings.push([initialSeeding[seed1], initialSeeding[seed2]]);
        }
      } else {
        if (isOdd) {
          byeTeamId = selectByeTeam(
            swissResults,
            teamsWithByes,
            allSwissMatches
          );
          teamsWithByes.add(byeTeamId);
          applyByeToResults(swissResults, byeTeamId);
          rerankResults(swissResults, allSwissMatches);
        }
        pairings = generateSwissPairings(
          swissResults,
          playedPairs,
          byeTeamId,
          allSwissMatches
        );
      }

      const roundMatches = [];
      pairings.forEach(([t1Id, t2Id], matchIdx) => {
        const matchId = idCounter.next++;
        const [s1, s2] = scoreOverrides[matchId] || generateScore(matchId);

        // Compute placeholder seeds (rank in current standings for round 2+)
        let ps1, ps2;
        if (round === 1) {
          // Find seed for team
          ps1 = parseInt(
            Object.entries(initialSeeding).find(([, v]) => v === t1Id)[0]
          );
          ps2 = parseInt(
            Object.entries(initialSeeding).find(([, v]) => v === t2Id)[0]
          );
        } else {
          ps1 = swissResults[t1Id]?.rank || 1;
          ps2 = swissResults[t2Id]?.rank || 1;
        }

        const m = {
          id: matchId,
          name: `Swiss R${round} M${matchIdx + 1}`,
          pool: null,
          swiss_round: swissRef,
          bracket: null,
          position_pool: null,
          sequence_number: round,
          placeholder_seed_1: ps1,
          placeholder_seed_2: ps2,
          team_1: teamsById[t1Id],
          team_2: teamsById[t2Id],
          score_team_1: s1,
          score_team_2: s2
        };
        roundMatches.push(m);
        allSwissMatches.push(m);
        allMatches.push(m);

        // Track played pairs
        const key = [Math.min(t1Id, t2Id), Math.max(t1Id, t2Id)].join("-");
        playedPairs.add(key);
      });

      // Update swiss results after this round (rebuilds from matches only)
      swissResults = computePoolResults(
        allSwissMatches,
        teams.map(t => t.id)
      );

      // Re-apply all bye bonuses (not captured in match objects)
      for (const btId of teamsWithByes) {
        applyByeToResults(swissResults, btId);
      }
      rerankResults(swissResults, allSwissMatches);

      stages.push({
        type: "swiss",
        name: `Swiss Round ${round}`,
        matches: roundMatches,
        results: JSON.parse(JSON.stringify(swissResults)),
        round,
        totalRounds: numSwissRounds,
        byeTeamId,
        swissMatchesSoFar: [...allSwissMatches]
      });
    }

    // Update current seeding from final swiss results
    const finalOppStrength = computeOpponentStrength(
      allSwissMatches,
      swissResults
    );
    const rankedTeams = Object.entries(swissResults).sort(
      ([idA, a], [idB, b]) =>
        swissSort(
          a,
          b,
          finalOppStrength[parseInt(idA)] || 0,
          finalOppStrength[parseInt(idB)] || 0
        )
    );
    rankedTeams.forEach(([teamId], idx) => {
      currentSeeding[idx + 1] = parseInt(teamId);
    });
  }

  // 4. Create brackets and position pools
  // Rules: first bracket is 1-8 (or 1-4 if <=4 teams), then remaining in 8s or 4s.
  // Odd leftover teams go into a position pool (round-robin).
  const bracketGroups = [];
  const positionPoolGroups = [];
  let cursor = 1;

  if (numTeams <= 4) {
    bracketGroups.push({ start: 1, end: numTeams });
    cursor = numTeams + 1;
  } else {
    // First bracket is 1-8 (or fewer if not enough teams)
    const firstEnd = Math.min(8, numTeams);
    bracketGroups.push({ start: 1, end: firstEnd });
    cursor = firstEnd + 1;
  }

  // Remaining teams: group into 8s, 4s, or 2s for brackets.
  // Odd leftover (3, 5) → position pool. 1 leftover → skip (last place bye).
  while (cursor <= numTeams) {
    const remaining = numTeams - cursor + 1;
    if (remaining >= 8) {
      bracketGroups.push({ start: cursor, end: cursor + 7 });
      cursor += 8;
    } else if (remaining >= 4 && remaining % 2 === 0) {
      // Even: 4, 6 → take 4 as bracket, continue
      bracketGroups.push({ start: cursor, end: cursor + 3 });
      cursor += 4;
    } else if (remaining === 2) {
      bracketGroups.push({ start: cursor, end: cursor + 1 });
      cursor += 2;
    } else if (remaining >= 3 && remaining % 2 === 1) {
      // Odd: 3, 5, 7 → position pool (round-robin)
      positionPoolGroups.push({ start: cursor, end: numTeams });
      cursor = numTeams + 1;
    } else {
      // Single team leftover — gets last place bye
      cursor = numTeams + 1;
    }
  }

  // Process brackets
  for (const group of bracketGroups) {
    const { start, end } = group;
    const bracketSize = end - start + 1;
    const bracketName = `${start}-${end}`;
    const bracketRef = {
      id: 100 + start,
      name: bracketName,
      type: "bracket"
    };

    const bracketMatches = [];
    if (bracketSize >= 2 && bracketSize % 2 === 0) {
      createBracketSequenceMatches(
        bracketRef,
        start,
        end,
        1,
        bracketMatches,
        idCounter
      );
    }

    // Populate teams into bracket from current seeding
    let bracketSeeding = {};
    for (let s = start; s <= end; s++) {
      bracketSeeding[s] = currentSeeding[s];
    }

    // Process bracket matches round by round
    const maxSeq = Math.max(...bracketMatches.map(m => m.sequence_number));
    for (let seq = 1; seq <= maxSeq; seq++) {
      const roundMatches = bracketMatches.filter(
        m => m.sequence_number === seq
      );
      for (const match of roundMatches) {
        match.team_1 = teamsById[bracketSeeding[match.placeholder_seed_1]];
        match.team_2 = teamsById[bracketSeeding[match.placeholder_seed_2]];

        const [s1, s2] = scoreOverrides[match.id] || generateScore(match.id);
        match.score_team_1 = s1;
        match.score_team_2 = s2;

        bracketSeeding = updateBracketSeeding(bracketSeeding, match);
        allMatches.push(match);
      }
    }

    const matchesByRound = {};
    for (const m of bracketMatches) {
      if (!matchesByRound[m.sequence_number]) {
        matchesByRound[m.sequence_number] = [];
      }
      matchesByRound[m.sequence_number].push(m);
    }

    stages.push({
      type: "bracket",
      name: `${bracketName} Bracket`,
      matches: bracketMatches,
      matchesByRound,
      seeding: bracketSeeding
    });
  }

  // Process position pools (odd leftover teams)
  for (const group of positionPoolGroups) {
    const { start, end } = group;
    const ppName = `${start}-${end}`;
    const ppRef = { id: 200 + start, name: ppName, type: "position_pool" };

    const seeds = [];
    for (let s = start; s <= end; s++) seeds.push(s);

    const ppMatches = [];
    for (let i = 0; i < seeds.length; i++) {
      for (let j = i + 1; j < seeds.length; j++) {
        const matchId = idCounter.next++;
        const t1 = teamsById[currentSeeding[seeds[i]]];
        const t2 = teamsById[currentSeeding[seeds[j]]];
        const [s1, s2] = scoreOverrides[matchId] || generateScore(matchId);
        const m = {
          id: matchId,
          name: `PP${i + 1} vs PP${j + 1}`,
          pool: null,
          swiss_round: null,
          bracket: null,
          position_pool: ppRef,
          sequence_number: 1,
          placeholder_seed_1: seeds[i],
          placeholder_seed_2: seeds[j],
          team_1: t1,
          team_2: t2,
          score_team_1: s1,
          score_team_2: s2
        };
        ppMatches.push(m);
        allMatches.push(m);
      }
    }

    const teamIdsInPP = seeds.map(s => currentSeeding[s]);
    const results = computePoolResults(ppMatches, teamIdsInPP);

    stages.push({
      type: "position_pool",
      name: `${ppName} Position Pool`,
      matches: ppMatches,
      results,
      teamIds: teamIdsInPP,
      seeds
    });
  }

  return { teams, stages, allMatches, currentSeeding, teamsById };
}

// ============ SUB-COMPONENTS ============

function StandingsTable(props) {
  const isSwiss = createMemo(() => !!props.swissMatches);

  const sortedResults = createMemo(() => {
    if (!props.results) return [];
    const swiss = isSwiss();
    return Object.entries(props.results)
      .map(([teamId, stats]) => ({
        ...stats,
        teamId: parseInt(teamId),
        teamName: props.teamsById[parseInt(teamId)]?.name || `Team ${teamId}`,
        points: swiss ? stats.wins * 2 + (stats.draws || 0) : null
      }))
      .sort((a, b) => a.rank - b.rank);
  });

  return (
    <div class="mt-3">
      <div class="overflow-x-auto rounded-lg shadow">
        <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
          <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
            <tr>
              <th class="px-4 py-2">#</th>
              <th class="px-4 py-2">Team</th>
              <Show when={isSwiss()}>
                <th class="px-4 py-2" title="Points: Win=2, Draw=1, Loss=0">Pts</th>
              </Show>
              <th class="px-4 py-2">W</th>
              <th class="px-4 py-2">L</th>
              <th class="px-4 py-2">D</th>
              <Show when={isSwiss()}>
                <th class="px-4 py-2" title="Opponent Strength: sum of opponents' points (higher = faced stronger opponents)">OS</th>
              </Show>
              <th class="px-4 py-2">GF</th>
              <th class="px-4 py-2">GA</th>
              <th class="px-4 py-2">GD</th>
            </tr>
          </thead>
          <tbody>
            <For each={sortedResults()}>
              {result => (
                <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                  <td class="px-4 py-2 font-medium">{result.rank}</td>
                  <td class="px-4 py-2 font-medium">{result.teamName}</td>
                  <Show when={result.points !== null}>
                    <td class="px-4 py-2 font-semibold">{result.points}</td>
                  </Show>
                  <td class="px-4 py-2">{result.wins}</td>
                  <td class="px-4 py-2">{result.losses}</td>
                  <td class="px-4 py-2">{result.draws}</td>
                  <Show when={isSwiss()}>
                    <td class="px-4 py-2">{result.os ?? 0}</td>
                  </Show>
                  <td class="px-4 py-2">{result.GF}</td>
                  <td class="px-4 py-2">{result.GA}</td>
                  <td class="px-4 py-2">{result.GF - result.GA}</td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>
      <Show when={isSwiss()}>
        <p class="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
          Pts = Win(2) + Draw(1). OS = sum of opponents' points (higher = faced stronger opponents). Tiebreaker: Pts &gt; H2H &gt; OS &gt; GD.
        </p>
      </Show>
    </div>
  );
}

function MatchRow(props) {
  return (
    <div class="flex items-center gap-2 rounded border border-gray-200 bg-white px-3 py-2 dark:border-gray-700 dark:bg-gray-800">
      <span class="flex-1 text-right text-sm font-medium text-gray-900 dark:text-white">
        {props.match.team_1?.name || "TBD"}
      </span>
      <span class="text-xs text-gray-400">
        ({props.match.placeholder_seed_1})
      </span>
      <input
        type="number"
        class="w-12 rounded border border-gray-300 bg-gray-50 px-1 py-0.5 text-center text-sm font-bold text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
        value={props.match.score_team_1}
        min={0}
        onChange={e =>
          props.onScoreChange(props.match.id, [
            parseInt(e.target.value) || 0,
            props.match.score_team_2
          ])
        }
      />
      <span class="text-xs text-gray-400">-</span>
      <input
        type="number"
        class="w-12 rounded border border-gray-300 bg-gray-50 px-1 py-0.5 text-center text-sm font-bold text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
        value={props.match.score_team_2}
        min={0}
        onChange={e =>
          props.onScoreChange(props.match.id, [
            props.match.score_team_1,
            parseInt(e.target.value) || 0
          ])
        }
      />
      <span class="text-xs text-gray-400">
        ({props.match.placeholder_seed_2})
      </span>
      <span class="flex-1 text-sm font-medium text-gray-900 dark:text-white">
        {props.match.team_2?.name || "TBD"}
      </span>
    </div>
  );
}

function StageSection(props) {
  const colorClass = () => STAGE_COLORS[props.stage.type] || "gray";

  return (
    <div class="mb-6 rounded-lg border border-gray-200 bg-white p-4 shadow dark:border-gray-700 dark:bg-gray-900">
      <h3
        class={`mb-3 text-lg font-bold text-${colorClass()}-600 dark:text-${colorClass()}-400`}
      >
        {props.stage.name}
        <Show when={props.stage.type === "swiss"}>
          <span class="ml-2 text-sm font-normal text-gray-500">
            (Round {props.stage.round}/{props.stage.totalRounds})
          </span>
        </Show>
      </h3>

      <div class="space-y-1.5">
        <Show when={props.stage.type === "bracket"}>
          <For
            each={Object.entries(props.stage.matchesByRound || {}).sort(
              ([a], [b]) => a - b
            )}
          >
            {([seqNum, matches]) => (
              <div class="mb-3">
                <h4 class="mb-1.5 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
                  Round {seqNum}
                </h4>
                <div class="space-y-1.5">
                  <For each={matches}>
                    {match => (
                      <div class="flex items-center gap-2">
                        <span class="w-24 text-xs text-gray-400">
                          {match.name}
                        </span>
                        <div class="flex-1">
                          <MatchRow
                            match={match}
                            onScoreChange={props.onScoreChange}
                          />
                        </div>
                      </div>
                    )}
                  </For>
                </div>
              </div>
            )}
          </For>
        </Show>

        <Show when={props.stage.type !== "bracket"}>
          <For each={props.stage.matches}>
            {match => (
              <MatchRow match={match} onScoreChange={props.onScoreChange} />
            )}
          </For>
        </Show>
      </div>

      <Show when={props.stage.byeTeamId}>
        <div class="mt-2 rounded border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-700 dark:border-teal-800 dark:bg-teal-900/30 dark:text-teal-300">
          Bye: {props.teamsById[props.stage.byeTeamId]?.name} (15-0 win)
        </div>
      </Show>

      <Show when={props.stage.results}>
        <StandingsTable
          results={props.stage.results}
          teamsById={props.teamsById}
          swissMatches={props.stage.swissMatchesSoFar}
        />
      </Show>
    </div>
  );
}

// ============ MAIN COMPONENT ============

export default function TournamentSimulator() {
  const [numTeams, setNumTeams] = createSignal(8);
  const [initialStage, setInitialStage] = createSignal("pools");
  const [numPools, setNumPools] = createSignal(2);
  const [swissRounds, setSwissRounds] = createSignal(3);
  const [isGenerated, setIsGenerated] = createSignal(false);
  const [scoreOverrides, setScoreOverrides] = createSignal({});
  const [teamNames, setTeamNames] = createSignal(
    Array.from({ length: 24 }, (_, i) => `Team ${i + 1}`)
  );

  const suggestedPools = createMemo(() => {
    const n = numTeams();
    if (n <= 4) return 1;
    if (n <= 8) return 2;
    if (n <= 12) return 3;
    return 4;
  });

  const config = createMemo(() => ({
    numTeams: numTeams(),
    initialStage: initialStage(),
    numPools: numPools(),
    swissRounds: swissRounds(),
    teamNames: teamNames()
  }));

  const computed = createMemo(() => {
    if (!isGenerated()) return null;
    return recomputeTournament(config(), scoreOverrides());
  });

  function handleScoreChange(matchId, scores) {
    setScoreOverrides(prev => ({ ...prev, [matchId]: scores }));
  }

  function handleGenerate() {
    setScoreOverrides({});
    setIsGenerated(true);
  }

  function handleReset() {
    setIsGenerated(false);
    setScoreOverrides({});
  }

  function updateTeamName(index, name) {
    setTeamNames(prev => {
      const next = [...prev];
      next[index] = name;
      return next;
    });
  }

  const [showRules, setShowRules] = createSignal(false);

  return (
    <div class="mx-auto max-w-4xl">
      <h1 class="mb-6 text-center">
        <span class="bg-gradient-to-r from-blue-500 to-purple-500 bg-clip-text text-2xl font-extrabold text-transparent">
          Tournament Simulator
        </span>
      </h1>

      {/* Collapsible Rules Section */}
      <div class="mb-6 rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
        <button
          class="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-gray-700 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800"
          onClick={() => setShowRules(!showRules())}
        >
          <span>Tournament Format & Rules</span>
          <span class="text-gray-400">{showRules() ? "−" : "+"}</span>
        </button>
        <Show when={showRules()}>
          <div class="border-t border-gray-200 px-4 py-3 text-sm text-gray-600 dark:border-gray-700 dark:text-gray-400">
            <div class="space-y-4">
              <div>
                <h4 class="font-semibold text-gray-800 dark:text-gray-200">
                  Tournament Stages
                </h4>
                <p class="mt-1">
                  A tournament has two phases: a{" "}
                  <span class="font-medium text-blue-600 dark:text-blue-400">
                    seeding stage
                  </span>{" "}
                  (Pools or Swiss) followed by a{" "}
                  <span class="font-medium text-purple-600 dark:text-purple-400">
                    bracket stage
                  </span>{" "}
                  for final placements.
                </p>
              </div>

              <div>
                <h4 class="font-semibold text-blue-700 dark:text-blue-400">
                  Pools
                </h4>
                <p class="mt-1">
                  Teams are divided into groups using serpentine seeding and
                  play a round-robin within each pool. Rankings are determined
                  by: wins, then head-to-head record, then goal difference, then
                  goals scored.
                </p>
              </div>

              <div>
                <h4 class="font-semibold text-teal-700 dark:text-teal-400">
                  Swiss Rounds
                </h4>
                <p class="mt-1">
                  All teams play in each round, paired against opponents with
                  similar records. In round 1, seeds are paired top-vs-bottom (1
                  vs N, 2 vs N-1, etc.). In subsequent rounds, teams are paired
                  by current standings, avoiding rematches where possible.
                </p>
              </div>

              <div>
                <h4 class="font-semibold text-teal-700 dark:text-teal-400">
                  Swiss — Odd Number of Teams
                </h4>
                <p class="mt-1">
                  When there is an odd number of teams, one team receives a{" "}
                  <span class="font-medium">bye</span> each round (a free 15-0
                  win). The bye is given to the lowest-ranked team that hasn't
                  already received a bye. Each team can only receive one bye
                  across all rounds.
                </p>
              </div>

              <div>
                <h4 class="font-semibold text-teal-700 dark:text-teal-400">
                  Swiss — Ranking & Tiebreakers
                </h4>
                <p class="mt-1">
                  Teams are ranked by <span class="font-medium">points</span>:
                  win = 2 pts, draw = 1 pt, loss = 0 pts. When teams have the
                  same points, ties are broken in this order:
                </p>
                <ol class="mt-1 list-inside list-decimal space-y-1 pl-2">
                  <li>
                    <span class="font-medium">Head-to-head</span> — wins between
                    the tied teams
                  </li>
                  <li>
                    <span class="font-medium">Opponent strength (OS)</span> —
                    sum of opponents' points. A higher value means the team
                    faced stronger opponents and is ranked higher
                  </li>
                  <li>
                    <span class="font-medium">Goal difference</span> — overall
                    goals scored minus goals conceded
                  </li>
                </ol>
              </div>

              <div>
                <h4 class="font-semibold text-purple-700 dark:text-purple-400">
                  Brackets
                </h4>
                <p class="mt-1">
                  After the seeding stage, teams are placed into elimination
                  brackets based on their final standings. The top 8 teams go
                  into the main bracket (or top 4 if 4 or fewer teams).
                  Remaining teams are grouped into brackets of 8, 4, or 2. If
                  there's an odd group left over, they play a position pool
                  (round-robin) instead.
                </p>
              </div>

              <div>
                <h4 class="font-semibold text-amber-700 dark:text-amber-400">
                  Position Pools
                </h4>
                <p class="mt-1">
                  When an odd number of remaining teams can't form an even
                  bracket, they play a round-robin position pool to determine
                  their final placement.
                </p>
              </div>
            </div>
          </div>
        </Show>
      </div>

      <Show
        when={isGenerated()}
        fallback={
          <div class="mx-auto max-w-xl space-y-6">
            {/* Team Count */}
            <div>
              <label class="mb-2 block text-sm font-medium text-gray-900 dark:text-white">
                Number of Teams
              </label>
              <input
                type="number"
                min={4}
                max={24}
                step={1}
                value={numTeams()}
                onInput={e => {
                  const val = parseInt(e.target.value) || 4;
                  const clamped = Math.max(4, Math.min(24, val));
                  setNumTeams(clamped);
                  setNumPools(
                    clamped <= 4 ? 1 : clamped <= 8 ? 2 : clamped <= 12 ? 3 : 4
                  );
                }}
                class="w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              />
            </div>

            {/* Team Names */}
            <div>
              <label class="mb-2 block text-sm font-medium text-gray-900 dark:text-white">
                Team Names
              </label>
              <div class="grid grid-cols-2 gap-2">
                <For each={Array.from({ length: numTeams() }, (_, i) => i)}>
                  {i => (
                    <div class="flex items-center gap-2">
                      <span class="w-6 text-right text-xs text-gray-400">
                        {i + 1}.
                      </span>
                      <input
                        type="text"
                        value={teamNames()[i]}
                        onInput={e => updateTeamName(i, e.target.value)}
                        class="flex-1 rounded border border-gray-300 bg-gray-50 px-2 py-1 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      />
                    </div>
                  )}
                </For>
              </div>
            </div>

            {/* Initial Stage */}
            <div>
              <label class="mb-2 block text-sm font-medium text-gray-900 dark:text-white">
                Initial Stage
              </label>
              <div class="flex gap-3">
                <button
                  class={`flex-1 rounded-lg border-2 px-4 py-3 text-sm font-medium transition-colors ${
                    initialStage() === "pools"
                      ? "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                      : "border-gray-300 text-gray-700 hover:border-gray-400 dark:border-gray-600 dark:text-gray-300"
                  }`}
                  onClick={() => setInitialStage("pools")}
                >
                  Pools
                </button>
                <button
                  class={`flex-1 rounded-lg border-2 px-4 py-3 text-sm font-medium transition-colors ${
                    initialStage() === "swiss"
                      ? "border-teal-500 bg-teal-50 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400"
                      : "border-gray-300 text-gray-700 hover:border-gray-400 dark:border-gray-600 dark:text-gray-300"
                  }`}
                  onClick={() => setInitialStage("swiss")}
                >
                  Swiss Round
                </button>
              </div>
            </div>

            {/* Stage-specific config */}
            <Show when={initialStage() === "pools"}>
              <div>
                <label class="mb-2 block text-sm font-medium text-gray-900 dark:text-white">
                  Number of Pools (suggested: {suggestedPools()})
                </label>
                <input
                  type="number"
                  min={1}
                  max={Math.floor(numTeams() / 2)}
                  value={numPools()}
                  onInput={e =>
                    setNumPools(
                      Math.max(
                        1,
                        Math.min(
                          Math.floor(numTeams() / 2),
                          parseInt(e.target.value) || 1
                        )
                      )
                    )
                  }
                  class="w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                />
                <p class="mt-1 text-xs text-gray-500">
                  ~{Math.ceil(numTeams() / numPools())} teams per pool
                  <Show when={numTeams() % numPools() !== 0}>
                    {" "}
                    (uneven distribution)
                  </Show>
                </p>
              </div>
            </Show>

            <Show when={initialStage() === "swiss"}>
              <div>
                <label class="mb-2 block text-sm font-medium text-gray-900 dark:text-white">
                  Number of Swiss Rounds
                </label>
                <input
                  type="number"
                  min={2}
                  max={numTeams() - 1}
                  value={swissRounds()}
                  onInput={e =>
                    setSwissRounds(
                      Math.max(
                        2,
                        Math.min(numTeams() - 1, parseInt(e.target.value) || 2)
                      )
                    )
                  }
                  class="w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                />
              </div>
            </Show>

            {/* Bracket preview */}
            <div class="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800">
              <h4 class="mb-1 text-sm font-medium text-gray-700 dark:text-gray-300">
                Bracket Stage (auto-configured)
              </h4>
              <p class="text-xs text-gray-500">
                <Show when={numTeams() <= 4}>1-{numTeams()} Bracket</Show>
                <Show when={numTeams() > 4 && numTeams() <= 8}>
                  1-{numTeams()} Bracket
                </Show>
                <Show when={numTeams() > 8}>
                  1-8 Bracket
                  {(() => {
                    const parts = [];
                    let c = 9;
                    while (c <= numTeams()) {
                      const r = numTeams() - c + 1;
                      if (r >= 8) {
                        parts.push(`${c}-${c + 7} Bracket`);
                        c += 8;
                      } else if (r >= 4 && r % 2 === 0) {
                        parts.push(`${c}-${c + 3} Bracket`);
                        c += 4;
                      } else if (r === 2) {
                        parts.push(`${c}-${c + 1} Bracket`);
                        c += 2;
                      } else if (r >= 3 && r % 2 === 1) {
                        parts.push(`${c}-${numTeams()} Position Pool`);
                        c = numTeams() + 1;
                      } else {
                        c = numTeams() + 1;
                      }
                    }
                    return parts.length ? " + " + parts.join(" + ") : "";
                  })()}
                </Show>
              </p>
            </div>

            {/* Generate Button */}
            <button
              class="w-full rounded-lg bg-blue-600 px-5 py-3 text-center text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-500 dark:hover:bg-blue-600"
              onClick={handleGenerate}
            >
              Generate Tournament
            </button>
          </div>
        }
      >
        {/* Simulation Display */}
        <div>
          <div class="mb-4 flex items-center justify-between">
            <button
              class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
              onClick={handleReset}
            >
              New Simulation
            </button>
            <button
              class="rounded-lg border border-orange-300 px-4 py-2 text-sm font-medium text-orange-700 hover:bg-orange-50 dark:border-orange-600 dark:text-orange-300 dark:hover:bg-orange-900/30"
              onClick={() => setScoreOverrides({})}
            >
              Reset All Scores
            </button>
          </div>

          {/* Seeding Overview */}
          <div class="mb-6 rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800">
            <h3 class="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
              Initial Seeding
            </h3>
            <div class="flex flex-wrap gap-2">
              <For each={computed()?.teams || []}>
                {(team, i) => (
                  <span class="rounded bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-800 dark:bg-gray-700 dark:text-gray-300">
                    {i() + 1}. {team.name}
                  </span>
                )}
              </For>
            </div>
          </div>

          {/* Stages */}
          <For each={computed()?.stages || []}>
            {stage => (
              <StageSection
                stage={stage}
                teamsById={computed()?.teamsById || {}}
                onScoreChange={handleScoreChange}
              />
            )}
          </For>

          {/* Final Seeding */}
          <Show when={computed()}>
            <div class="mt-6 rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-900/30">
              <h3 class="mb-2 text-sm font-semibold text-green-700 dark:text-green-300">
                Final Tournament Seeding
              </h3>
              <div class="space-y-1">
                <For
                  each={Object.entries(computed().currentSeeding).sort(
                    ([a], [b]) => parseInt(a) - parseInt(b)
                  )}
                >
                  {([seed, teamId]) => (
                    <div class="flex items-center gap-2 text-sm">
                      <span class="w-8 font-bold text-green-600 dark:text-green-400">
                        {seed}.
                      </span>
                      <span class="text-gray-900 dark:text-white">
                        {computed().teamsById[teamId]?.name}
                      </span>
                    </div>
                  )}
                </For>
              </div>
            </div>
          </Show>
        </div>
      </Show>
    </div>
  );
}
