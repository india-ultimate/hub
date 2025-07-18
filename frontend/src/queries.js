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

export const fetchAllManualTransactions = async () => {
  const response = await fetch(
    "/api/transactions?user_only=false&only_manual=True",
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
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

export const fetchAllInvalidManualTransactions = async () => {
  const response = await fetch(
    "/api/transactions?user_only=false&only_invalid=true&only_manual=true",
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

export const fetchSeasons = async () => {
  const response = await fetch("/api/seasons", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const searchTeams = async (searchText, pagination) => {
  let baseUrl = "/api/teams/search";
  let params = new URLSearchParams();
  if (searchText) {
    params.set("text", searchText);
  }
  if (pagination.pageIndex) {
    params.set("page", pagination.pageIndex + 1);
  }
  if (params.toString().length > 0) {
    baseUrl = baseUrl + "?" + params.toString();
  }

  const response = await fetch(baseUrl, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const searchUsers = async searchText => {
  let baseUrl = "/api/users/search";
  let params = new URLSearchParams();
  if (searchText) {
    params.set("text", searchText);
  }
  if (params.toString().length > 0) {
    baseUrl = baseUrl + "?" + params.toString();
  }
  const response = await fetch(baseUrl, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const searchPlayers = async (searchText, pagination) => {
  let baseUrl = "/api/players/search";
  let params = new URLSearchParams();
  if (searchText) {
    params.set("text", searchText);
  }
  if (pagination.pageIndex) {
    params.set("page", pagination.pageIndex + 1);
  }
  if (params.toString().length > 0) {
    baseUrl = baseUrl + "?" + params.toString();
  }
  const response = await fetch(baseUrl, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const getRecommendedPlayers = async (teamSlug, pagination) => {
  let baseUrl = "/api/players/recommend";
  let params = new URLSearchParams();
  if (teamSlug) {
    params.set("team_slug", teamSlug);
  }
  if (pagination.pageIndex) {
    params.set("page", pagination.pageIndex + 1);
  }
  if (params.toString().length > 0) {
    baseUrl = baseUrl + "?" + params.toString();
  }
  const response = await fetch(baseUrl, {
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

export const fetchAllSeries = async () => {
  const response = await fetch("/api/series/all", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchSeriesBySlug = async series_slug => {
  const response = await fetch(`/api/series/?slug=${series_slug}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
};

export const fetchSeriesInvitations = async series_slug => {
  const response = await fetch(
    `/api/series/${series_slug}/invitations-received`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
};

export const fetchTeamSeriesInvitationsSent = async (
  series_slug,
  team_slug
) => {
  const response = await fetch(
    `/api/series/${series_slug}/team/${team_slug}/invitations-sent`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
};

export const fetchSeriesTeamBySlug = async (series_slug, team_slug) => {
  const response = await fetch(`/api/series/${series_slug}/team/${team_slug}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
};

export const fetchTeamSeriesRoster = async (series_slug, team_slug) => {
  const response = await fetch(
    `/api/series/${series_slug}/team/${team_slug}/roster`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
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

/**
 *
 * @param {string} tournament_slug
 * @returns
 */
export const fetchTournamentBySlug = async tournament_slug => {
  const response = await fetch(`/api/tournament?slug=${tournament_slug}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

/**
 * @typedef {object} TournamentField
 * @property {number} id
 * @property {string} name
 * @property {boolean} is_broadcasted
 */

/**
 * @param {number} tournament_id
 * @returns {Promise<TournamentField[]>}
 * @throws
 */
export const fetchFieldsByTournamentId = async tournament_id => {
  const response = await fetch(`/api/tournament/${tournament_id}/fields`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

/**
 * @param {string} slug
 * @returns {Promise<TournamentField[]>}
 * @throws
 */

export const fetchFieldsByTournamentSlug = async slug => {
  const response = await fetch(`/api/tournament/slug/${slug}/fields`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
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

export const fetchMatch = async match_id => {
  const response = await fetch(`/api/match/${match_id}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchMatchStats = async match_id => {
  const response = await fetch(`/api/match/${match_id}/stats`, {
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

export const searchSeriesRosterPlayers = async (
  tournament_slug,
  team_slug,
  searchText,
  pagination
) => {
  let baseUrl = `/api/tournament/${tournament_slug}/team/${team_slug}/players/search`;
  let params = new URLSearchParams();
  if (searchText) {
    params.set("text", searchText);
  }
  if (pagination.pageIndex) {
    params.set("page", pagination.pageIndex + 1);
  }
  if (params.toString().length > 0) {
    baseUrl = baseUrl + "?" + params.toString();
  }
  console.log(baseUrl);
  const response = await fetch(baseUrl, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  return await response.json();
};

export const fetchTournamentTeamMatches = async (
  tournament_slug,
  team_slug
) => {
  const response = await fetch(
    `/api/tournament/${tournament_slug}/team/${team_slug}/matches`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const fetchTournamentTeamBySlug = async (
  tournament_slug,
  team_slug,
  use_uc_registrations
) => {
  if (use_uc_registrations) {
    return await fetchTournamentTeamBySlugV1(tournament_slug, team_slug);
  }
  return await fetchTournamentTeamBySlugV2(tournament_slug, team_slug);
};

export const fetchTournamentTeamBySlugV1 = async (
  tournament_slug,
  team_slug
) => {
  const response = await fetch(
    `/api/v1/tournament/${tournament_slug}/team/${team_slug}/roster`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const fetchTournamentTeamBySlugV2 = async (
  tournament_slug,
  team_slug
) => {
  const response = await fetch(
    `/api/v2/tournament/${tournament_slug}/team/${team_slug}/roster`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const fetchTournamentTeamPointsBySlugV2 = async (
  tournament_slug,
  team_slug
) => {
  const response = await fetch(
    `/api/v2/tournament/${tournament_slug}/team/${team_slug}/roster-points`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const fetchUserAccessByTournamentSlug = async tournament_slug => {
  const response = await fetch(
    `/api/me/access?tournament_slug=${tournament_slug}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    }
  );
  return await response.json();
};

export const fetchUser = async () => {
  const response = await fetch("/api/me", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const fetchUserRegistrations = async () => {
  const response = await fetch("/api/me/registrations", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

// Mutations ----------------

export const createTournament = async formData => {
  const response = await fetch("/api/tournaments", {
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

export const createTournamentFromEvent = async formData => {
  const response = await fetch("/api/tournaments/event", {
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

export const updateSeeding = async ({ id, teamSeeding }) => {
  let seedToTeamId = {};
  teamSeeding.forEach(
    (teamId, seeding) => (seedToTeamId[(seeding + 1).toString()] = teamId)
  );
  const response = await fetch(`/api/tournament/update/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify({ seeding: seedToTeamId })
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

export const addTeamSeriesRegistration = async ({ series_slug, body }) => {
  const response = await fetch(`/api/series/${series_slug}/register-team`, {
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

export const removeTeamSeriesRegistration = async ({ series_slug, body }) => {
  const response = await fetch(`/api/series/${series_slug}/deregister-team`, {
    method: "DELETE",
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

export const invitePlayerToSeries = async ({
  series_slug,
  team_slug,
  body
}) => {
  const response = await fetch(
    `/api/series/${series_slug}/team/${team_slug}/invitation`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin",
      body: JSON.stringify(body)
    }
  );
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
};

export const revokeInvitation = async ({ invitation_id }) => {
  const response = await fetch(`/api/series/invitation/${invitation_id}`, {
    method: "DELETE",
    headers: {
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
};

export const acceptSeriesInvitationFromEmail = async ({ token }) => {
  const response = await fetch(`/api/series/invitation/accept?token=${token}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json"
    }
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
};

export const declineSeriesInvitationFromEmail = async ({ token }) => {
  const response = await fetch(
    `/api/series/invitation/decline?token=${token}`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json"
      }
    }
  );
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
};

export const acceptSeriesInvitation = async ({ invitation_id }) => {
  const response = await fetch(
    `/api/series/invitation/${invitation_id}/accept`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
};

export const declineSeriesInvitation = async ({ invitation_id }) => {
  const response = await fetch(
    `/api/series/invitation/${invitation_id}/decline`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }
  return data;
};

export const registerYourselfToSeries = async ({ series_slug, team_slug }) => {
  const response = await fetch(
    `/api/series/${series_slug}/team/${team_slug}/roster/add-self`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    }
  );
  const data = await response.json();

  if (!response.ok) {
    throw new Error(JSON.stringify(data));
  }
  return data;
};

export const addTeamRegistration = async ({ tournament_id, body }) => {
  const response = await fetch(
    `/api/tournament/${tournament_id}/register-team`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin",
      body: JSON.stringify(body)
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(JSON.stringify(data));
  }

  return data;
};

export const removeTeamRegistration = async ({ tournament_id, body }) => {
  const response = await fetch(
    `/api/tournament/${tournament_id}/deregister-team`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin",
      body: JSON.stringify(body)
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const addToRoster = async ({ event_id, team_id, body }) => {
  const response = await fetch(
    `/api/tournament/${event_id}/team/${team_id}/roster`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin",
      body: JSON.stringify(body)
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(JSON.stringify(data));
  }

  return data;
};

export const removeFromRoster = async ({
  event_id,
  team_id,
  registration_id
}) => {
  const response = await fetch(
    `/api/tournament/${event_id}/team/${team_id}/roster/${registration_id}`,
    {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    }
  );
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const updatePlayerRegistration = async ({
  event_id,
  team_id,
  registration_id,
  body
}) => {
  const response = await fetch(
    `/api/tournament/${event_id}/team/${team_id}/roster/${registration_id}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin",
      body: JSON.stringify(body)
    }
  );
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const createField = async ({ tournament_id, body }) => {
  const response = await fetch(`/api/tournament/${tournament_id}/field`, {
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

export const updateField = async ({ field_id, body }) => {
  const response = await fetch(`/api/tournament/field/${field_id}`, {
    method: "PUT",
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

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
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

export const submitMatchScore = async ({ match_id, body }) => {
  const response = await fetch(`/api/match/${match_id}/submit-score`, {
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

export const submitMatchSpiritScore = async ({ match_id, team_id, body }) => {
  const response = await fetch(`/api/match/${match_id}/submit-spirit-score`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify({ ...body, team_id })
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
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

export const deleteMatch = async ({ match_id }) => {
  const response = await fetch(`/api/match/${match_id}`, {
    method: "DELETE",
    headers: {
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });
  return await response.json();
};

export const updateTournamentRules = async ({ tournament_id, body }) => {
  const response = await fetch(`/api/tournament/rules/${tournament_id}`, {
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

export const createTeam = async formData => {
  const response = await fetch("/api/teams", {
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

export const updateTeamName = async body => {
  const response = await fetch("/api/teams/edit-name", {
    method: "PUT",
    headers: {
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

export const updateTeam = async formData => {
  const response = await fetch("/api/teams/edit", {
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

export const fetchTournamentLeaderboard = async tournament_slug => {
  const response = await fetch(
    `/api/tournament/${tournament_slug}/leaderboard`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        XrCSRFToken: getCookie("csrftoken")
      },
      credentials: "same-origin"
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const createMatchStats = async ({ match_id, body }) => {
  const response = await fetch(`/api/match/${match_id}/stats`, {
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

export const createMatchStatsEvent = async ({ match_id, body }) => {
  const response = await fetch(`/api/match/${match_id}/stats/event`, {
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

export const matchStatsSwitchOffense = async ({ match_id }) => {
  const response = await fetch(`/api/match/${match_id}/stats/switch-offense`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const matchStatsUndo = async ({ match_id }) => {
  const response = await fetch(`/api/match/${match_id}/stats/event/undo`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const matchStatsHalfTime = async ({ match_id }) => {
  const response = await fetch(`/api/match/${match_id}/stats/half-time`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

export const matchStatsFullTime = async ({ match_id }) => {
  const response = await fetch(`/api/match/${match_id}/stats/full-time`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data?.message || JSON.stringify(data));
  }

  return data;
};

// Ticket API functions
export const fetchTickets = async (filter = "") => {
  let queryParams = "";

  // Handle different filter types
  if (filter === "ME") {
    queryParams = "created_by_me=true";
  } else if (filter) {
    queryParams = `status=${filter}`;
  }

  const response = await fetch(`/api/ticket/?${queryParams}`, {
    method: "GET",
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to fetch tickets");
  }
  return data;
};

export const fetchTicketDetail = async ticketId => {
  const response = await fetch(`/api/ticket/${ticketId}`, {
    method: "GET",
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to fetch ticket details");
  }
  return data;
};

export const createTicket = async data => {
  const response = await fetch("/api/ticket/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(data)
  });

  const responseData = await response.json();
  if (!response.ok) {
    throw new Error(responseData?.message || "Failed to create ticket");
  }
  return responseData;
};

export const addTicketMessage = async (ticketId, data) => {
  const formData = new FormData();
  formData.append("message_details", JSON.stringify({ message: data.message }));
  if (data.attachment) {
    formData.append("attachment", data.attachment);
  }

  const response = await fetch(`/api/ticket/${ticketId}/message`, {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken")
      // Do not set Content-Type; browser will set it for FormData
    },
    credentials: "same-origin",
    body: formData
  });
  const responseData = await response.json();
  if (!response.ok) {
    throw new Error(responseData?.message || "Failed to add message");
  }
  return responseData;
};

export const updateTicket = async (ticketId, data) => {
  const response = await fetch(`/api/ticket/${ticketId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(data)
  });

  const responseData = await response.json();
  if (!response.ok) {
    throw new Error(responseData?.message || "Failed to update ticket");
  }
  return responseData;
};

// Election API functions
export const createElection = async data => {
  const response = await fetch("/api/election/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(data)
  });

  const responseData = await response.json();
  if (!response.ok) {
    throw new Error(responseData?.message || "Failed to create election");
  }
  return responseData;
};

export const fetchElections = async () => {
  const response = await fetch("/api/election/", {
    method: "GET",
    headers: {
      "Content-Type": "application/json"
    },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to fetch elections");
  }
  return data;
};

export const fetchElection = async electionId => {
  const response = await fetch(`/api/election/${electionId}/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json"
    },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to fetch election details");
  }
  return data;
};

export const updateElection = async (electionId, data) => {
  const response = await fetch(`/api/election/${electionId}/`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(data)
  });

  const responseData = await response.json();
  if (!response.ok) {
    throw new Error(responseData?.message || "Failed to update election");
  }
  return responseData;
};

export const deleteElection = async electionId => {
  const response = await fetch(`/api/election/${electionId}/`, {
    method: "DELETE",
    headers: {
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to delete election");
  }
  return data;
};

export const createCandidate = async (electionId, data) => {
  const response = await fetch(`/api/election/${electionId}/candidates/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Failed to create candidate");
  }

  return response.json();
};

export const fetchCandidates = async electionId => {
  const response = await fetch(`/api/election/${electionId}/candidates/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json"
    },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to fetch candidates");
  }
  return data;
};

export const getVoterVerification = async electionId => {
  const response = await fetch(`/api/election/${electionId}/verify/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Failed to verify voter eligibility");
  }

  return response.json();
};

export const castRankedVote = async (electionId, data) => {
  const response = await fetch(`/api/election/${electionId}/vote/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify(data)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Failed to cast vote");
  }

  return response.json();
};

export const fetchEligibleVoters = async electionId => {
  const response = await fetch(`/api/election/${electionId}/eligible-voters/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json"
    },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to fetch eligible voters");
  }
  return data;
};

export const importEligibleVoters = async (electionId, formData) => {
  const response = await fetch(`/api/election/${electionId}/eligible-voters/`, {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: formData
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to import eligible voters");
  }
  return data;
};

export const generateElectionResults = async electionId => {
  const response = await fetch(
    `/api/election/${electionId}/generate-results/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Failed to generate election results");
  }

  return response.json();
};

export const getElectionResults = async electionId => {
  const response = await fetch(`/api/election/${electionId}/results/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Failed to fetch election results");
  }

  return response.json();
};

export const getMyWards = async electionId => {
  const response = await fetch(`/api/election/${electionId}/my-wards/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json"
    },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to fetch wards");
  }
  return data;
};

export const castRankedVoteForWard = async (electionId, wardId, data) => {
  const response = await fetch(
    `/api/election/${electionId}/vote-for-ward/?ward_id=${wardId}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin",
      body: JSON.stringify(data)
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Failed to cast vote for ward");
  }

  return response.json();
};

export const getElectionVoteCount = async electionId => {
  const response = await fetch(`/api/election/${electionId}/vote-count/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json"
    },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to fetch vote count");
  }
  return data;
};

export const sendElectionNotification = async electionId => {
  const response = await fetch(
    `/api/election/${electionId}/send-notification/`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    }
  );

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to send election notification");
  }
  return data;
};

export const getEmailWorkerStatus = async () => {
  const response = await fetch("/api/election/email-worker-status/", {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to get email worker status");
  }
  return data;
};

// Chat API functions
export const fetchChatHistory = async () => {
  const response = await fetch("/api/chat/history", {
    method: "GET",
    headers: {
      "Content-Type": "application/json"
    },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to fetch chat history");
  }
  return data;
};

export const sendChatMessage = async message => {
  const response = await fetch("/api/chat/send_message", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: JSON.stringify({ message })
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to send message");
  }
  return data;
};

export const clearChatHistory = async () => {
  const response = await fetch("/api/chat/clear_history", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to clear chat history");
  }
  return data;
};

export const fetchMembershipStatus = async () => {
  const response = await fetch("/api/me/membership", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to fetch membership status");
  }
  return data;
};

// Profile Picture API functions
export const uploadProfilePicture = async file => {
  const formData = new FormData();
  formData.append("profile_pic", file);

  const response = await fetch("/api/profile-pic", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken")
    },
    credentials: "same-origin",
    body: formData
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.message || "Failed to upload profile picture");
  }
  return data;
};
