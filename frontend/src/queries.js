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
