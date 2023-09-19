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
  const response = await fetch("/api/events", {
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

export const fetchTournaments = async () => {
  const response = await fetch("/api/tournaments", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchPools = async tournament_id => {
  const response = await fetch(`/api/tournament/${tournament_id}/pools`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchCrossPool = async tournament_id => {
  const response = await fetch(`/api/tournament/${tournament_id}/cross-pool`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

// Mutations ----------------

export const createTournament = async body => {
  const response = await fetch("/api/tournament", {
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

export const updateSeeding = async ({ id, body }) => {
  const response = await fetch(`/api/tournament/${id}`, {
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
  const response = await fetch(`/api/tournament/${id}`, {
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
  const response = await fetch(`/api/tournament/${tournament_id}/pool`, {
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
  const response = await fetch(`/api/tournament/${tournament_id}/cross-pool`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });
  return await response.json();
};
