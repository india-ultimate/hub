import { getCookie } from "./utils";

export const fetchContributors = async () => {
  const repoResp = await fetch(
    "https://api.github.com/repos/india-ultimate/hub/contributors"
  );
  const repoContributors = await repoResp.json();

  let contributors = [];

  for await (const repoContributor of repoContributors) {
    const contributorResp = await fetch(repoContributor.url);
    const contributor = await contributorResp.json();
    contributors.push(contributor);
  }

  return contributors;
};

export const fetchTransactions = async () => {
  const response = await fetch("/api/transactions", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchAllTransactions = async () => {
  const response = await fetch("/api/transactions?include_all=1", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchEvents = async () => {
  const response = await fetch("/api/events?include_all=true", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchAllInvalidTransactions = async () => {
  const response = await fetch(
    "/api/transactions?include_all=1&only_invalid=1",
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const fetchPlayers = async () => {
  const response = await fetch("/api/players", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchTeams = async () => {
  const response = await fetch("/api/teams", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchTeamBySlug = async team_slug => {
  const response = await fetch(`/api/team/${team_slug}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchTournaments = async () => {
  const response = await fetch("/api/tournaments", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });

  let tournaments = await response.json();

  tournaments.sort((a, b) => {
    if (a.status === "LIV" && b.status !== "LIV") {
      return -1;
    } else if (a.status !== "LIV" && b.status === "LIV") {
      return 1;
    } else if (
      (a.status === "LIV" && b.status === "LIV") ||
      (a.status !== "LIV" && b.status !== "LIV")
    ) {
      return 0;
    }
  });

  return tournaments;
};

export const fetchTournament = async tournament_id => {
  const response = await fetch(`/api/tournament?id=${tournament_id}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchTournamentBySlug = async tournament_slug => {
  const response = await fetch(`/api/tournament?slug=${tournament_slug}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchPools = async tournament_id => {
  const response = await fetch(`/api/tournament/pools?id=${tournament_id}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchPoolsBySlug = async tournament_slug => {
  const response = await fetch(
    `/api/tournament/pools?slug=${tournament_slug}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const fetchCrossPool = async tournament_id => {
  const response = await fetch(
    `/api/tournament/cross-pool?id=${tournament_id}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const fetchCrossPoolBySlug = async tournament_slug => {
  const response = await fetch(
    `/api/tournament/cross-pool?slug=${tournament_slug}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const fetchBrackets = async tournament_id => {
  const response = await fetch(`/api/tournament/brackets?id=${tournament_id}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchBracketsBySlug = async tournament_slug => {
  const response = await fetch(
    `/api/tournament/brackets?slug=${tournament_slug}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const fetchPositionPools = async tournament_id => {
  const response = await fetch(
    `/api/tournament/position-pools?id=${tournament_id}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const fetchPositionPoolsBySlug = async tournament_slug => {
  const response = await fetch(
    `/api/tournament/position-pools?slug=${tournament_slug}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const fetchMatches = async tournament_id => {
  const response = await fetch(`/api/tournament/${tournament_id}/matches`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchMatchesBySlug = async tournament_slug => {
  const response = await fetch(
    `/api/tournament/slug/${tournament_slug}/matches`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const fetchTournamentTeamBySlug = async (tournament_slug, team_slug) => {
  const response = await fetch(
    `/api/tournament/roster?tournament_slug=${tournament_slug}&team_slug=${team_slug}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

// Mutations ----------------

export const createTournament = async formData => {
  const response = await fetch("/api/tournament", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: formData
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const updateSeeding = async ({ id, body }) => {
  const response = await fetch(`/api/tournament/update/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(body)
  });
  return await response.json();
};

export const deleteTournament = async ({ id }) => {
  const response = await fetch(`/api/tournament/delete/${id}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });
  return await response.json();
};

export const createPool = async ({
  tournament_id,
  seq_num,
  name,
  seeding_list
}) => {
  const response = await fetch(`/api/tournament/pool/${tournament_id}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify({
      seeding: JSON.parse(seeding_list),
      sequence_number: parseInt(seq_num),
      name: name
    })
  });
  return await response.json();
};

export const createCrossPool = async ({ tournament_id }) => {
  const response = await fetch(`/api/tournament/cross-pool/${tournament_id}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });
  return await response.json();
};

export const createBracket = async ({ tournament_id, seq_num, name }) => {
  const response = await fetch(`/api/tournament/bracket/${tournament_id}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify({
      sequence_number: parseInt(seq_num),
      name: name
    })
  });
  return await response.json();
};

export const createPositionPool = async ({
  tournament_id,
  seq_num,
  name,
  seeding_list
}) => {
  const response = await fetch(
    `/api/tournament/position-pool/${tournament_id}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin",
      body: JSON.stringify({
        seeding: JSON.parse(seeding_list),
        sequence_number: parseInt(seq_num),
        name: name
      })
    }
  );
  return await response.json();
};

export const createMatch = async ({ tournament_id, body }) => {
  const response = await fetch(`/api/tournament/match/${tournament_id}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(body)
  });
  return await response.json();
};

export const updateMatch = async ({ match_id, body }) => {
  const response = await fetch(`/api/match/${match_id}/update`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(body)
  });
  return await response.json();
};

export const startTournament = async ({ tournament_id }) => {
  const response = await fetch(`/api/tournament/start/${tournament_id}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });
  return await response.json();
};

export const generateTournamentFixtures = async ({ tournament_id }) => {
  const response = await fetch(
    `/api/tournament/generate-fixtures/${tournament_id}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const addMatchScore = async ({ match_id, body }) => {
  const response = await fetch(`/api/match/${match_id}/score`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(body)
  });
  return await response.json();
};

export const addMatchSpiritScore = async ({ match_id, body }) => {
  const response = await fetch(`/api/match/${match_id}/update`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(body)
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};
